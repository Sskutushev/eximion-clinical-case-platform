import logging
import time

from clinical_extraction.errors import ContentBlockedError, ExtractionError, ProviderError
from clinical_extraction.evals.dataset import EvalExample
from clinical_extraction.evals.metrics import (
    CaseReport,
    CaseStatus,
    EvalSummary,
    evaluate_case,
    summarize,
)
from clinical_extraction.extractor import ClinicalCaseExtractor
from clinical_extraction.prompt import PROMPT_VERSION
from clinical_extraction.providers.base import ExtractionProvider

logger = logging.getLogger(__name__)


def run_eval(
    provider: ExtractionProvider,
    examples: list[EvalExample],
    *,
    provider_name: str,
    delay_seconds: float = 0.0,
    max_attempts: int = 3,
) -> EvalSummary:
    """Extract every case in the dataset and score it against ground truth.

    Failures are recorded, not swallowed: a case that cannot be extracted counts
    against schema_valid_rate.

    `delay_seconds` paces the requests. Free Gemini tiers allow a handful of
    requests per minute, and without pacing the back half of a run is just 429s
    — which would show up as an extraction failure rather than a quota one.
    """
    extractor = ClinicalCaseExtractor(provider, max_attempts=max_attempts)
    reports: list[CaseReport] = []

    for index, example in enumerate(examples):
        if delay_seconds > 0 and index > 0:
            time.sleep(delay_seconds)
        try:
            result = extractor.extract(example.raw_text)
        except (ExtractionError, ValueError) as exc:
            logger.warning(
                "extraction failed during eval",
                extra={"example_id": example.id, "error_type": type(exc).__name__},
            )
            if isinstance(exc, ContentBlockedError):
                status = CaseStatus.MODEL_BLOCKED
            elif isinstance(exc, ProviderError):
                status = CaseStatus.PROVIDER_ERROR
            else:
                status = CaseStatus.SCHEMA_INVALID
            reports.append(
                CaseReport(
                    example_id=example.id,
                    status=status,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        reports.append(evaluate_case(example.expected, result.case, example.id))

    return summarize(
        reports, provider=provider_name, model=provider.model, prompt_version=PROMPT_VERSION
    )
