import json
import shutil
from pathlib import Path

import pytest

from clinical_extraction.decisioning.providers.local import LocalDecisionProvider
from clinical_extraction.decisioning.router import DecisionRouter, Route
from clinical_extraction.decisioning.schema import DecisionQuery
from clinical_extraction.decisioning.tasks import DecisionTask
from clinical_extraction.errors import UnsupportedDecisionTaskError
from clinical_extraction.evals.dataset import load_dataset
from clinical_extraction.evals.metrics import normalize
from clinical_extraction.ml.datasets import HELD_OUT_CASES, finding_category_records
from clinical_extraction.ml.features import FeatureConfig, extract_features
from clinical_extraction.ml.model import (
    MODELS_DIR,
    ModelArtifactError,
    load_model,
)
from clinical_extraction.ml.records import DecisionRecord, LabelSource, Split, fingerprint

COMMITTED = MODELS_DIR / DecisionTask.FINDING_CATEGORY


def _records() -> list[DecisionRecord]:
    return finding_category_records(load_dataset())


def test_features_treat_measurements_alike() -> None:
    config = FeatureConfig()

    assert extract_features("Heart rate 96/min", config) == extract_features(
        "Heart rate 54/min", config
    )
    assert "w:rate 00" in extract_features("Heart rate 96/min", config)
    assert "c: hear" in extract_features("Heart rate 96/min", config)


def test_no_vignette_lands_on_both_sides_of_the_split() -> None:
    records = _records()
    train_groups = {r.case_group_id for r in records if r.split is Split.TRAIN}
    held_groups = {r.case_group_id for r in records if r.split is Split.HELD_OUT}

    assert train_groups.isdisjoint(held_groups)
    assert held_groups == HELD_OUT_CASES


def test_the_held_out_set_covers_every_category() -> None:
    held_out = {r.label for r in _records() if r.split is Split.HELD_OUT}

    assert len(held_out) == 7


def test_seed_phrases_are_not_copies_of_eval_findings() -> None:
    records = _records()
    eval_texts = {
        normalize(r.text) for r in records if r.label_source is LabelSource.SYNTHETIC_GROUND_TRUTH
    }
    seeds = [r for r in records if r.label_source is LabelSource.SYNTHETIC_SEED]

    assert seeds
    assert not {normalize(r.text) for r in seeds} & eval_texts
    assert all(r.split is Split.TRAIN for r in seeds)


def test_the_committed_model_matches_the_current_dataset() -> None:
    """Change the data and this fails until the model is retrained: no stale artifacts."""
    loaded = load_model(COMMITTED)
    trusted = [r for r in _records() if r.trusted]

    assert loaded.manifest.dataset["fingerprint"] == fingerprint(trusted)
    assert not loaded.manifest.gate.passed, "promoting a model is a deliberate, reviewed change"


def test_a_tampered_artifact_is_refused(tmp_path: Path) -> None:
    copy = tmp_path / "finding_category"
    shutil.copytree(COMMITTED, copy)
    model_file = copy / "model.json"
    model_file.write_text(model_file.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(ModelArtifactError, match="does not match"):
        load_model(copy)


def test_a_malformed_artifact_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactError, match="cannot read"):
        load_model(tmp_path)

    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ModelArtifactError, match="malformed"):
        load_model(tmp_path)


def test_the_local_provider_answers_only_what_it_has_a_model_for() -> None:
    local = LocalDecisionProvider.from_directory()
    finding = DecisionQuery(
        id="findings.0.category",
        task=DecisionTask.FINDING_CATEGORY,
        target="findings[0]",
        subject="Serum potassium 6.1 mmol/L",
        index=0,
    )
    status = DecisionQuery(
        id="answers.0.status",
        task=DecisionTask.DIAGNOSIS_STATUS,
        target="answers[0]",
        subject="Hyperkalaemia",
        index=0,
    )

    batch = local.decide("source", [finding])
    decision = batch.decisions[finding.id]
    assert decision.label in {"laboratory", "vital_sign", "imaging", "other"}
    assert sum(decision.probabilities.values()) == pytest.approx(1.0, abs=1e-4)
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.provider == "local"

    assert local.supports(DecisionTask.FINDING_CATEGORY)
    assert not local.supports(DecisionTask.DIAGNOSIS_STATUS)
    with pytest.raises(UnsupportedDecisionTaskError):
        local.decide("source", [status])


def test_an_empty_models_directory_supports_nothing(tmp_path: Path) -> None:
    local = LocalDecisionProvider.from_directory(tmp_path)

    assert not any(local.supports(task) for task in DecisionTask)
    assert local.model == "none"


def test_a_model_for_an_old_task_version_is_refused(tmp_path: Path) -> None:
    copy = tmp_path / "finding_category"
    shutil.copytree(COMMITTED, copy)
    manifest = json.loads((copy / "manifest.json").read_text(encoding="utf-8"))
    manifest["task_version"] = "finding-category-v0"
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="retrain"):
        LocalDecisionProvider.from_directory(tmp_path)


# ── Training (needs the optional ml group) ────────────────────────────────────


def test_retraining_reproduces_the_committed_model(tmp_path: Path) -> None:
    pytest.importorskip("sklearn")
    from clinical_extraction.ml.train import train_task, write_result  # noqa: PLC0415

    committed = load_model(COMMITTED)
    result = train_task(DecisionTask.FINDING_CATEGORY, _records())
    write_result(result, tmp_path)
    retrained = load_model(tmp_path / "finding_category")

    assert retrained.manifest.model_version == committed.manifest.model_version
    held_out = [r for r in _records() if r.split is Split.HELD_OUT]
    for record in held_out:
        fresh = retrained.classifier.predict_proba(record.text)
        stored = committed.classifier.predict_proba(record.text)
        assert max(fresh, key=fresh.__getitem__) == max(stored, key=stored.__getitem__)
        for label, probability in stored.items():
            assert fresh[label] == pytest.approx(probability, abs=1e-3)


def test_training_needs_both_splits() -> None:
    pytest.importorskip("sklearn")
    from clinical_extraction.ml.train import train_task  # noqa: PLC0415

    train_only = [r for r in _records() if r.split is Split.TRAIN]
    with pytest.raises(ValueError, match="both train and held-out"):
        train_task(DecisionTask.FINDING_CATEGORY, train_only)


def test_a_local_model_cannot_go_primary_before_its_gate() -> None:
    local = LocalDecisionProvider.from_directory()
    routes = {DecisionTask.FINDING_CATEGORY: Route(primary="local")}

    assert not local.promotable(DecisionTask.FINDING_CATEGORY)
    with pytest.raises(ValueError, match="promotion gate"):
        DecisionRouter({"local": local}, routes)
    # An explicit experiment may still do it, knowingly.
    DecisionRouter({"local": local}, routes, allow_ungated_local=True)
