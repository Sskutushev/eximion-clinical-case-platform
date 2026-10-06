"""Held-out metrics for a classifier, and the gate a model must pass to go live."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Any

from clinical_extraction.evals.metrics import percentile
from clinical_extraction.ml.model import GateResult, TextClassifier
from clinical_extraction.ml.records import DecisionRecord


@dataclass(frozen=True, slots=True)
class ClassifierMetrics:
    examples: int
    accuracy: float
    macro_f1: float
    per_label: dict[str, dict[str, float]]
    # How often the out-of-distribution guard would send a held-out example to
    # review, and how familiar typical text is. A model that is accurate but
    # unsure of a fifth of normal findings still sends a fifth of them to people.
    ood_review_rate: float
    feature_coverage_p05: float
    feature_coverage_p50: float
    errors: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_classifier(
    classifier: TextClassifier,
    records: Sequence[DecisionRecord],
    *,
    min_feature_coverage: float,
) -> ClassifierMetrics:
    """Score the exported classifier, the exact thing that would run in production."""
    predictions = [(record, classifier.predict(record.text)) for record in records]
    coverage = [classifier.coverage(record.text) for record in records]
    correct = sum(record.label == predicted for record, predicted in predictions)

    per_label: dict[str, dict[str, float]] = {}
    for label in classifier.labels:
        tp = sum(r.label == label and p == label for r, p in predictions)
        fp = sum(r.label != label and p == label for r, p in predictions)
        fn = sum(r.label == label and p != label for r, p in predictions)
        support = tp + fn
        if support == 0 and fp == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    f1_scores = [values["f1"] for values in per_label.values()]
    return ClassifierMetrics(
        examples=len(records),
        accuracy=round(correct / len(records), 4) if records else 0.0,
        macro_f1=round(sum(f1_scores) / len(f1_scores), 4) if f1_scores else 0.0,
        per_label=per_label,
        ood_review_rate=(
            round(sum(c < min_feature_coverage for c in coverage) / len(coverage), 4)
            if coverage
            else 0.0
        ),
        # The low tail matters more than the top: it is where the guard fires.
        feature_coverage_p05=percentile(coverage, 5),
        feature_coverage_p50=percentile(coverage, 50),
        # Record ids and labels only, so the report can be shared without the text.
        errors=[
            {"record_id": r.record_id, "expected": r.label, "predicted": p}
            for r, p in predictions
            if r.label != p
        ],
    )


@dataclass(frozen=True, slots=True)
class PromotionGate:
    """Offline conditions before a local model may answer instead of Jev.

    Passing it is necessary, not sufficient: the model then runs in shadow next
    to the current provider, and only a clean comparison there moves traffic.
    The bar is deliberately higher than "beats Jev on ten cases".
    """

    min_examples: int = 200
    min_accuracy: float = 0.95
    min_macro_f1: float = 0.90
    max_ood_review_rate: float = 0.05

    def check(self, metrics: ClassifierMetrics) -> GateResult:
        reasons = []
        if metrics.examples < self.min_examples:
            reasons.append(
                f"held-out set has {metrics.examples} examples, needs {self.min_examples}"
            )
        if metrics.accuracy < self.min_accuracy:
            reasons.append(f"accuracy {metrics.accuracy} is below {self.min_accuracy}")
        if metrics.macro_f1 < self.min_macro_f1:
            reasons.append(f"macro F1 {metrics.macro_f1} is below {self.min_macro_f1}")
        if metrics.ood_review_rate > self.max_ood_review_rate:
            reasons.append(
                f"out-of-distribution review rate {metrics.ood_review_rate} "
                f"is above {self.max_ood_review_rate}"
            )
        return GateResult(passed=not reasons, reasons=reasons)

    def to_dict(self) -> dict[str, float]:
        return {key: float(value) for key, value in asdict(self).items()}
