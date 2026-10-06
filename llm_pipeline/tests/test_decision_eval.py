import json
from pathlib import Path
from typing import Any

import pytest

from clinical_extraction.cli import REFERENCE_THRESHOLDS, main
from clinical_extraction.config import get_decision_settings
from clinical_extraction.decisioning.policy import ReviewStatus
from clinical_extraction.decisioning.providers.fake import FakeDecisionProvider
from clinical_extraction.decisioning.router import DecisionRouter, default_routes
from clinical_extraction.decisioning.verifier import CaseVerifier
from clinical_extraction.evals.dataset import load_dataset
from clinical_extraction.evals.decisions import (
    CLEAN,
    INJECTED_MISJUDGMENTS,
    MUTATIONS,
    build_scenarios,
    reference_provider,
    run_decision_eval,
)
from clinical_extraction.extractor import ClinicalCaseExtractor
from clinical_extraction.pipeline import ClinicalExtractionPipeline
from clinical_extraction.providers.fake import FakeProvider


def _verifier(provider: FakeDecisionProvider) -> CaseVerifier:
    router = DecisionRouter(
        {provider.name: provider}, default_routes(primary=provider.name, shadow_local=False)
    )
    return CaseVerifier(router)


def test_every_vignette_gets_a_clean_run_and_each_planted_defect() -> None:
    examples = load_dataset()
    scenarios = build_scenarios(examples)

    assert len(scenarios) == len(examples) * (1 + len(MUTATIONS))
    for scenario in scenarios:
        if scenario.defect != CLEAN:
            clean = next(e for e in examples if e.id == scenario.example_id).expected
            assert scenario.candidate != clean, scenario.defect


def test_the_eval_registers_exactly_the_injected_misjudgments() -> None:
    examples = load_dataset()

    summary = run_decision_eval(
        _verifier(reference_provider(examples)), examples, provider="reference", model="ref"
    )

    assert {f["example_id"] for f in summary.failures} == set(INJECTED_MISJUDGMENTS)
    assert summary.clean_pass_rate == 0.9
    assert summary.defect_detection_recall == 0.98
    assert summary.false_accept_rate == 0.02
    assert summary.recall_by_defect["title_leak"] == 0.9
    assert summary.verification_unavailable == 0


def test_a_verifier_that_flags_everything_is_not_rewarded() -> None:
    examples = load_dataset()

    def paranoid(source_text: str, query: Any) -> tuple[str, float]:
        del source_text, query
        return "not_stated", 0.2

    summary = run_decision_eval(
        _verifier(FakeDecisionProvider(paranoid)), examples, provider="paranoid", model="p"
    )

    assert summary.defect_detection_recall == 1.0
    assert summary.clean_pass_rate == 0.0


def test_an_outage_is_counted_and_nothing_is_accepted() -> None:
    examples = load_dataset()[:2]
    broken = FakeDecisionProvider(lambda *_: ("x", 1.0), fail=True)

    summary = run_decision_eval(_verifier(broken), examples, provider="down", model="d")

    assert summary.verification_unavailable == summary.scenarios
    assert summary.false_accept_rate == 0.0


def test_the_cli_gate_passes_and_reports_the_shadow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "decisions.json"

    assert main(["eval-decisions", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    for metric, threshold in REFERENCE_THRESHOLDS.items():
        assert payload[metric] >= threshold
    assert payload["shadow"]["held_out_examples"] == 20
    assert 0.0 <= payload["shadow"]["accuracy_held_out"] <= 1.0
    assert json.loads(capsys.readouterr().out)["provider"] == "reference"


def test_the_cli_gate_fails_when_the_verifier_degrades(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    degraded = tmp_path / "dataset.jsonl"
    with degraded.open("w", encoding="utf-8") as handle:
        for example in load_dataset():
            if example.id in INJECTED_MISJUDGMENTS:
                record = {
                    "id": example.id,
                    "raw_text": example.raw_text,
                    "expected": example.expected.model_dump(mode="json"),
                }
                handle.write(json.dumps(record) + "\n")

    assert main(["eval-decisions", "--dataset", str(degraded), "--no-shadow"]) == 1
    assert "decision eval gate failed" in capsys.readouterr().err


def test_typesafe_eval_needs_a_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    monkeypatch.chdir(Path(__file__).parent)  # away from any local .env
    get_decision_settings.cache_clear()

    assert main(["eval-decisions", "--provider", "typesafe"]) == 1
    assert "TYPESAFE_API_KEY" in capsys.readouterr().err


def test_the_pipeline_adds_verification_without_touching_scores() -> None:
    examples = load_dataset()
    example = examples[0]
    extractor = ClinicalCaseExtractor(
        FakeProvider.returning(example.expected.model_dump(mode="json")), max_attempts=1
    )

    plain = ClinicalExtractionPipeline(extractor).run(example.raw_text).to_dict()
    verified = (
        ClinicalExtractionPipeline(extractor, _verifier(reference_provider(examples)))
        .run(example.raw_text)
        .to_dict()
    )

    assert plain["verification"] is None
    assert verified["verification"]["status"] == ReviewStatus.ACCEPT
    # Keep scoring deterministic: verification must not change a single point.
    assert verified["case"] == plain["case"]
    assert verified["case"] == extractor.extract(example.raw_text).to_case_create_payload()


def test_eval_local_reports_held_out_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["eval-local", "--task", "finding_category"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dataset_matches_manifest"] is True
    assert payload["held_out"]["examples"] == 20
    assert payload["gate"]["passed"] is False


def test_train_local_cli_writes_an_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pytest.importorskip("sklearn")

    assert main(["train-local", "--task", "finding_category", "--models-dir", str(tmp_path)]) == 0

    assert (tmp_path / "finding_category" / "model.json").exists()
    assert json.loads(capsys.readouterr().out)["task"] == "finding_category"
