"""The extraction contract must stay POSTable to the backend's /api/v1/cases.

Guards against the two sides drifting apart: the check reads the committed
OpenAPI document, so it runs in CI with no backend or database.
"""

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest

from clinical_extraction.schema import ClinicalCaseExtraction

OPENAPI_PATH = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    return document


def _resolve(openapi: dict[str, Any], name: str) -> dict[str, Any]:
    schema = dict(openapi["components"]["schemas"][name])
    # jsonschema resolves $ref against the document root.
    schema["components"] = openapi["components"]
    return schema


def test_extraction_fields_match_the_backend_create_schema(openapi: dict[str, Any]) -> None:
    backend = openapi["components"]["schemas"]["ClinicalCaseCreate"]["properties"]
    extraction = ClinicalCaseExtraction.model_json_schema()["properties"]

    # `provenance` is added by the pipeline, not extracted by the model.
    assert set(extraction) == set(backend) - {"provenance"}


def test_backend_and_extraction_agree_on_enums(openapi: dict[str, Any]) -> None:
    schemas = openapi["components"]["schemas"]
    extraction_defs = ClinicalCaseExtraction.model_json_schema()["$defs"]

    assert set(schemas["FindingCategory"]["enum"]) == set(
        extraction_defs["FindingCategory"]["enum"]
    )
    assert set(schemas["PatientSex"]["enum"]) == set(extraction_defs["PatientSex"]["enum"])


def test_extraction_payload_validates_against_the_live_api_schema(
    openapi: dict[str, Any], valid_extraction: dict[str, Any]
) -> None:
    case = ClinicalCaseExtraction.model_validate(valid_extraction)
    payload = case.to_case_create_payload(model="gemini-2.5-flash", prompt_version="extract-v1")

    jsonschema.validate(payload, _resolve(openapi, "ClinicalCaseCreate"))


def test_backend_rejects_what_extraction_rejects(
    openapi: dict[str, Any], valid_extraction: dict[str, Any]
) -> None:
    schema = _resolve(openapi, "ClinicalCaseCreate")
    invalid = {**valid_extraction, "findings": [{"category": "vibes", "value": "x"}]}

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)
    with pytest.raises(ValueError, match="findings"):
        ClinicalCaseExtraction.model_validate(invalid)


def test_public_case_schema_has_no_answer_key(openapi: dict[str, Any]) -> None:
    """The security invariant, asserted from the published contract itself."""
    public = openapi["components"]["schemas"]["PublicClinicalCase"]["properties"]

    assert "answers" not in public
    assert not {k for k in public if "correct" in k or "weight" in k}
