"""Fake-provider responses for the offline eval.

Ground truth with small, deliberate defects, so the harness is shown to catch
errors rather than always printing a perfect score.
"""

import json
from typing import Any

from clinical_extraction.evals.dataset import EvalExample

# example_id -> how its fake response deviates from ground truth
INJECTED_DEFECTS: dict[str, str] = {
    "case-003": "drops the last finding (recall miss)",
    "case-005": "misses the accepted synonym in the answer key",
    "case-007": "returns patient_age as null",
    "case-009": "emits an invalid category (schema violation)",
}


def _without_last_finding(payload: dict[str, Any]) -> dict[str, Any]:
    payload["findings"] = payload["findings"][:-1]
    return payload


def _drop_synonym(payload: dict[str, Any]) -> dict[str, Any]:
    correct = [a for a in payload["answers"] if a["is_correct"]]
    if len(correct) > 1:
        removed = correct[-1]
        payload["answers"] = [a for a in payload["answers"] if a is not removed]
    return payload


def _null_age(payload: dict[str, Any]) -> dict[str, Any]:
    payload["patient_age"] = None
    return payload


def _invalid_category(payload: dict[str, Any]) -> dict[str, Any]:
    payload["findings"][0]["category"] = "not_a_category"
    return payload


_MUTATORS = {
    "case-003": _without_last_finding,
    "case-005": _drop_synonym,
    "case-007": _null_age,
    "case-009": _invalid_category,
}


def build_fixtures(examples: list[EvalExample]) -> dict[str, str]:
    """Map a distinctive slice of each raw text to the canned JSON response."""
    fixtures: dict[str, str] = {}
    for example in examples:
        payload = example.expected.model_dump(mode="json")
        if (mutate := _MUTATORS.get(example.id)) is not None:
            payload = mutate(payload)
        # The provider matches on a substring of the prompt.
        fixtures[example.raw_text.strip()[:80]] = json.dumps(payload)
    return fixtures
