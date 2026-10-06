"""A trained text classifier and its manifest, loaded without any ML dependency.

The artifact is plain JSON, not a pickle: loading it cannot execute code, and a
reviewer can read exactly what changed between two model versions.
"""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clinical_extraction.ml.features import FeatureConfig, extract_features, tfidf_vector

MODEL_FORMAT = "tfidf-logreg-v1"
MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
MODEL_FILE = "model.json"
MANIFEST_FILE = "manifest.json"


class ModelArtifactError(Exception):
    """The artifact is missing, malformed or does not match its manifest."""


@dataclass(frozen=True, slots=True)
class TextClassifier:
    labels: tuple[str, ...]
    config: FeatureConfig
    idf: Mapping[str, float]
    # feature -> one weight per label
    coefs: Mapping[str, tuple[float, ...]]
    intercept: tuple[float, ...]

    def predict_proba(self, text: str) -> dict[str, float]:
        vector = tfidf_vector(extract_features(text, self.config), self.idf)
        logits = list(self.intercept)
        for name, value in vector.items():
            for index, weight in enumerate(self.coefs[name]):
                logits[index] += value * weight
        top = max(logits)
        exps = [math.exp(logit - top) for logit in logits]
        total = sum(exps)
        return {label: exp / total for label, exp in zip(self.labels, exps, strict=True)}

    def predict(self, text: str) -> str:
        probabilities = self.predict_proba(text)
        return max(probabilities, key=probabilities.__getitem__)

    def to_json(self) -> str:
        payload = {
            "format": MODEL_FORMAT,
            "labels": list(self.labels),
            "config": self.config.to_dict(),
            "intercept": [round(value, 6) for value in self.intercept],
            "features": {
                name: [round(self.idf[name], 6), [round(w, 6) for w in self.coefs[name]]]
                for name in sorted(self.idf)
            },
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> "TextClassifier":
        try:
            data = json.loads(raw)
            if data["format"] != MODEL_FORMAT:
                raise ModelArtifactError(f"unsupported model format {data['format']!r}")
            labels = tuple(data["labels"])
            features = data["features"]
            idf = {name: float(entry[0]) for name, entry in features.items()}
            coefs = {name: tuple(float(w) for w in entry[1]) for name, entry in features.items()}
            intercept = tuple(float(value) for value in data["intercept"])
            config = FeatureConfig.from_dict(data["config"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelArtifactError(f"malformed model artifact: {exc}") from exc
        if len(intercept) != len(labels) or any(len(c) != len(labels) for c in coefs.values()):
            raise ModelArtifactError("model weights do not match its labels")
        return cls(labels=labels, config=config, idf=idf, coefs=coefs, intercept=intercept)


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ModelManifest:
    """Everything needed to trust, compare or reproduce a model version."""

    task: str
    task_version: str
    model_type: str
    model_version: str
    model_sha256: str
    labels: list[str]
    dataset: dict[str, Any]
    hyperparameters: dict[str, Any]
    held_out: dict[str, Any]
    gate: GateResult

    def to_json(self) -> str:
        payload = {
            "task": self.task,
            "task_version": self.task_version,
            "model_type": self.model_type,
            "model_version": self.model_version,
            "model_sha256": self.model_sha256,
            "labels": self.labels,
            "dataset": self.dataset,
            "hyperparameters": self.hyperparameters,
            "held_out": self.held_out,
            "gate": {"passed": self.gate.passed, "reasons": self.gate.reasons},
        }
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> "ModelManifest":
        try:
            data = json.loads(raw)
            gate = GateResult(passed=bool(data["gate"]["passed"]), reasons=data["gate"]["reasons"])
            return cls(
                task=data["task"],
                task_version=data["task_version"],
                model_type=data["model_type"],
                model_version=data["model_version"],
                model_sha256=data["model_sha256"],
                labels=list(data["labels"]),
                dataset=dict(data["dataset"]),
                hyperparameters=dict(data["hyperparameters"]),
                held_out=dict(data["held_out"]),
                gate=gate,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelArtifactError(f"malformed manifest: {exc}") from exc


def sha256_text(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class LoadedModel:
    manifest: ModelManifest
    classifier: TextClassifier


def load_model(directory: Path) -> LoadedModel:
    """Load a model and refuse it if the weights are not the ones the manifest describes."""
    try:
        manifest_raw = (directory / MANIFEST_FILE).read_text(encoding="utf-8")
        model_raw = (directory / MODEL_FILE).read_text(encoding="utf-8")
    except OSError as exc:
        raise ModelArtifactError(f"cannot read model in {directory.name}: {exc}") from exc
    manifest = ModelManifest.from_json(manifest_raw)
    if sha256_text(model_raw) != manifest.model_sha256:
        raise ModelArtifactError(f"{directory.name}: model.json does not match its manifest")
    classifier = TextClassifier.from_json(model_raw)
    if list(classifier.labels) != manifest.labels:
        raise ModelArtifactError(f"{directory.name}: labels differ from the manifest")
    return LoadedModel(manifest=manifest, classifier=classifier)


def save_model(directory: Path, classifier: TextClassifier, manifest: ModelManifest) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MODEL_FILE).write_text(classifier.to_json(), encoding="utf-8", newline="\n")
    (directory / MANIFEST_FILE).write_text(manifest.to_json(), encoding="utf-8", newline="\n")
