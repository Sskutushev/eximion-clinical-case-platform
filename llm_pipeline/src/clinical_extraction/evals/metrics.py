"""Extraction metrics against hand-written ground truth.

No LLM-as-a-judge: every number here is reproducible from the dataset.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any

from clinical_extraction.schema import ClinicalCaseExtraction

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = " .,;:!?\"'()[]{}"


def normalize(text: str) -> str:
    """The backend's scoring rule, so metrics match production matching."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", normalized).strip(_EDGE_PUNCTUATION)


@dataclass(frozen=True, slots=True)
class SetMetrics:
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int

    @classmethod
    def compare(cls, predicted: set[str], expected: set[str]) -> "SetMetrics":
        tp = len(predicted & expected)
        fp = len(predicted - expected)
        fn = len(expected - predicted)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return cls(round(precision, 4), round(recall, 4), round(f1, 4), tp, fp, fn)


@dataclass(frozen=True, slots=True)
class CaseReport:
    """Per-example outcome. `schema_valid=False` means extraction failed outright."""

    example_id: str
    schema_valid: bool
    error: str | None = None
    age_correct: bool | None = None
    sex_correct: bool | None = None
    answer_key_correct: bool | None = None
    findings: SetMetrics | None = None
    finding_category_accuracy: float | None = None
    mismatches: list[str] = field(default_factory=list)


def _answer_key(case: ClinicalCaseExtraction) -> set[str]:
    return {normalize(a.text) for a in case.answers if a.is_correct and a.score_weight > 0}


def evaluate_case(
    expected: ClinicalCaseExtraction, predicted: ClinicalCaseExtraction, example_id: str
) -> CaseReport:
    mismatches: list[str] = []

    age_correct = expected.patient_age == predicted.patient_age
    if not age_correct:
        mismatches.append("patient_age")
    sex_correct = expected.patient_sex == predicted.patient_sex
    if not sex_correct:
        mismatches.append("patient_sex")

    # The accepted set must match exactly: a missed synonym would silently
    # reject a valid physician answer in production.
    answer_key_correct = _answer_key(predicted) == _answer_key(expected)
    if not answer_key_correct:
        mismatches.append("answer_key")

    expected_values = {normalize(f.value) for f in expected.findings}
    predicted_values = {normalize(f.value) for f in predicted.findings}
    findings = SetMetrics.compare(predicted_values, expected_values)
    if findings.f1 < 1.0:
        mismatches.append("findings")

    # Category accuracy is measured only on the findings both sides agree on.
    expected_categories = {normalize(f.value): f.category for f in expected.findings}
    matched = [
        (expected_categories[normalize(f.value)], f.category)
        for f in predicted.findings
        if normalize(f.value) in expected_categories
    ]
    category_accuracy = (
        round(sum(e == p for e, p in matched) / len(matched), 4) if matched else None
    )
    if category_accuracy is not None and category_accuracy < 1.0:
        mismatches.append("finding_categories")

    return CaseReport(
        example_id=example_id,
        schema_valid=True,
        age_correct=age_correct,
        sex_correct=sex_correct,
        answer_key_correct=answer_key_correct,
        findings=findings,
        finding_category_accuracy=category_accuracy,
        mismatches=mismatches,
    )


@dataclass(frozen=True, slots=True)
class EvalSummary:
    provider: str
    model: str
    prompt_version: str
    total: int
    schema_valid_rate: float
    age_accuracy: float
    sex_accuracy: float
    answer_key_accuracy: float
    findings_precision: float
    findings_recall: float
    findings_f1: float
    finding_category_accuracy: float | None
    exact_case_match_rate: float
    failures: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def summarize(
    reports: list[CaseReport], *, provider: str, model: str, prompt_version: str
) -> EvalSummary:
    total = len(reports)
    valid = [r for r in reports if r.schema_valid]
    categories = [
        r.finding_category_accuracy for r in valid if r.finding_category_accuracy is not None
    ]

    return EvalSummary(
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        total=total,
        schema_valid_rate=round(len(valid) / total, 4) if total else 0.0,
        age_accuracy=_mean([float(bool(r.age_correct)) for r in valid]),
        sex_accuracy=_mean([float(bool(r.sex_correct)) for r in valid]),
        answer_key_accuracy=_mean([float(bool(r.answer_key_correct)) for r in valid]),
        findings_precision=_mean([r.findings.precision for r in valid if r.findings]),
        findings_recall=_mean([r.findings.recall for r in valid if r.findings]),
        findings_f1=_mean([r.findings.f1 for r in valid if r.findings]),
        finding_category_accuracy=_mean(categories) if categories else None,
        exact_case_match_rate=(
            round(sum(not r.mismatches for r in valid) / total, 4) if total else 0.0
        ),
        failures=[
            {
                "example_id": r.example_id,
                "schema_valid": r.schema_valid,
                "error": r.error,
                "mismatches": r.mismatches,
            }
            for r in reports
            if not r.schema_valid or r.mismatches
        ],
    )
