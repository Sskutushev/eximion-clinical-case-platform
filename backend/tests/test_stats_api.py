import uuid

from fastapi.testclient import TestClient


def _outcomes(body: dict[str, object]) -> dict[str, int]:
    rows = body["outcomes"]
    assert isinstance(rows, list)
    return {row["outcome"]: row["count"] for row in rows}


def test_stats_start_empty(client: TestClient, created_case_id: str) -> None:
    body = client.get(f"/api/v1/cases/{created_case_id}/stats").json()

    assert body["submissions"] == 0
    assert body["average_score"] == 0.0
    assert body["max_score"] == 10
    assert _outcomes(body) == {"correct": 0, "partially_correct": 0, "incorrect": 0}


def test_stats_count_every_outcome(client: TestClient, created_case_id: str) -> None:
    for answer in ["Acute appendicitis", "appendicitis", "Mesenteric lymphadenitis", "Migraine"]:
        client.post(f"/api/v1/cases/{created_case_id}/score", json={"answer": answer})

    body = client.get(f"/api/v1/cases/{created_case_id}/stats").json()

    assert body["submissions"] == 4
    assert _outcomes(body) == {"correct": 2, "partially_correct": 1, "incorrect": 1}
    # Mean of 10, 10, 3 and 0.
    assert body["average_score"] == 5.75


def test_stats_never_expose_answers(client: TestClient, created_case_id: str) -> None:
    client.post(f"/api/v1/cases/{created_case_id}/score", json={"answer": "Acute appendicitis"})

    response = client.get(f"/api/v1/cases/{created_case_id}/stats")

    raw = response.text.casefold()
    for leaked in ("appendicitis", "lymphadenitis", "answer", "is_correct", "score_weight"):
        assert leaked not in raw


def test_stats_for_unknown_case_return_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/cases/{uuid.uuid4()}/stats").status_code == 404


def test_public_case_carries_parsed_measurements(client: TestClient, created_case_id: str) -> None:
    findings = client.get(f"/api/v1/cases/{created_case_id}").json()["findings"]

    by_value = {f["value"]: f["measurements"] for f in findings}
    lab = by_value["WBC 14.2 x10^9/L"]
    assert lab[0]["label"] == "White cell count"
    assert lab[0]["value"] == 14.2
    assert lab[0]["flag"] == "high"
    # A finding with no number is still returned, just without a plot.
    assert by_value["Pain migrating to the right lower quadrant"] == []
