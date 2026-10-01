"""Gemini provider behaviour, exercised against a stubbed SDK client (no network)."""

from dataclasses import dataclass
from typing import Any

import pytest
from google.genai import errors as genai_errors
from pydantic import SecretStr, ValidationError

from clinical_extraction.config import ExtractionSettings
from clinical_extraction.errors import ProviderError
from clinical_extraction.providers.gemini import GeminiProvider


@dataclass
class _Usage:
    prompt_token_count: int | None
    candidates_token_count: int | None


@dataclass
class _Response:
    text: str | None
    usage_metadata: _Usage | None = None
    prompt_feedback: str | None = None


class _Models:
    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.config: Any = None

    def generate_content(self, *, model: str, contents: str, config: Any) -> Any:
        del model, contents
        self.config = config
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome


class _Client:
    def __init__(self, outcome: Any) -> None:
        self.models = _Models(outcome)


def _settings(**overrides: Any) -> ExtractionSettings:
    return ExtractionSettings(google_cloud_project="demo-project", gemini_api_key=None, **overrides)


def _provider(outcome: Any, **overrides: Any) -> tuple[GeminiProvider, _Client]:
    client = _Client(outcome)
    return GeminiProvider(_settings(**overrides), client=client), client  # type: ignore[arg-type]


def test_structured_output_is_requested_deterministically() -> None:
    provider, client = _provider(_Response(text='{"ok": true}', usage_metadata=_Usage(120, 45)))

    response = provider.generate_structured(
        system_instruction="sys", user_prompt="prompt", json_schema={"type": "object"}
    )

    config = client.models.config
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == {"type": "object"}
    assert config.temperature == 0.0
    assert config.system_instruction == "sys"
    assert response.text == '{"ok": true}'
    assert response.usage == {"prompt_tokens": 120, "output_tokens": 45}


@pytest.mark.parametrize(
    ("status", "expected_retryable"),
    [(429, True), (503, True), (400, False), (403, False)],
)
def test_api_errors_are_classified_by_status(status: int, *, expected_retryable: bool) -> None:
    error = genai_errors.APIError(status, {"message": "upstream failure"})
    provider, _ = _provider(error)

    with pytest.raises(ProviderError) as exc_info:
        provider.generate_structured(system_instruction="sys", user_prompt="prompt", json_schema={})

    assert exc_info.value.retryable is expected_retryable
    assert str(status) in str(exc_info.value)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_empty_response_is_not_retried(text: str | None) -> None:
    provider, _ = _provider(_Response(text=text, prompt_feedback="BLOCKED"))

    with pytest.raises(ProviderError) as exc_info:
        provider.generate_structured(system_instruction="sys", user_prompt="prompt", json_schema={})

    assert exc_info.value.retryable is False
    assert "empty response" in str(exc_info.value)


def test_model_name_is_reported_for_provenance() -> None:
    provider, _ = _provider(_Response(text="{}"), gemini_model="gemini-2.5-pro")

    assert provider.model == "gemini-2.5-pro"


def test_settings_require_credentials() -> None:
    with pytest.raises(ValidationError, match="GOOGLE_CLOUD_PROJECT"):
        ExtractionSettings(google_cloud_project=None, gemini_api_key=None)


def test_vertex_is_preferred_over_api_key() -> None:
    both = ExtractionSettings(google_cloud_project="demo-project", gemini_api_key=SecretStr("key"))
    key_only = ExtractionSettings(google_cloud_project=None, gemini_api_key=SecretStr("key"))

    assert both.use_vertex is True
    assert key_only.use_vertex is False
