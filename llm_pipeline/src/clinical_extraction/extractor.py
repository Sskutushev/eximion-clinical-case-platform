"""raw clinical text -> validated ClinicalCaseExtraction."""

import json
import logging
from dataclasses import dataclass

from pydantic import ValidationError
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from clinical_extraction.errors import ProviderError, SchemaValidationError
from clinical_extraction.prompt import PROMPT_VERSION, SYSTEM_INSTRUCTION, build_user_prompt
from clinical_extraction.providers.base import ExtractionProvider
from clinical_extraction.schema import ClinicalCaseExtraction

logger = logging.getLogger(__name__)

MAX_INPUT_CHARS = 20_000


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    case: ClinicalCaseExtraction
    model: str
    prompt_version: str
    attempts: int
    usage: dict[str, int] | None

    def to_case_create_payload(self) -> dict[str, object]:
        return self.case.to_case_create_payload(
            model=self.model, prompt_version=self.prompt_version
        )


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, ProviderError) and exc.retryable


def _log_retry(state: RetryCallState) -> None:
    logger.warning(
        "retrying extraction after transient provider error",
        extra={"attempt": state.attempt_number},
    )


class ClinicalCaseExtractor:
    def __init__(self, provider: ExtractionProvider, *, max_attempts: int = 3) -> None:
        self._provider = provider
        self._max_attempts = max_attempts
        self._json_schema = ClinicalCaseExtraction.model_json_schema()

    def extract(self, raw_text: str) -> ExtractionResult:
        """Extract a structured case.

        Raises:
            ValueError: the input is empty or too long.
            ProviderError: the provider failed (after bounded retries for transient errors).
            SchemaValidationError: the model output did not satisfy the contract.
        """
        text = raw_text.strip()
        if not text:
            raise ValueError("raw_text must not be empty")
        if len(text) > MAX_INPUT_CHARS:
            raise ValueError(f"raw_text exceeds {MAX_INPUT_CHARS} characters")

        user_prompt = build_user_prompt(text)
        attempts = 0
        # Retries cover transport/quota only; a schema violation is never retried.
        retrying = Retrying(
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(multiplier=0.5, max=8),
            retry=retry_if_exception(_is_retryable),
            before_sleep=_log_retry,
            reraise=True,
        )

        for attempt in retrying:
            with attempt:
                attempts += 1
                response = self._provider.generate_structured(
                    system_instruction=SYSTEM_INSTRUCTION,
                    user_prompt=user_prompt,
                    json_schema=self._json_schema,
                )

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise SchemaValidationError(
                f"provider returned non-JSON output: {exc.msg}", raw_response=response.text
            ) from exc

        try:
            case = ClinicalCaseExtraction.model_validate(payload)
        except ValidationError as exc:
            # Field paths and rules only; the clinical values stay out of the log.
            logger.exception(
                "extraction failed schema validation",
                extra={
                    "error_count": exc.error_count(),
                    "fields": [".".join(map(str, e["loc"])) for e in exc.errors()],
                },
            )
            raise SchemaValidationError(
                f"extraction does not satisfy the contract: {exc.error_count()} error(s)",
                raw_response=response.text,
            ) from exc

        logger.info(
            "extraction succeeded",
            extra={
                "model": response.model,
                "prompt_version": PROMPT_VERSION,
                "attempts": attempts,
                "findings": len(case.findings),
                "answers": len(case.answers),
            },
        )
        return ExtractionResult(
            case=case,
            model=response.model,
            prompt_version=PROMPT_VERSION,
            attempts=attempts,
            usage=response.usage,
        )
