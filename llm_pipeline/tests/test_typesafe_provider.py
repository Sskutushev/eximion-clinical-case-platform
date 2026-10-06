"""The Jev adapter against the real SDK, with the HTTP layer mocked."""

import json
import logging
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from typesafe_sdk import Choice, RetryPolicy, TypeSafeClient

from clinical_extraction.config import DecisionSettings
from clinical_extraction.decisioning.providers.typesafe import (
    TypeSafeDecisionProvider,
    build_question,
)
from clinical_extraction.decisioning.schema import DecisionQuery
from clinical_extraction.decisioning.tasks import NO, YES, DecisionTask
from clinical_extraction.errors import DecisionProviderError

SOURCE = "A 41-year-old woman with sudden pleuritic chest pain after a long flight."

QUERIES = [
    DecisionQuery(
        id="findings.0.category",
        task=DecisionTask.FINDING_CATEGORY,
        target="findings[0]",
        subject="Heart rate 118/min",
        index=0,
    ),
    DecisionQuery(
        id="title.leak",
        task=DecisionTask.DIAGNOSIS_LEAK,
        target="title",
        subject="Sudden pleuritic chest pain",
        reference=("Pulmonary embolism",),
    ),
]

GOOD_ANSWERS = {
    "findings.0.category": {
        "type": "choice",
        "choice": "vital_sign",
        "confidence": 0.91,
        "probabilities": {"vital_sign": 0.93, "laboratory": 0.05, "other": 0.02},
    },
    "title.leak": {"type": "noul", "noul": 0.12},
}


def _settings(**overrides: Any) -> DecisionSettings:
    # Ignore any local .env: these tests must not depend on a developer's keys.
    return DecisionSettings(_env_file=None, typesafe_api_key="test-key", **overrides)


def _provider(
    handler: Callable[[httpx2.Request], httpx2.Response],
) -> TypeSafeDecisionProvider:
    client = TypeSafeClient(
        api_key="test-key",
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=0),
    )
    return TypeSafeDecisionProvider(_settings(), client=client)


def _respond(answers: dict[str, Any], status: int = 200) -> httpx2.Response:
    body = {
        "model": "jev-1.13.0",
        "answers": answers,
        "usage": {"input_tokens": 412, "output_tokens": 9},
    }
    return httpx2.Response(status, json=body)


def test_all_questions_go_in_one_request_with_the_source_as_state() -> None:
    requests: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(json.loads(request.content))
        return _respond(GOOD_ANSWERS)

    _provider(handler).decide(SOURCE, QUERIES)

    [body] = requests
    assert body["state"] == SOURCE
    assert body["model"] == "jev-latest"
    category = body["questions"]["findings.0.category"]
    assert category["type"] == "choice"
    assert set(category["criteria"]) == {
        "history",
        "symptom",
        "vital_sign",
        "physical_exam",
        "laboratory",
        "imaging",
        "other",
    }
    assert category["instructions"]["finding"] == "Heart rate 118/min"
    leak = body["questions"]["title.leak"]
    assert leak["type"] == "noul"
    assert leak["instructions"]["diagnoses"] == ["Pulmonary embolism"]


def test_answers_become_typed_decisions() -> None:
    batch = _provider(lambda _: _respond(GOOD_ANSWERS)).decide(SOURCE, QUERIES)

    category = batch.decisions["findings.0.category"]
    assert (category.label, category.confidence) == ("vital_sign", 0.91)
    assert category.model == "jev-1.13.0"
    assert category.task_version == "finding-category-v1"

    leak = batch.decisions["title.leak"]
    assert leak.label == NO
    assert leak.probabilities[YES] == pytest.approx(0.12)
    assert leak.confidence == pytest.approx(0.76)

    assert (batch.input_tokens, batch.output_tokens, batch.calls) == (412, 9, 1)


def test_an_unknown_label_is_rejected_not_passed_on() -> None:
    answers = {**GOOD_ANSWERS, "findings.0.category": {**GOOD_ANSWERS["findings.0.category"]}}
    answers["findings.0.category"]["choice"] = "radiology"

    with pytest.raises(DecisionProviderError, match="unknown label"):
        _provider(lambda _: _respond(answers)).decide(SOURCE, QUERIES)


def test_a_missing_answer_is_an_error() -> None:
    answers = {"title.leak": GOOD_ANSWERS["title.leak"]}

    with pytest.raises(DecisionProviderError, match="missing"):
        _provider(lambda _: _respond(answers)).decide(SOURCE, QUERIES)


@pytest.mark.parametrize(("status", "retryable"), [(401, False), (422, False), (503, True)])
def test_api_errors_are_typed(status: int, retryable: bool) -> None:  # noqa: FBT001
    provider = _provider(lambda _: httpx2.Response(status, json={"detail": SOURCE}))

    with pytest.raises(DecisionProviderError) as raised:
        provider.decide(SOURCE, QUERIES)

    assert raised.value.retryable is retryable
    assert SOURCE not in str(raised.value)


def test_a_connection_failure_is_typed() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    with pytest.raises(DecisionProviderError, match="request failed"):
        _provider(handler).decide(SOURCE, QUERIES)


def test_no_key_means_no_provider() -> None:
    with pytest.raises(DecisionProviderError, match="TYPESAFE_API_KEY"):
        TypeSafeDecisionProvider(DecisionSettings(_env_file=None, typesafe_api_key=None))


def test_an_empty_question_list_makes_no_request() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no request expected")

    batch = _provider(handler).decide(SOURCE, [])

    assert batch.calls == 0


def test_clinical_text_stays_out_of_the_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        _provider(lambda _: _respond(GOOD_ANSWERS)).decide(SOURCE, QUERIES)
        with pytest.raises(DecisionProviderError):
            _provider(lambda _: httpx2.Response(500, json={"detail": SOURCE})).decide(
                SOURCE, QUERIES
            )

    assert SOURCE not in caplog.text
    assert "Heart rate 118/min" not in caplog.text


def test_the_completeness_question_carries_the_extracted_list() -> None:
    query = DecisionQuery(
        id="findings.completeness",
        task=DecisionTask.FINDING_COMPLETENESS,
        target="findings",
        subject="",
        reference=("Heart rate 118/min", "Oxygen saturation 91% on room air"),
    )

    built = build_question(query)
    assert isinstance(built, Choice)
    question = built.model_dump()

    assert question["type"] == "choice"
    assert question["instructions"]["extracted_findings"] == list(query.reference)
    assert set(question["criteria"]) == {"complete", "likely_incomplete"}


def test_a_gateway_base_url_is_used_when_configured() -> None:
    """Vercel AI Gateway serves the same System One endpoint under its own host."""
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(str(request.url))
        return _respond(GOOD_ANSWERS)

    settings = _settings(
        typesafe_base_url="https://gateway.example/typesafe", jev_model="typesafe-ai/jev"
    )
    client = TypeSafeClient(
        api_key="test-key",
        base_url=settings.typesafe_base_url,
        transport=httpx2.MockTransport(handler),
        retry=RetryPolicy(max_retries=0),
    )
    batch = TypeSafeDecisionProvider(settings, client=client).decide(SOURCE, QUERIES)

    assert seen == ["https://gateway.example/typesafe/v1/systemone"]
    assert batch.model == "jev-1.13.0"


def test_the_provider_builds_its_client_from_settings() -> None:
    provider = TypeSafeDecisionProvider(
        _settings(typesafe_base_url="https://gateway.example/typesafe")
    )

    assert provider.model == "jev-latest"
