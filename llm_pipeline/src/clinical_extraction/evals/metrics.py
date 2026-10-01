"""Extraction metrics against hand-written ground truth.

No LLM-as-a-judge: every number here is reproducible from the dataset.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from clinical_extraction.schema import ClinicalCaseExtraction

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = " .,;:!?\"'()[]{}"


def normalize(text: str) -> str:
    """The backend's scoring rule, so metrics match production matching."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", normalized).strip(_EDGE_PUNCTUATION)


# A finding is free text, so the model paraphrases: "Temperature 38.1 C" for
# "Temperature 38.1 °C". Exact match scores that as a miss, which measures
# wording rather than extraction. Two findings count as the same when their
# token sets overlap by at least this much.
SIMILARITY_THRESHOLD = 0.6


def _tokens(text: str) -> frozenset[str]:
    return frozenset(normalize(text).split())


def similarity(left: str, right: str) -> float:
    """Jaccard overlap of the two token sets, 0..1."""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def match_findings(predicted: list[str], expected: list[str]) -> tuple[int, int, int]:
    """Greedy one-to-one pairing above the threshold. Returns (tp, fp, fn)."""
    unmatched = list(expected)
    true_positives = 0
    for candidate in predicted:
        best = max(unmatched, key=lambda e: similarity(candidate, e), default=None)
        if best is not None and similarity(candidate, best) >= SIMILARITY_THRESHOLD:
            unmatched.remove(best)
            true_positives += 1
    return true_positives, len(predicted) - true_positives, len(unmatched)


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
        return cls.from_counts(
            len(predicted & expected), len(predicted - expected), len(expected - predicted)
        )

    @classmethod
    def from_counts(cls, tp: int, fp: int, fn: int) -> "SetMetrics":
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        return cls(round(precision, 4), round(recall, 4), round(f1, 4), tp, fp, fn)


class CaseStatus(StrEnum):
    """Why a case did or did not produce a scored extraction.

    A provider error is not a model error: a 429 means the request never reached
    the model, so counting it against schema validity would understate accuracy.
    The two are reported separately.
    """

    SCORED = "scored"
    SCHEMA_INVALID = "schema_invalid"
    PROVIDER_ERROR = "provider_error"
    MODEL_BLOCKED = "model_blocked"


@dataclass(frozen=True, slots=True)
class CaseReport:
    example_id: str
    status: CaseStatus
    error: str | None = None
    age_correct: bool | None = None
    sex_correct: bool | None = None
    answer_key_correct: bool | None = None
    findings: SetMetrics | None = None
    findings_exact: SetMetrics | None = None
    finding_category_accuracy: float | None = None
    mismatches: list[str] = field(default_factory=list)


def _answer_key(case: ClinicalCaseExtraction) -> set[str]:
    return {normalize(a.text) for a in case.answers if a.is_correct}


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

    expected_values = [f.value for f in expected.findings]
    predicted_values = [f.value for f in predicted.findings]
    findings = SetMetrics.from_counts(*match_findings(predicted_values, expected_values))
    if findings.f1 < 1.0:
        mismatches.append("findings")

    findings_exact = SetMetrics.compare(
        {normalize(v) for v in predicted_values}, {normalize(v) for v in expected_values}
    )

    # Category accuracy is measured only on the findings both sides agree on.
    matched: list[tuple[str, str]] = []
    available = list(expected.findings)
    for prediction in predicted.findings:
        best = max(available, key=lambda e: similarity(prediction.value, e.value), default=None)
        if best is not None and similarity(prediction.value, best.value) >= SIMILARITY_THRESHOLD:
            available.remove(best)
            matched.append((best.category, prediction.category))
    category_accuracy = (
        round(sum(e == p for e, p in matched) / len(matched), 4) if matched else None
    )
    if category_accuracy is not None and category_accuracy < 1.0:
        mismatches.append("finding_categories")

    return CaseReport(
        example_id=example_id,
        status=CaseStatus.SCORED,
        age_correct=age_correct,
        sex_correct=sex_correct,
        answer_key_correct=answer_key_correct,
        findings=findings,
        findings_exact=findings_exact,
        finding_category_accuracy=category_accuracy,
        mismatches=mismatches,
    )


@dataclass(frozen=True, slots=True)
class EvalSummary:
    provider: str
    model: str
    prompt_version: str
    total: int
    scored: int
    provider_errors: int
    model_blocked: int
    schema_valid_rate: float
    age_accuracy: float
    sex_accuracy: float
    answer_key_accuracy: float
    findings_precision: float
    findings_recall: float
    findings_f1: float
    findings_f1_exact_text: float
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
    valid = [r for r in reports if r.status is CaseStatus.SCORED]
    provider_errors = sum(1 for r in reports if r.status is CaseStatus.PROVIDER_ERROR)
    blocked = sum(1 for r in reports if r.status is CaseStatus.MODEL_BLOCKED)
    # Schema validity is measured over the responses the model actually returned.
    # A request that never reached the model, or that the model declined, is
    # neither a valid nor an invalid schema.
    answered = total - provider_errors - blocked
    categories = [
        r.finding_category_accuracy for r in valid if r.finding_category_accuracy is not None
    ]

    return EvalSummary(
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        total=total,
        scored=len(valid),
        provider_errors=provider_errors,
        model_blocked=blocked,
        schema_valid_rate=round(len(valid) / answered, 4) if answered else 0.0,
        age_accuracy=_mean([float(bool(r.age_correct)) for r in valid]),
        sex_accuracy=_mean([float(bool(r.sex_correct)) for r in valid]),
        answer_key_accuracy=_mean([float(bool(r.answer_key_correct)) for r in valid]),
        findings_precision=_mean([r.findings.precision for r in valid if r.findings]),
        findings_recall=_mean([r.findings.recall for r in valid if r.findings]),
        findings_f1=_mean([r.findings.f1 for r in valid if r.findings]),
        findings_f1_exact_text=_mean([r.findings_exact.f1 for r in valid if r.findings_exact]),
        finding_category_accuracy=_mean(categories) if categories else None,
        exact_case_match_rate=(
            round(sum(not r.mismatches for r in valid) / answered, 4) if answered else 0.0
        ),
        failures=[
            {
                "example_id": r.example_id,
                "status": r.status,
                "error": r.error,
                "mismatches": r.mismatches,
            }
            for r in reports
            if r.status is not CaseStatus.SCORED or r.mismatches
        ],
    )
