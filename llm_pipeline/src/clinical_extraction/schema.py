"""Extraction contract.

Mirrors the backend's `ClinicalCaseCreate` so an extraction result can be POSTed
to /api/v1/cases unchanged. `tests/test_contract_alignment.py` enforces that.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
AnswerText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
FindingText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)
]


class FindingCategory(StrEnum):
    HISTORY = "history"
    SYMPTOM = "symptom"
    VITAL_SIGN = "vital_sign"
    PHYSICAL_EXAM = "physical_exam"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    OTHER = "other"


class PatientSex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


class FindingExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FindingCategory = Field(description="Clinical category of this finding.")
    value: FindingText = Field(description="The finding, quoted or closely paraphrased.")


class AnswerExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: AnswerText = Field(description="A diagnosis named in the source text.")
    is_correct: bool = Field(
        description="True only when the source states this is the established diagnosis."
    )
    score_weight: int = Field(ge=0, le=100, description="10 for correct, 0-5 for differentials.")


class ClinicalCaseExtraction(BaseModel):
    """Structured case extracted from free clinical text."""

    model_config = ConfigDict(extra="forbid")

    title: ShortText = Field(description="Short descriptive title of the presenting problem.")
    patient_age: int | None = Field(
        default=None, ge=0, le=130, description="Age in years, or null when not stated."
    )
    patient_sex: PatientSex | None = Field(
        default=None, description="Patient sex, or null when not stated."
    )
    presentation: LongText = Field(description="Summary of the presenting complaint and course.")
    findings: list[FindingExtraction] = Field(min_length=1, max_length=50)
    answers: list[AnswerExtraction] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _validate_answer_key(self) -> Self:
        correct = [a.score_weight for a in self.answers if a.is_correct]
        if not any(w > 0 for w in correct):
            raise ValueError("exactly one established diagnosis with score_weight > 0 is required")
        if any(not a.is_correct and a.score_weight > max(correct) for a in self.answers):
            raise ValueError("differentials cannot outweigh the established diagnosis")
        if len({a.text.strip().casefold() for a in self.answers}) != len(self.answers):
            raise ValueError("answers must be unique")
        return self

    def to_case_create_payload(self, *, model: str, prompt_version: str) -> dict[str, object]:
        """Payload for POST /api/v1/cases, tagged with extraction provenance."""
        return {
            **self.model_dump(mode="json"),
            "provenance": {
                "source": "llm_extraction",
                "model": model,
                "prompt_version": prompt_version,
            },
        }
