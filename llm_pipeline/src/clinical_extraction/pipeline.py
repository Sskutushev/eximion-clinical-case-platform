"""Extraction, then optional verification.

`ClinicalCaseExtractor` is unchanged and still usable on its own. This only
adds a second, separate step after it.
"""

from dataclasses import dataclass
from typing import Any

from clinical_extraction.decisioning.verifier import CaseVerifier, VerificationReport
from clinical_extraction.extractor import ClinicalCaseExtractor, ExtractionResult


@dataclass(frozen=True, slots=True)
class PipelineResult:
    extraction: ExtractionResult
    verification: VerificationReport | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.extraction.to_case_create_payload(),
            # Accept means the automatic checks passed. It is not a licence to
            # publish: a person still approves every LLM-extracted case.
            "verification": self.verification.to_dict() if self.verification else None,
        }


class ClinicalExtractionPipeline:
    def __init__(
        self, extractor: ClinicalCaseExtractor, verifier: CaseVerifier | None = None
    ) -> None:
        self._extractor = extractor
        self._verifier = verifier

    def run(self, raw_text: str) -> PipelineResult:
        extraction = self._extractor.extract(raw_text)
        verification = self._verifier.verify(raw_text, extraction.case) if self._verifier else None
        return PipelineResult(extraction=extraction, verification=verification)
