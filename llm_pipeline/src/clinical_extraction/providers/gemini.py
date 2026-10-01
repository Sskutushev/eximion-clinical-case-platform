"""Gemini provider: native structured output via `response_json_schema`.

No regex or markdown parsing — the model is constrained to the schema and the
result is validated with Pydantic by the caller.
"""

import logging
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from clinical_extraction.config import ExtractionSettings
from clinical_extraction.errors import ContentBlockedError, ProviderError
from clinical_extraction.providers.base import ProviderResponse

logger = logging.getLogger(__name__)

# Transport/quota failures worth one bounded retry; 4xx misuse is not retried.
_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class GeminiProvider:
    """Vertex AI (ADC) when GOOGLE_CLOUD_PROJECT is set, otherwise the Gemini API key."""

    def __init__(self, settings: ExtractionSettings, client: genai.Client | None = None) -> None:
        self._settings = settings
        self._client = client or self._build_client(settings)

    @staticmethod
    def _build_client(settings: ExtractionSettings) -> genai.Client:
        http_options = types.HttpOptions(timeout=settings.request_timeout_seconds * 1000)
        if settings.use_vertex:
            return genai.Client(
                vertexai=True,
                project=settings.google_cloud_project,
                location=settings.google_cloud_location,
                http_options=http_options,
            )
        api_key = settings.gemini_api_key
        if api_key is None:  # pragma: no cover - guarded by settings validation
            raise ProviderError("No Gemini credentials configured")
        return genai.Client(api_key=api_key.get_secret_value(), http_options=http_options)

    @property
    def model(self) -> str:
        return self._settings.gemini_model

    def generate_structured(
        self, *, system_instruction: str, user_prompt: str, json_schema: dict[str, Any]
    ) -> ProviderResponse:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_json_schema=json_schema,
            temperature=self._settings.temperature,
            max_output_tokens=self._settings.max_output_tokens,
        )
        try:
            response = self._client.models.generate_content(
                model=self.model, contents=user_prompt, config=config
            )
        except genai_errors.APIError as exc:
            retryable = exc.code in _RETRYABLE_STATUS
            # Log the status only: the message may echo the clinical prompt back.
            logger.warning(
                "gemini request failed", extra={"status": exc.code, "retryable": retryable}
            )
            raise ProviderError(
                f"Gemini API error (status {exc.code})", retryable=retryable
            ) from exc
        except genai_errors.ClientError as exc:  # pragma: no cover - transport level
            raise ProviderError("Gemini transport error", retryable=True) from exc

        text = response.text
        if not text or not text.strip():
            feedback = getattr(response, "prompt_feedback", None)
            raise ContentBlockedError(
                "Gemini returned an empty response", feedback=str(feedback) if feedback else None
            )

        usage = None
        if (meta := response.usage_metadata) is not None:
            usage = {
                "prompt_tokens": meta.prompt_token_count or 0,
                "output_tokens": meta.candidates_token_count or 0,
            }
        return ProviderResponse(text=text, model=self.model, usage=usage)
