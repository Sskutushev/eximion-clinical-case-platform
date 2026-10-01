import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CaseAnswer, CaseFinding, ClinicalCase
from tests.conftest import ADMIN_HEADERS


def test_create_case_persists_normalized_rows(
    client: TestClient, db: Session, case_payload: dict[str, Any]
) -> None:
    response = client.post("/api/v1/cases", json=case_payload, headers=ADMIN_HEADERS)

    assert response.status_code == 201
    case_id = uuid.UUID(response.json()["id"])
    assert response.headers["location"] == f"/api/v1/cases/{case_id}"

    case = db.get(ClinicalCase, case_id)
    assert case is not None
    assert case.title == case_payload["title"]
    findings = db.scalars(
        select(CaseFinding).where(CaseFinding.case_id == case_id).order_by(CaseFinding.position)
    ).all()
    assert [f.value for f in findings] == [f["value"] for f in case_payload["findings"]]
    answers = db.scalars(select(CaseAnswer).where(CaseAnswer.case_id == case_id)).all()
    assert {a.normalized_answer for a in answers} == {
        "acute appendicitis",
        "appendicitis",
        "mesenteric lymphadenitis",
    }


def _mutate(payload: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {**payload, **changes}


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"findings": []}, "at least one finding"),
        ({"answers": [{"text": "X", "is_correct": False, "score_weight": 0}]}, "no correct"),
        ({"patient_age": 200}, "age out of range"),
        ({"patient_sex": "unknown"}, "sex not in enum"),
        ({"title": "   "}, "blank title"),
        ({"unexpected": "field"}, "unknown field"),
        (
            {
                "answers": [
                    {"text": "Appendicitis", "is_correct": True, "score_weight": 10},
                    {"text": "  APPENDICITIS. ", "is_correct": True, "score_weight": 10},
                ]
            },
            "duplicate after normalization",
        ),
        (
            {
                "answers": [
                    {"text": "Appendicitis", "is_correct": True, "score_weight": 5},
                    {"text": "Colitis", "is_correct": False, "score_weight": 9},
                ]
            },
            "partial outweighs correct",
        ),
    ],
)
def test_create_case_rejects_invalid_payload(
    client: TestClient,
    db: Session,
    case_payload: dict[str, Any],
    changes: dict[str, Any],
    reason: str,
) -> None:
    response = client.post(
        "/api/v1/cases", json=_mutate(case_payload, **changes), headers=ADMIN_HEADERS
    )

    assert response.status_code == 422, reason
    assert db.scalar(select(func.count()).select_from(ClinicalCase)) == 0


@pytest.mark.parametrize("headers", [{}, {"X-Admin-API-Key": "wrong"}])
def test_create_case_requires_admin_key(
    client: TestClient, case_payload: dict[str, Any], headers: dict[str, str]
) -> None:
    response = client.post("/api/v1/cases", json=case_payload, headers=headers)

    assert response.status_code == 401


def test_get_case_never_exposes_answer_key(client: TestClient, created_case_id: str) -> None:
    response = client.get(f"/api/v1/cases/{created_case_id}")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "title",
        "patient_age",
        "patient_sex",
        "presentation",
        "findings",
        "created_at",
    }
    assert all(set(f) == {"category", "value", "measurements"} for f in body["findings"])
    raw = response.text.casefold()
    for leaked in ("appendicitis", "lymphadenitis", "is_correct", "score_weight", "answer"):
        assert leaked not in raw


def test_get_case_returns_findings_in_order(
    client: TestClient, created_case_id: str, case_payload: dict[str, Any]
) -> None:
    body = client.get(f"/api/v1/cases/{created_case_id}").json()

    returned = [{"category": f["category"], "value": f["value"]} for f in body["findings"]]
    assert returned == case_payload["findings"]
    assert body["patient_age"] == 24


def test_get_unknown_case_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/cases/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Clinical case not found"}


def test_get_case_with_malformed_id_returns_422(client: TestClient) -> None:
    assert client.get("/api/v1/cases/not-a-uuid").status_code == 422


def test_list_cases_returns_summaries_only(client: TestClient, created_case_id: str) -> None:
    response = client.get("/api/v1/cases", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == [created_case_id]
    assert set(body["items"][0]) == {"id", "title", "created_at"}
