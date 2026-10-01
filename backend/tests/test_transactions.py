from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import CaseAnswer, CaseFinding, ClinicalCase
from app.schemas.cases import AnswerIn, ClinicalCaseCreate
from app.services.cases import create_case


def test_create_case_is_atomic(db: Session, case_payload: dict[str, Any]) -> None:
    """A DB-level failure on a child row must roll back the case and all siblings."""
    valid = ClinicalCaseCreate.model_validate(case_payload)
    duplicate = AnswerIn(text="Appendicitis", is_correct=True, score_weight=10)
    # Bypass API validation so the UNIQUE(case_id, normalized_answer) constraint fires mid-insert.
    invalid = valid.model_copy(update={"answers": [*valid.answers, duplicate]})

    with pytest.raises(IntegrityError):
        create_case(db, invalid)
    db.rollback()

    for model in (ClinicalCase, CaseFinding, CaseAnswer):
        assert db.scalar(select(func.count()).select_from(model)) == 0
