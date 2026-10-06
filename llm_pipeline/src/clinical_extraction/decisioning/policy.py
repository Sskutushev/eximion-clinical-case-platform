"""Turn decisions into an outcome: accept the candidate, or send it to review.

All of the judgement lives here, in plain code that can be read and tested.
Providers answer questions; they never edit the extraction. A disagreement is
a reason for a person to look, not permission for a model to overwrite the
value.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from clinical_extraction.decisioning.schema import Decision, DecisionQuery
from clinical_extraction.decisioning.tasks import ESTABLISHED, YES, DecisionTask
from clinical_extraction.schema import ClinicalCaseExtraction


class ReviewStatus(StrEnum):
    ACCEPT = "accept"
    NEEDS_REVIEW = "needs_review"


class Verdict(StrEnum):
    FLAGGED = "flagged"
    UNCERTAIN = "uncertain"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ReviewReason:
    """Why a candidate needs a person. Carries positions and labels, never clinical text."""

    check: str
    target: str
    verdict: Verdict
    detail: str
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class PolicyThresholds:
    # Experimental defaults. Calibrate on a dev split, confirm on held-out data.
    min_confidence: float = 0.5
    leak_flag_probability: float = 0.5


class VerificationPolicy:
    def __init__(self, thresholds: PolicyThresholds | None = None) -> None:
        self._thresholds = thresholds or PolicyThresholds()

    def evaluate(
        self,
        case: ClinicalCaseExtraction,
        queries: Sequence[DecisionQuery],
        decisions: Mapping[str, Decision],
    ) -> list[ReviewReason]:
        reasons: list[ReviewReason] = []
        for query in queries:
            decision = decisions[query.id]
            reason = self._check(case, query, decision)
            if reason is not None:
                reasons.append(reason)
        return reasons

    def _check(
        self, case: ClinicalCaseExtraction, query: DecisionQuery, decision: Decision
    ) -> ReviewReason | None:
        leak = self._leak(decision) if query.task is DecisionTask.DIAGNOSIS_LEAK else None
        if leak is not None:
            # A likely leak is flagged even when the verifier is unsure of it.
            outcome: tuple[Verdict, str] | None = leak
        elif decision.confidence < self._thresholds.min_confidence:
            # A low-confidence decision is reviewable, not a reason to guess.
            outcome = (Verdict.UNCERTAIN, f"{query.task} is unclear")
        elif query.task is DecisionTask.FINDING_SUPPORT:
            outcome = _support(decision)
        elif query.task is DecisionTask.FINDING_CATEGORY:
            outcome = _category(case, query, decision)
        elif query.task is DecisionTask.DIAGNOSIS_STATUS:
            outcome = _status(case, query, decision)
        elif query.task is DecisionTask.FINDING_COMPLETENESS:
            outcome = _completeness(decision)
        else:
            outcome = None

        if outcome is None:
            return None
        verdict, detail = outcome
        return ReviewReason(
            check=query.task,
            target=query.target,
            verdict=verdict,
            detail=detail,
            confidence=decision.confidence,
        )

    def _leak(self, decision: Decision) -> tuple[Verdict, str] | None:
        # A leak gives the answer away, so it has its own, lower bar than the
        # general confidence threshold. A "no" still has to be a confident one.
        yes = decision.probabilities.get(YES, 0.0)
        if yes >= self._thresholds.leak_flag_probability:
            return Verdict.FLAGGED, f"may reveal the diagnosis (p={yes:.2f})"
        return None


def _completeness(decision: Decision) -> tuple[Verdict, str] | None:
    if decision.label != "complete":
        return Verdict.FLAGGED, "the source may state findings the extraction missed"
    return None


def _support(decision: Decision) -> tuple[Verdict, str] | None:
    if decision.label != "supported":
        return Verdict.FLAGGED, f"finding is {decision.label} by the source"
    return None


def _category(
    case: ClinicalCaseExtraction, query: DecisionQuery, decision: Decision
) -> tuple[Verdict, str] | None:
    extracted = case.findings[_index(query)].category
    if decision.label != extracted:
        return Verdict.FLAGGED, f"extracted as {extracted}, verifier says {decision.label}"
    return None


def _status(
    case: ClinicalCaseExtraction, query: DecisionQuery, decision: Decision
) -> tuple[Verdict, str] | None:
    answer = case.answers[_index(query)]
    if decision.label == "not_stated":
        return Verdict.FLAGGED, "diagnosis is not stated in the source"
    if (decision.label == ESTABLISHED) != answer.is_correct:
        extracted = "established" if answer.is_correct else "not established"
        return Verdict.FLAGGED, f"extracted as {extracted}, verifier says {decision.label}"
    return None


def _index(query: DecisionQuery) -> int:
    if query.index is None:
        raise ValueError(f"{query.id} has no position in the candidate")
    return query.index
