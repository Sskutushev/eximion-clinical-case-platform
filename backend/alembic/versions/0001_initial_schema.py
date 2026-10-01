"""initial schema: cases, findings, answer key, submissions

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clinical_cases",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("patient_age", sa.SmallInteger(), nullable=True),
        sa.Column("patient_sex", sa.String(16), nullable=True),
        sa.Column("presentation", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("patient_age BETWEEN 0 AND 130", name="ck_clinical_cases_patient_age_range"),
        sa.CheckConstraint(
            "patient_sex IN ('female', 'male', 'other')", name="ck_clinical_cases_patient_sex_allowed"
        ),
        sa.CheckConstraint("char_length(title) > 0", name="ck_clinical_cases_title_not_empty"),
        sa.CheckConstraint(
            "char_length(presentation) > 0", name="ck_clinical_cases_presentation_not_empty"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_clinical_cases"),
    )
    op.create_index("ix_clinical_cases_created_at", "clinical_cases", ["created_at"])

    op.create_table(
        "case_findings",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint(
            "category IN ('history', 'symptom', 'vital_sign', 'physical_exam', "
            "'laboratory', 'imaging', 'other')",
            name="ck_case_findings_category_allowed",
        ),
        sa.CheckConstraint("position >= 0", name="ck_case_findings_position_non_negative"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["clinical_cases.id"],
            name="fk_case_findings_case_id_clinical_cases", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_findings"),
        sa.UniqueConstraint("case_id", "position", name="uq_case_findings_case_id_position"),
    )
    op.create_index("ix_case_findings_case_id", "case_findings", ["case_id"])

    op.create_table(
        "case_answers",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("answer_text", sa.String(300), nullable=False),
        sa.Column("normalized_answer", sa.String(300), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("score_weight", sa.SmallInteger(), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("score_weight BETWEEN 0 AND 100", name="ck_case_answers_score_weight_range"),
        sa.CheckConstraint(
            "char_length(normalized_answer) > 0", name="ck_case_answers_normalized_not_empty"
        ),
        sa.CheckConstraint("position >= 0", name="ck_case_answers_position_non_negative"),
        sa.ForeignKeyConstraint(
            ["case_id"], ["clinical_cases.id"],
            name="fk_case_answers_case_id_clinical_cases", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_answers"),
        sa.UniqueConstraint("case_id", "position", name="uq_case_answers_case_id_position"),
        sa.UniqueConstraint(
            "case_id", "normalized_answer", name="uq_case_answers_case_id_normalized_answer"
        ),
    )
    op.create_index("ix_case_answers_case_id", "case_answers", ["case_id"])

    op.create_table(
        "case_submissions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("matched_answer_id", sa.BigInteger(), nullable=True),
        sa.Column("submitted_answer", sa.String(300), nullable=False),
        sa.Column("normalized_answer", sa.String(300), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("max_score", sa.SmallInteger(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("max_score >= 0", name="ck_case_submissions_max_score_non_negative"),
        sa.CheckConstraint(
            "score BETWEEN 0 AND max_score", name="ck_case_submissions_score_within_max"
        ),
        sa.ForeignKeyConstraint(
            ["case_id"], ["clinical_cases.id"],
            name="fk_case_submissions_case_id_clinical_cases", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["matched_answer_id"], ["case_answers.id"],
            name="fk_case_submissions_matched_answer_id_case_answers", ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_case_submissions"),
    )
    op.create_index(
        "ix_case_submissions_case_id_created_at", "case_submissions", ["case_id", "created_at"]
    )
    op.create_index(
        "ix_case_submissions_matched_answer_id", "case_submissions", ["matched_answer_id"]
    )


def downgrade() -> None:
    op.drop_table("case_submissions")
    op.drop_table("case_answers")
    op.drop_table("case_findings")
    op.drop_table("clinical_cases")
