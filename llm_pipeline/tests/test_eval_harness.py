import json
from pathlib import Path

import pytest

from clinical_extraction.cli import FAKE_THRESHOLDS, main
from clinical_extraction.evals.dataset import DEFAULT_DATASET, load_dataset
from clinical_extraction.evals.fixtures import INJECTED_DEFECTS, build_fixtures
from clinical_extraction.evals.runner import run_eval
from clinical_extraction.providers.fake import FakeProvider


def test_dataset_is_valid_and_covers_the_contract() -> None:
    examples = load_dataset()

    assert len(examples) == 10
    assert len({e.id for e in examples}) == 10
    categories = {f.category for e in examples for f in e.expected.findings}
    assert len(categories) == 7, "every finding category should appear in the dataset"
    assert any(e.expected.patient_age is None for e in examples), "unstated age must be covered"
    assert any(len([a for a in e.expected.answers if a.is_correct]) > 1 for e in examples), (
        "synonym answer keys must be covered"
    )


def test_dataset_contains_no_identifiers() -> None:
    raw = DEFAULT_DATASET.read_text(encoding="utf-8").lower()
    for marker in ("mrn", "ssn", "@", "phone", "+1", "street"):
        assert marker not in raw


def test_eval_detects_the_injected_defects() -> None:
    examples = load_dataset()
    provider = FakeProvider(build_fixtures(examples))

    summary = run_eval(provider, examples, provider_name="fake")

    assert summary.total == 10
    failed_ids = {f["example_id"] for f in summary.failures}
    assert failed_ids == set(INJECTED_DEFECTS)
    # case-009 carries an invalid category, so it must fail schema validation.
    assert summary.schema_valid_rate == 0.9
    assert next(f for f in summary.failures if f["example_id"] == "case-009")["error"] is not None
    assert summary.answer_key_accuracy < 1.0
    assert summary.findings_recall < 1.0
    assert summary.age_accuracy < 1.0


def test_eval_gate_passes_for_the_fake_provider(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "summary.json"

    exit_code = main(["eval", "--provider", "fake", "--output", str(output)])

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    for metric, threshold in FAKE_THRESHOLDS.items():
        assert payload[metric] >= threshold
    assert json.loads(capsys.readouterr().out)["provider"] == "fake"


def test_eval_gate_fails_when_metrics_degrade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    examples = load_dataset()
    degraded = tmp_path / "dataset.jsonl"
    # Keep only cases whose fixtures are defective: the gate must then fail.
    with degraded.open("w", encoding="utf-8") as handle:
        for example in examples:
            if example.id in INJECTED_DEFECTS:
                handle.write(
                    json.dumps(
                        {
                            "id": example.id,
                            "raw_text": example.raw_text,
                            "expected": example.expected.model_dump(mode="json"),
                        }
                    )
                    + "\n"
                )

    exit_code = main(["eval", "--provider", "fake", "--dataset", str(degraded)])

    assert exit_code == 1
    assert "eval gate failed" in capsys.readouterr().err


def test_dataset_errors_are_explicit(tmp_path: Path) -> None:
    broken = tmp_path / "broken.jsonl"
    broken.write_text('{"id": "x", "raw_text": "t"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        load_dataset(broken)

    empty = tmp_path / "empty.jsonl"
    empty.write_text("\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no examples"):
        load_dataset(empty)
