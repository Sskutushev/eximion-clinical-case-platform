"""API contract. These models are the OpenAPI source of truth for the frontend and LLM pipeline.

Input models forbid unknown fields; public output models contain no answer-key fields.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.enums import FindingCategory, PatientSex, ScoreOutcome
from app.domain.scoring import normalize_answer

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
AnswerText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)]
FindingText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1_000)
]
PatientAge = Annotated[int, Field(ge=0, le=130)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Inputs -----------------------------------------------------------------


class FindingIn(_Input):
    category: FindingCategory
    value: FindingText


class AnswerIn(_Input):
    text: AnswerText
    is_correct: bool
    score_weight: int = Field(ge=0, le=100, description="Points awarded when matched.")


class Provenance(_Input):
    source: Literal["manual", "llm_extraction"]
    model: ShortText | None = None
    prompt_version: ShortText | None = None


class ClinicalCaseCreate(_Input):
    title: ShortText
    patient_age: PatientAge | None = None
    patient_sex: PatientSex | None = None
    presentation: LongText
    findings: list[FindingIn] = Field(min_length=1, max_length=50)
    answers: list[AnswerIn] = Field(
        min_length=1,
        max_length=20,
        description="Answer key. Stored server-side only; never returned by public endpoints.",
    )
    provenance: Provenance | None = None

    @model_validator(mode="after")
    def _validate_answer_key(self) -> Self:
        correct_weights = [a.score_weight for a in self.answers if a.is_correct]
        if not any(w > 0 for w in correct_weights):
            raise ValueError("answer key needs at least one correct answer with score_weight > 0")
        if any(not a.is_correct and a.score_weight > max(correct_weights) for a in self.answers):
            raise ValueError("partial-credit answers cannot outweigh the correct answer")

        normalized = [normalize_answer(a.text) for a in self.answers]
        if not all(normalized):
            raise ValueError("answers must contain more than punctuation")
        if len(set(normalized)) != len(normalized):
            raise ValueError("answers must be unique after normalization")
        return self


class ScoreRequest(_Input):
    answer: AnswerText

    @model_validator(mode="after")
    def _not_blank_after_normalization(self) -> Self:
        if not normalize_answer(self.answer):
            raise ValueError("answer must contain more than punctuation")
        return self


# --- Outputs ----------------------------------------------------------------


class CaseCreated(BaseModel):
    id: uuid.UUID


class PublicFinding(BaseModel):
    category: FindingCategory
    value: str


class PublicClinicalCase(BaseModel):
    """What a participant sees. Deliberately has NO answer / correctness / weight fields."""

    id: uuid.UUID
    title: str
    patient_age: int | None
    patient_sex: PatientSex | None
    presentation: str
    findings: list[PublicFinding]
    created_at: datetime


class CaseSummary(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime


class CaseList(BaseModel):
    items: list[CaseSummary]
    limit: int
    offset: int


class ScoreResponse(BaseModel):
    submission_id: uuid.UUID
    score: int
    max_score: int
    is_correct: bool
    outcome: ScoreOutcome
    feedback: str


class ErrorResponse(BaseModel):
    detail: str
