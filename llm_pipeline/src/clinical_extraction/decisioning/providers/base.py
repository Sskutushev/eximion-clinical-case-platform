from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from clinical_extraction.decisioning.schema import DecisionBatch, DecisionQuery
from clinical_extraction.decisioning.tasks import DecisionTask


@runtime_checkable
class DecisionProvider(Protocol):
    """Answers bounded questions about a candidate extraction.

    Same contract for an external API (Jev), a local model and the test fake,
    so a task can move from one to another without touching the pipeline. A
    provider only answers: it never edits the candidate and never decides what
    happens to it. That is the policy's job.
    """

    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    def supports(self, task: DecisionTask) -> bool: ...

    def decide(self, source_text: str, queries: Sequence[DecisionQuery]) -> DecisionBatch: ...
