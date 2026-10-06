"""Deterministic decision provider for tests, CI and the offline eval."""

from collections.abc import Callable, Collection, Sequence

from clinical_extraction.decisioning.schema import (
    Decision,
    DecisionBatch,
    DecisionQuery,
    choice_confidence,
)
from clinical_extraction.decisioning.tasks import TASKS, DecisionTask
from clinical_extraction.errors import DecisionProviderError

FAKE_DECISION_MODEL = "fake-decider-1"

# (source_text, query) -> (label, probability given to that label)
Answerer = Callable[[str, DecisionQuery], tuple[str, float]]


class FakeDecisionProvider:
    def __init__(
        self,
        answer: Answerer,
        *,
        tasks: Collection[DecisionTask] | None = None,
        name: str = "fake",
        model: str = FAKE_DECISION_MODEL,
        fail: bool = False,
    ) -> None:
        self._answer = answer
        self._tasks = frozenset(tasks if tasks is not None else TASKS)
        self._name = name
        self._model = model
        self._fail = fail
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def model(self) -> str:
        return self._model

    def supports(self, task: DecisionTask) -> bool:
        return task in self._tasks

    def decide(self, source_text: str, queries: Sequence[DecisionQuery]) -> DecisionBatch:
        self.calls += 1
        if self._fail:
            raise DecisionProviderError("fake provider configured to fail", retryable=True)
        decisions = {}
        for query in queries:
            label, top = self._answer(source_text, query)
            decisions[query.id] = self._decision(query, label, top)
        return DecisionBatch(
            decisions=decisions, provider=self.name, model=self.model, latency_ms=0.0
        )

    def _decision(self, query: DecisionQuery, label: str, top: float) -> Decision:
        labels = list(TASKS[query.task].labels)
        rest = (1 - top) / (len(labels) - 1)
        probabilities = {name: (top if name == label else rest) for name in labels}
        return Decision(
            query_id=query.id,
            task=query.task,
            label=label,
            probabilities=probabilities,
            confidence=choice_confidence(probabilities),
            provider=self.name,
            model=self.model,
            task_version=TASKS[query.task].version,
        )
