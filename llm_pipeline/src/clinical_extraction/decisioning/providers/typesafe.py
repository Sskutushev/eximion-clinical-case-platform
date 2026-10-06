"""Jev (TypeSafe System One) as a decision provider.

A thin adapter: questions out, typed decisions back. One request per case,
because Jev evaluates independent questions in parallel and bills the shared
state once. No routing and no thresholds in here.
"""

import logging
import time
from collections.abc import Mapping, Sequence
from typing import Any

from typesafe_sdk import (
    Choice,
    ChoiceAnswer,
    Noul,
    NoulAnswer,
    Question,
    RetryPolicy,
    TypeSafeAPIError,
    TypeSafeClient,
    TypeSafeError,
)

from clinical_extraction.config import DecisionSettings
from clinical_extraction.decisioning.schema import Decision, DecisionBatch, DecisionQuery
from clinical_extraction.decisioning.tasks import NO, TASKS, YES, DecisionTask, TaskKind
from clinical_extraction.errors import DecisionProviderError

logger = logging.getLogger(__name__)

# The SDK logs request and response bodies at debug level. Here those bodies are
# clinical text, so its logger stays at WARNING whatever the app's level is.
logging.getLogger("typesafe_sdk").setLevel(logging.WARNING)

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_YES_NO_MIDPOINT = 0.5

# What the subject is called inside the question, so Jev reads "finding" or
# "diagnosis" rather than an anonymous field.
_SUBJECT_KEY: Mapping[DecisionTask, str] = {
    DecisionTask.FINDING_SUPPORT: "finding",
    DecisionTask.FINDING_CATEGORY: "finding",
    DecisionTask.DIAGNOSIS_STATUS: "diagnosis",
    DecisionTask.DIAGNOSIS_LEAK: "text",
}


def build_question(query: DecisionQuery) -> Question:
    spec = TASKS[query.task]
    instructions: dict[str, Any] = {
        "question": spec.question,
        _SUBJECT_KEY[query.task]: query.subject,
    }
    if spec.kind is TaskKind.BINARY:
        instructions["diagnoses"] = list(query.reference)
        return Noul(
            instructions=instructions,
            criteria={"true": spec.labels[YES], "false": spec.labels[NO]},
        )
    return Choice(instructions=instructions, criteria=dict(spec.labels))


class TypeSafeDecisionProvider:
    def __init__(self, settings: DecisionSettings, client: TypeSafeClient | None = None) -> None:
        self._model = settings.jev_model
        self._client = client or self._build_client(settings)

    @staticmethod
    def _build_client(settings: DecisionSettings) -> TypeSafeClient:
        if settings.typesafe_api_key is None:
            raise DecisionProviderError("TYPESAFE_API_KEY is not set")
        try:
            return TypeSafeClient(
                api_key=settings.typesafe_api_key.get_secret_value(),
                model=settings.jev_model,
                timeout=settings.typesafe_timeout_seconds,
                retry=RetryPolicy(max_retries=settings.typesafe_max_retries),
            )
        except TypeSafeError as exc:
            raise DecisionProviderError(f"TypeSafe client misconfigured: {exc}") from exc

    @property
    def name(self) -> str:
        return "typesafe"

    @property
    def model(self) -> str:
        return self._model

    def supports(self, task: DecisionTask) -> bool:
        return task in TASKS

    def decide(self, source_text: str, queries: Sequence[DecisionQuery]) -> DecisionBatch:
        if not queries:
            return DecisionBatch.empty(self.name, self.model)

        questions = {query.id: build_question(query) for query in queries}
        started = time.perf_counter()
        try:
            # The SDK already retries 408/429/5xx and connection errors with backoff.
            response = self._client.system_one(
                state=source_text, questions=questions, model=self._model
            )
        except TypeSafeAPIError as exc:
            retryable = exc.status in _RETRYABLE_STATUS
            # Status only: an error body can echo the request back.
            logger.warning(
                "typesafe request failed", extra={"status": exc.status, "retryable": retryable}
            )
            raise DecisionProviderError(
                f"TypeSafe API error (status {exc.status})", retryable=retryable
            ) from exc
        except TypeSafeError as exc:
            logger.warning("typesafe request failed", extra={"error_type": type(exc).__name__})
            raise DecisionProviderError(
                f"TypeSafe request failed: {type(exc).__name__}", retryable=True
            ) from exc
        latency_ms = (time.perf_counter() - started) * 1000

        decisions = {
            query.id: self._to_decision(query, response.answers.get(query.id), response.model)
            for query in queries
        }
        return DecisionBatch(
            decisions=decisions,
            provider=self.name,
            model=response.model,
            latency_ms=round(latency_ms, 1),
            input_tokens=response.usage.input_tokens or 0,
            output_tokens=response.usage.output_tokens or 0,
        )

    def _to_decision(self, query: DecisionQuery, answer: object, model: str) -> Decision:
        spec = TASKS[query.task]
        if spec.kind is TaskKind.BINARY and isinstance(answer, NoulAnswer):
            yes = min(1.0, max(0.0, answer.noul))
            probabilities = {YES: yes, NO: round(1 - yes, 6)}
            label = YES if yes >= _YES_NO_MIDPOINT else NO
            # A Noul has no separate confidence; distance from 0.5 is the same idea.
            confidence = round(abs(2 * yes - 1), 4)
        elif spec.kind is TaskKind.CHOICE and isinstance(answer, ChoiceAnswer):
            if answer.choice not in spec.labels:
                raise DecisionProviderError(f"TypeSafe returned an unknown label for {query.id}")
            label = answer.choice
            probabilities = dict(answer.probabilities)
            confidence = answer.confidence
        else:
            raise DecisionProviderError(f"TypeSafe answer for {query.id} is missing or mistyped")

        return Decision(
            query_id=query.id,
            task=query.task,
            label=label,
            probabilities=probabilities,
            confidence=confidence,
            provider=self.name,
            model=model,
            task_version=spec.version,
        )
