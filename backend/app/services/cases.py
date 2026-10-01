"""Use cases. One database transaction per public function."""

import uuid
from dataclasses import asdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CaseAnswer, CaseFinding, CaseSubmission, ClinicalCase
from app.domain.enums import FindingCategory, PatientSex, ScoreOutcome
from app.domain.measurements import parse_measurements
from app.domain.scoring import AnswerKeyEntry, max_score, normalize_answer, score_answer
from app.schemas.cases import (
    CaseList,
    CaseStats,
    CaseSummary,
    ClinicalCaseCreate,
    FindingMeasurement,
    OutcomeCount,
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
            PublicFinding(
                category=FindingCategory(f.category),
                value=f.value,
                measurements=[FindingMeasurement(**asdict(m)) for m in parse_measurements(f.value)],
            )
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


def get_case_stats(session: Session, case_id: uuid.UUID) -> CaseStats:
    """How the field has done on this case.

    Counts only. Showing which answers were given would leak the key, so the
    response carries outcome totals and nothing else.
    """
    if session.get(ClinicalCase, case_id) is None:
        raise CaseNotFoundError(case_id)

    rows = session.execute(
        select(
            CaseSubmission.is_correct,
            CaseSubmission.score,
            CaseSubmission.max_score,
            func.count().label("attempts"),
        )
        .where(CaseSubmission.case_id == case_id)
        .group_by(CaseSubmission.is_correct, CaseSubmission.score, CaseSubmission.max_score)
    ).all()

    counts: dict[ScoreOutcome, int] = dict.fromkeys(ScoreOutcome, 0)
    total = 0
    weighted = 0
    ceiling = 0
    for row in rows:
        if row.is_correct:
            outcome = ScoreOutcome.CORRECT
        elif row.score > 0:
            outcome = ScoreOutcome.PARTIALLY_CORRECT
        else:
            outcome = ScoreOutcome.INCORRECT
        counts[outcome] += row.attempts
        total += row.attempts
        weighted += row.score * row.attempts
        ceiling = max(ceiling, row.max_score)

    if ceiling == 0:
        ceiling = max_score(
            [
                AnswerKeyEntry(a.id, a.normalized_answer, a.is_correct, a.score_weight)
                for a in session.scalars(select(CaseAnswer).where(CaseAnswer.case_id == case_id))
            ]
        )

    return CaseStats(
        submissions=total,
        outcomes=[OutcomeCount(outcome=o, count=c) for o, c in counts.items()],
        average_score=round(weighted / total, 2) if total else 0.0,
        max_score=ceiling,
    )
