import json
import logging
from typing import Any

import pytest

from clinical_extraction import (
    ClinicalCaseExtractor,
    ContentBlockedError,
    ProviderError,
    SchemaValidationError,
)
from clinical_extraction.prompt import PROMPT_VERSION, SYSTEM_INSTRUCTION
from clinical_extraction.providers.fake import FAKE_MODEL, FakeProvider
from clinical_extraction.schema import ClinicalCaseExtraction
from clinical_extraction.scoring_policy import DIFFERENTIAL_WEIGHT, ESTABLISHED_DIAGNOSIS_WEIGHT

RAW_TEXT = "A 24-year-old man with right lower quadrant pain. Diagnosis: acute appendicitis."


def test_extract_returns_validated_case(valid_extraction: dict[str, Any]) -> None:
    provider = FakeProvider.returning(valid_extraction)

    result = ClinicalCaseExtractor(provider).extract(RAW_TEXT)

    assert result.case.title == valid_extraction["title"]
    assert result.case.patient_age == 24
    assert [f.category for f in result.case.findings] == ["symptom", "laboratory"]
    assert (result.model, result.attempts) == (FAKE_MODEL, 1)
    assert RAW_TEXT in provider.calls[0]


def test_payload_carries_provenance_for_the_backend(valid_extraction: dict[str, Any]) -> None:
    result = ClinicalCaseExtractor(FakeProvider.returning(valid_extraction)).extract(RAW_TEXT)

    payload = result.to_case_create_payload()

    assert payload["provenance"] == {
        "source": "llm_extraction",
        "model": FAKE_MODEL,
        "prompt_version": PROMPT_VERSION,
    }
    assert payload["findings"] == valid_extraction["findings"]


def test_prompt_forbids_the_model_from_diagnosing() -> None:
    assert "You do NOT diagnose" in SYSTEM_INSTRUCTION
    assert "Never infer" in SYSTEM_INSTRUCTION


def test_non_json_output_raises_schema_error() -> None:
    provider = FakeProvider(default="Here is the case: {oops")

    with pytest.raises(SchemaValidationError, match="non-JSON"):
        ClinicalCaseExtractor(provider).extract(RAW_TEXT)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"patient_age": 400}, "age out of range"),
        ({"findings": []}, "no findings"),
        ({"title": ""}, "blank title"),
        ({"hallucinated_field": "x"}, "unknown field"),
        (
            {"answers": [{"text": "Appendicitis", "is_correct": False}]},
            "no established diagnosis",
        ),
        ({"findings": [{"category": "vibes", "value": "x"}]}, "category outside the enum"),
    ],
)
def test_invalid_output_raises_without_fallback(
    valid_extraction: dict[str, Any], mutation: dict[str, Any], reason: str
) -> None:
    provider = FakeProvider.returning({**valid_extraction, **mutation})

    with pytest.raises(SchemaValidationError) as exc_info:
        ClinicalCaseExtractor(provider).extract(RAW_TEXT)

    assert exc_info.value.raw_response is not None, reason


def test_schema_violations_are_not_retried(valid_extraction: dict[str, Any]) -> None:
    provider = FakeProvider.returning({**valid_extraction, "patient_age": 400})

    with pytest.raises(SchemaValidationError):
        ClinicalCaseExtractor(provider, max_attempts=3).extract(RAW_TEXT)

    assert len(provider.calls) == 1


def test_transient_provider_errors_are_retried(valid_extraction: dict[str, Any]) -> None:
    def fail_twice(call_number: int) -> None:
        if call_number < 3:
            raise ProviderError("503 upstream", retryable=True)

    provider = FakeProvider(default=json.dumps(valid_extraction), on_call=fail_twice)

    result = ClinicalCaseExtractor(provider, max_attempts=3).extract(RAW_TEXT)

    assert result.attempts == 3
    assert len(provider.calls) == 3


def test_retries_are_bounded(valid_extraction: dict[str, Any]) -> None:
    def always_fail(_: int) -> None:
        raise ProviderError("503 upstream", retryable=True)

    provider = FakeProvider(default=json.dumps(valid_extraction), on_call=always_fail)

    with pytest.raises(ProviderError):
        ClinicalCaseExtractor(provider, max_attempts=2).extract(RAW_TEXT)

    assert len(provider.calls) == 2


def test_non_retryable_provider_error_fails_immediately(valid_extraction: dict[str, Any]) -> None:
    def fail(_: int) -> None:
        raise ProviderError("safety block", retryable=False)

    provider = FakeProvider(default=json.dumps(valid_extraction), on_call=fail)

    with pytest.raises(ProviderError, match="safety block"):
        ClinicalCaseExtractor(provider, max_attempts=3).extract(RAW_TEXT)

    assert len(provider.calls) == 1


@pytest.mark.parametrize("raw_text", ["", "   \n ", "x" * 20_001])
def test_input_guards(valid_extraction: dict[str, Any], raw_text: str) -> None:
    provider = FakeProvider.returning(valid_extraction)

    with pytest.raises(ValueError, match="raw_text"):
        ClinicalCaseExtractor(provider).extract(raw_text)

    assert provider.calls == []


def test_validation_failures_do_not_log_clinical_values(
    valid_extraction: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    """Pydantic embeds offending input values in its message; they must not be logged."""
    marker = "UNIQUE-PATIENT-NARRATIVE-TOKEN"
    provider = FakeProvider.returning(
        {**valid_extraction, "presentation": marker, "patient_age": 400}
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(SchemaValidationError):
        ClinicalCaseExtractor(provider).extract(RAW_TEXT)

    assert marker not in caplog.text
    assert "400" not in caplog.text
    record = next(r for r in caplog.records if r.message == "extraction failed schema validation")
    assert record.exc_info is None
    assert record.__dict__["fields"] == ["patient_age"]


def test_the_model_is_never_asked_to_score_a_diagnosis() -> None:
    """Weighting a differential 'by clinical proximity' is an invented number."""
    assert "score_weight" not in SYSTEM_INSTRUCTION
    assert "do not score them" in SYSTEM_INSTRUCTION
    assert "score_weight" not in str(ClinicalCaseExtraction.model_json_schema())


def test_weights_are_applied_by_policy_not_by_the_model(
    valid_extraction: dict[str, Any],
) -> None:
    result = ClinicalCaseExtractor(FakeProvider.returning(valid_extraction)).extract(RAW_TEXT)

    payload = result.to_case_create_payload()
    answers = payload["answers"]
    assert isinstance(answers, list)
    by_text = {a["text"]: a["score_weight"] for a in answers}
    assert by_text["Acute appendicitis"] == ESTABLISHED_DIAGNOSIS_WEIGHT
    assert by_text["Mesenteric lymphadenitis"] == DIFFERENTIAL_WEIGHT


def test_a_blocked_response_is_not_a_transport_failure() -> None:
    """Content filtering is the model declining, not the provider being down."""
    error = ContentBlockedError("blocked", feedback="SAFETY")

    assert isinstance(error, ProviderError)
    assert error.retryable is False
    assert error.feedback == "SAFETY"
