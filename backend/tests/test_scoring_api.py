import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CaseSubmission


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("Acute appendicitis", (10, "correct", True)),
        ("appendicitis", (10, "correct", True)),  # accepted synonym
        ("  ACUTE   Appendicitis. ", (10, "correct", True)),  # case/whitespace/punctuation
        ("Mesenteric lymphadenitis", (3, "partially_correct", False)),
        ("Gastroenteritis", (0, "incorrect", False)),
    ],
)
def test_score_is_deterministic(
    client: TestClient, created_case_id: str, answer: str, expected: tuple[int, str, bool]
) -> None:
    response = client.post(f"/api/v1/cases/{created_case_id}/score", json={"answer": answer})

    assert response.status_code == 200
    body = response.json()
    assert (body["score"], body["outcome"], body["is_correct"]) == expected
    assert body["max_score"] == 10


def test_submission_is_persisted(client: TestClient, db: Session, created_case_id: str) -> None:
    response = client.post(
        f"/api/v1/cases/{created_case_id}/score", json={"answer": " Appendicitis "}
    )

    submission = db.get(CaseSubmission, uuid.UUID(response.json()["submission_id"]))
    assert submission is not None
    assert str(submission.case_id) == created_case_id
    assert submission.submitted_answer == "Appendicitis"
    assert submission.normalized_answer == "appendicitis"
    assert (submission.score, submission.max_score, submission.is_correct) == (10, 10, True)
    assert submission.matched_answer_id is not None


def test_incorrect_submission_is_persisted_without_match(
    client: TestClient, db: Session, created_case_id: str
) -> None:
    client.post(f"/api/v1/cases/{created_case_id}/score", json={"answer": "Migraine"})

    submission = db.scalars(select(CaseSubmission)).one()
    assert submission.matched_answer_id is None
    assert submission.score == 0


def test_score_unknown_case_returns_404_and_persists_nothing(
    client: TestClient, db: Session
) -> None:
    response = client.post(f"/api/v1/cases/{uuid.uuid4()}/score", json={"answer": "Anything"})

    assert response.status_code == 404
    assert db.scalars(select(CaseSubmission)).first() is None


@pytest.mark.parametrize("answer", ["", "   ", "...", "x" * 301])
def test_score_rejects_blank_or_oversized_answer(
    client: TestClient, created_case_id: str, answer: str
) -> None:
    response = client.post(f"/api/v1/cases/{created_case_id}/score", json={"answer": answer})

    assert response.status_code == 422
