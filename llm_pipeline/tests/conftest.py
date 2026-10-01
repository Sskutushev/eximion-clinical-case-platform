from typing import Any

import pytest


@pytest.fixture
def valid_extraction() -> dict[str, Any]:
    return {
        "title": "Acute right lower quadrant pain",
        "patient_age": 24,
        "patient_sex": "male",
        "presentation": "Migratory abdominal pain for 18 hours with nausea.",
        "findings": [
            {"category": "symptom", "value": "Pain migrating to the right lower quadrant"},
            {"category": "laboratory", "value": "White cell count 14.2 x10^9/L"},
        ],
        "answers": [
            {"text": "Acute appendicitis", "is_correct": True},
            {"text": "Appendicitis", "is_correct": True},
            {"text": "Mesenteric lymphadenitis", "is_correct": False},
        ],
    }
