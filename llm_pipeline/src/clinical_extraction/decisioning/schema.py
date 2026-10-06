"""Typed inputs and outputs of the decision layer."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from clinical_extraction.decisioning.tasks import DecisionTask


@dataclass(frozen=True, slots=True)
class DecisionQuery:
    """One atomic question about one part of a candidate extraction.

    `target` points at the part being judged (`findings[2]`, `answers[0]`,
    `title`). It is safe to log; `subject` and `reference` are clinical text and
    are not.
    """

    id: str
    task: DecisionTask
    target: str
    subject: str
    reference: tuple[str, ...] = ()
    # Position of the finding or answer in the candidate; None for case-level fields.
    index: int | None = None


@dataclass(frozen=True, slots=True)
class Decision:
    query_id: str
    task: DecisionTask
    label: str
    probabilities: Mapping[str, float]
    # How clearly the top label wins, 0..1. Not a calibrated accuracy: each
    # provider's scale has to be checked against labelled data before a
    # threshold means anything.
    confidence: float
    provider: str
    model: str
    task_version: str


@dataclass(frozen=True, slots=True)
class DecisionBatch:
    """Answers from one provider call, with what the call cost."""

    decisions: Mapping[str, Decision]
    provider: str
    model: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 1

    @classmethod
    def empty(cls, provider: str, model: str) -> "DecisionBatch":
        return cls(decisions={}, provider=provider, model=model, latency_ms=0.0, calls=0)


def choice_confidence(probabilities: Mapping[str, float]) -> float:
    """How far the top probability sits above an even split, 0..1.

    The same summary TypeSafe documents for Choice answers, so a local model's
    confidence reads on a comparable scale. Comparable is not identical: the
    promotion gate still recalibrates per provider.
    """
    if not probabilities:
        return 0.0
    count = len(probabilities)
    if count == 1:
        return 1.0
    even = 1 / count
    top = max(probabilities.values())
    return round(max(0.0, (top - even) / (1 - even)), 4)


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    """A shadow provider's answer next to the primary one. Never used to decide."""

    query_id: str
    task: DecisionTask
    primary_label: str
    shadow_label: str
    shadow_confidence: float
    shadow_model: str

    @property
    def agrees(self) -> bool:
        return self.primary_label == self.shadow_label


@dataclass(frozen=True, slots=True)
class RoutedDecisions:
    primary: Mapping[str, Decision]
    batches: list[DecisionBatch] = field(default_factory=list)
    shadow: list[ShadowComparison] = field(default_factory=list)
    shadow_errors: int = 0
