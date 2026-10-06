"""Train a local task model and write it as a versioned artifact.

Needs the optional `ml` dependency group (`uv sync --group ml`). Serving the
result does not: the artifact is JSON and inference is plain Python.
"""

import json
import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clinical_extraction.decisioning.tasks import TASKS, DecisionTask
from clinical_extraction.ml.evaluation import ClassifierMetrics, PromotionGate, evaluate_classifier
from clinical_extraction.ml.features import FeatureConfig, extract_features, tfidf_vector
from clinical_extraction.ml.model import (
    MODEL_FORMAT,
    ModelManifest,
    TextClassifier,
    save_model,
    sha256_text,
)
from clinical_extraction.ml.records import DecisionRecord, Split, fingerprint

SEED = 13


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    features: FeatureConfig = field(default_factory=FeatureConfig)
    # Inverse regularisation strength. Short phrases and few examples: keep the
    # weights moderate rather than memorising the seed list.
    c: float = 10.0
    max_iter: int = 5000
    # Out-of-distribution guard applied at serving time. Kept with the model so
    # changing it changes the model version, not just the runtime behaviour.
    min_feature_coverage: float = 0.3


@dataclass(frozen=True, slots=True)
class TrainingResult:
    classifier: TextClassifier
    manifest: ModelManifest
    held_out: ClassifierMetrics


def _require_sklearn() -> Any:
    try:
        from sklearn.linear_model import LogisticRegression  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError("training needs the ml dependency group: uv sync --group ml") from exc
    return LogisticRegression


def fit_classifier(records: Sequence[DecisionRecord], config: TrainingConfig) -> TextClassifier:
    import numpy as np  # noqa: PLC0415 - optional dependency, training only

    logistic_regression = _require_sklearn()
    counts = [extract_features(record.text, config.features) for record in records]

    document_frequency: Counter[str] = Counter()
    for features in counts:
        document_frequency.update(features.keys())
    total = len(records)
    # Smoothed idf, as if one extra document contained every feature.
    idf = {name: math.log((1 + total) / (1 + df)) + 1 for name, df in document_frequency.items()}
    vocabulary = {name: column for column, name in enumerate(sorted(idf))}

    matrix = np.zeros((total, len(vocabulary)))
    for row, features in enumerate(counts):
        for name, value in tfidf_vector(features, idf).items():
            matrix[row, vocabulary[name]] = value

    model = logistic_regression(
        C=config.c, max_iter=config.max_iter, class_weight="balanced", random_state=SEED
    )
    model.fit(matrix, [record.label for record in records])

    labels = tuple(str(label) for label in model.classes_)
    coefs = {
        name: tuple(float(model.coef_[k][column]) for k in range(len(labels)))
        for name, column in vocabulary.items()
    }
    return TextClassifier(
        labels=labels,
        config=config.features,
        idf=idf,
        coefs=coefs,
        intercept=tuple(float(value) for value in model.intercept_),
    )


def train_task(
    task: DecisionTask,
    records: Sequence[DecisionRecord],
    *,
    config: TrainingConfig | None = None,
    gate: PromotionGate | None = None,
) -> TrainingResult:
    config = config or TrainingConfig()
    gate = gate or PromotionGate()
    trusted = [r for r in records if r.trusted and r.task == task]
    train = [r for r in trusted if r.split is Split.TRAIN]
    held_out = [r for r in trusted if r.split is Split.HELD_OUT]
    if not train or not held_out:
        raise ValueError(f"{task}: need trusted records in both train and held-out splits")

    # Reload from JSON before scoring, so the metrics belong to the artifact
    # that ships, rounding included, and not to the in-memory sklearn model.
    classifier = TextClassifier.from_json(fit_classifier(train, config).to_json())
    metrics = evaluate_classifier(
        classifier, held_out, min_feature_coverage=config.min_feature_coverage
    )
    dataset_hash = fingerprint(trusted)
    hyperparameters = {
        "features": config.features.to_dict(),
        "c": config.c,
        "max_iter": config.max_iter,
        "class_weight": "balanced",
        "seed": SEED,
        "min_feature_coverage": config.min_feature_coverage,
    }
    # Data and settings both define the model: change either, get a new version.
    version_hash = sha256_text(dataset_hash + json.dumps(hyperparameters, sort_keys=True))

    manifest = ModelManifest(
        task=task,
        task_version=TASKS[task].version,
        model_type=MODEL_FORMAT,
        model_version=f"{task}-{MODEL_FORMAT}-{version_hash[:10]}",
        model_sha256=sha256_text(classifier.to_json()),
        labels=list(classifier.labels),
        dataset={
            "fingerprint": dataset_hash,
            "train_examples": len(train),
            "held_out_examples": len(held_out),
            "label_sources": dict(Counter(str(r.label_source) for r in trusted)),
        },
        hyperparameters=hyperparameters,
        held_out={**metrics.to_dict(), "gate_criteria": gate.to_dict()},
        gate=gate.check(metrics),
    )
    return TrainingResult(classifier=classifier, manifest=manifest, held_out=metrics)


def write_result(result: TrainingResult, models_dir: Path) -> Path:
    directory = models_dir / result.manifest.task
    save_model(directory, result.classifier, result.manifest)
    return directory
