import logging

from clinical_extraction.errors import ExtractionError
from clinical_extraction.evals.dataset import EvalExample
from clinical_extraction.evals.metrics import CaseReport, EvalSummary, evaluate_case, summarize
from clinical_extraction.extractor import ClinicalCaseExtractor
from clinical_extraction.prompt import PROMPT_VERSION
from clinical_extraction.providers.base import ExtractionProvider

logger = logging.getLogger(__name__)


def run_eval(
    provider: ExtractionProvider, examples: list[EvalExample], *, provider_name: str
) -> EvalSummary:
    """Extract every case in the dataset and score it against ground truth.

    Failures are recorded, not swallowed: a case that cannot be extracted counts
    against schema_valid_rate.
    """
    extractor = ClinicalCaseExtractor(provider)
    reports: list[CaseReport] = []

    for example in examples:
        try:
            result = extractor.extract(example.raw_text)
        except (ExtractionError, ValueError) as exc:
            logger.warning(
                "extraction failed during eval",
                extra={"example_id": example.id, "error_type": type(exc).__name__},
            )
            reports.append(
                CaseReport(
                    example_id=example.id,
                    schema_valid=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        reports.append(evaluate_case(example.expected, result.case, example.id))

    return summarize(
        reports, provider=provider_name, model=provider.model, prompt_version=PROMPT_VERSION
    )
