"""Use cases. One database transaction per public function."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CaseAnswer, CaseFinding, CaseSubmission, ClinicalCase
from app.domain.enums import FindingCategory, PatientSex, ScoreOutcome
from app.domain.scoring import AnswerKeyEntry, normalize_answer, score_answer
from app.schemas.cases import (
    CaseList,
    CaseSummary,
    ClinicalCaseCreate,
    PublicClinicalCase,
    PublicFinding,
    ScoreResponse,
)

_FEEDBACK = {
    ScoreOutcome.CORRECT: "Correct diagnosis.",
    ScoreOutcome.PARTIALLY_CORRECT: "Partially correct: a relevant but not the leading diagnosis.",
    ScoreOutcome.INCORRECT: "Incorrect diagnosis.",
}


class CaseNotFoundError(Exception):
    def __init__(self, case_id: uuid.UUID) -> None:
        super().__init__(f"clinical case {case_id} not found")
        self.case_id = case_id


def create_case(session: Session, payload: ClinicalCaseCreate) -> uuid.UUID:
    case = ClinicalCase(
        title=payload.title,
        patient_age=payload.patient_age,
        patient_sex=payload.patient_sex,
        presentation=payload.presentation,
        provenance=payload.provenance.model_dump() if payload.provenance else None,
        findings=[
            CaseFinding(category=f.category, value=f.value, position=i)
            for i, f in enumerate(payload.findings)
        ],
        answers=[
            CaseAnswer(
                answer_text=a.text,
                normalized_answer=normalize_answer(a.text),
                is_correct=a.is_correct,
                score_weight=a.score_weight,
                position=i,
            )
            for i, a in enumerate(payload.answers)
        ],
    )
    with session.begin():
        session.add(case)
    return case.id


def get_public_case(session: Session, case_id: uuid.UUID) -> PublicClinicalCase:
    # Loads findings only: the answer key is never read on this path.
    case = session.scalar(
        select(ClinicalCase)
        .where(ClinicalCase.id == case_id)
        .options(selectinload(ClinicalCase.findings))
    )
    if case is None:
        raise CaseNotFoundError(case_id)
    return PublicClinicalCase(
        id=case.id,
        title=case.title,
        patient_age=case.patient_age,
        patient_sex=PatientSex(case.patient_sex) if case.patient_sex else None,
        presentation=case.presentation,
        findings=[
            PublicFinding(category=FindingCategory(f.category), value=f.value)
            for f in case.findings
        ],
        created_at=case.created_at,
    )


def list_cases(session: Session, *, limit: int, offset: int) -> CaseList:
    rows = session.execute(
        select(ClinicalCase.id, ClinicalCase.title, ClinicalCase.created_at)
        .order_by(ClinicalCase.created_at.desc(), ClinicalCase.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return CaseList(
        items=[CaseSummary(id=r.id, title=r.title, created_at=r.created_at) for r in rows],
        limit=limit,
        offset=offset,
    )


def submit_answer(session: Session, case_id: uuid.UUID, answer: str) -> ScoreResponse:
    with session.begin():
        if session.get(ClinicalCase, case_id) is None:
            raise CaseNotFoundError(case_id)
        answer_key = [
            AnswerKeyEntry(a.id, a.normalized_answer, a.is_correct, a.score_weight)
            for a in session.scalars(select(CaseAnswer).where(CaseAnswer.case_id == case_id))
        ]
        result = score_answer(answer, answer_key)
        submission = CaseSubmission(
            case_id=case_id,
            matched_answer_id=result.matched_answer_id,
            submitted_answer=answer,
            normalized_answer=result.normalized_answer,
            score=result.score,
            max_score=result.max_score,
            is_correct=result.is_correct,
        )
        session.add(submission)

    return ScoreResponse(
        submission_id=submission.id,
        score=result.score,
        max_score=result.max_score,
        is_correct=result.is_correct,
        outcome=result.outcome,
        feedback=_FEEDBACK[result.outcome],
    )
