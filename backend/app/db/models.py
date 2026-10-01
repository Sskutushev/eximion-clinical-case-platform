"""Database models. Internal only: never serialized to a client."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ClinicalCase(Base):
    __tablename__ = "clinical_cases"
    __table_args__ = (
        CheckConstraint("patient_age BETWEEN 0 AND 130", name="patient_age_range"),
        CheckConstraint("patient_sex IN ('female', 'male', 'other')", name="patient_sex_allowed"),
        CheckConstraint("char_length(title) > 0", name="title_not_empty"),
        CheckConstraint("char_length(presentation) > 0", name="presentation_not_empty"),
        Index("ix_clinical_cases_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(200))
    patient_age: Mapped[int | None] = mapped_column(SmallInteger)
    patient_sex: Mapped[str | None] = mapped_column(String(16))
    presentation: Mapped[str] = mapped_column(Text)
    # Optional: LLM model + prompt version when the case came from extraction.
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    findings: Mapped[list["CaseFinding"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseFinding.position",
        lazy="raise",
    )
    answers: Mapped[list["CaseAnswer"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="CaseAnswer.position",
        lazy="raise",
    )


class CaseFinding(Base):
    __tablename__ = "case_findings"
    __table_args__ = (
        UniqueConstraint("case_id", "position"),
        CheckConstraint(
            "category IN ('history', 'symptom', 'vital_sign', 'physical_exam', "
            "'laboratory', 'imaging', 'other')",
            name="category_allowed",
        ),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger)

    case: Mapped[ClinicalCase] = relationship(back_populates="findings")


class CaseAnswer(Base):
    """Answer key. A case may accept synonyms and give partial credit."""

    __tablename__ = "case_answers"
    __table_args__ = (
        UniqueConstraint("case_id", "position"),
        UniqueConstraint("case_id", "normalized_answer"),
        CheckConstraint("score_weight BETWEEN 0 AND 100", name="score_weight_range"),
        CheckConstraint("char_length(normalized_answer) > 0", name="normalized_not_empty"),
        CheckConstraint("position >= 0", name="position_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clinical_cases.id", ondelete="CASCADE"), index=True
    )
    answer_text: Mapped[str] = mapped_column(String(300))
    normalized_answer: Mapped[str] = mapped_column(String(300))
    is_correct: Mapped[bool] = mapped_column(Boolean)
    score_weight: Mapped[int] = mapped_column(SmallInteger)
    position: Mapped[int] = mapped_column(SmallInteger)

    case: Mapped[ClinicalCase] = relationship(back_populates="answers")


class CaseSubmission(Base):
    """A scored attempt. Append-only: this is the competition audit trail."""

    __tablename__ = "case_submissions"
    __table_args__ = (
        CheckConstraint("max_score >= 0", name="max_score_non_negative"),
        CheckConstraint("score BETWEEN 0 AND max_score", name="score_within_max"),
        Index("ix_case_submissions_case_id_created_at", "case_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )
    # RESTRICT: never drop a case out from under its attempts.
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clinical_cases.id", ondelete="RESTRICT"))
    matched_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("case_answers.id", ondelete="SET NULL"), index=True
    )
    submitted_answer: Mapped[str] = mapped_column(String(300))
    normalized_answer: Mapped[str] = mapped_column(String(300))
    score: Mapped[int] = mapped_column(SmallInteger)
    max_score: Mapped[int] = mapped_column(SmallInteger)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
