from typing import Any

from clinical_extraction.evals.metrics import SetMetrics, evaluate_case, normalize, summarize
from clinical_extraction.schema import ClinicalCaseExtraction


def _case(data: dict[str, Any]) -> ClinicalCaseExtraction:
    return ClinicalCaseExtraction.model_validate(data)


def test_identical_extraction_scores_perfectly(valid_extraction: dict[str, Any]) -> None:
    expected = _case(valid_extraction)

    report = evaluate_case(expected, _case(valid_extraction), "case-001")

    assert report.mismatches == []
    assert report.findings is not None
    assert (report.findings.precision, report.findings.recall, report.findings.f1) == (
        1.0,
        1.0,
        1.0,
    )
    assert report.answer_key_correct is True
    assert report.finding_category_accuracy == 1.0


def test_missing_synonym_is_an_answer_key_failure(valid_extraction: dict[str, Any]) -> None:
    expected = _case(valid_extraction)
    predicted = _case(
        {
            **valid_extraction,
            "answers": valid_extraction["answers"][:1] + valid_extraction["answers"][2:],
        }
    )

    report = evaluate_case(expected, predicted, "case-001")

    assert report.answer_key_correct is False
    assert "answer_key" in report.mismatches


def test_dropped_finding_lowers_recall_only(valid_extraction: dict[str, Any]) -> None:
    expected = _case(valid_extraction)
    predicted = _case({**valid_extraction, "findings": valid_extraction["findings"][:1]})

    report = evaluate_case(expected, predicted, "case-001")

    assert report.findings == SetMetrics(1.0, 0.5, 0.6667, 1, 0, 1)
    assert "findings" in report.mismatches


def test_wrong_category_is_detected(valid_extraction: dict[str, Any]) -> None:
    findings = [dict(f) for f in valid_extraction["findings"]]
    findings[0]["category"] = "imaging"
    predicted = _case({**valid_extraction, "findings": findings})

    report = evaluate_case(_case(valid_extraction), predicted, "case-001")

    assert report.finding_category_accuracy == 0.5
    assert "finding_categories" in report.mismatches


def test_demographic_mismatches_are_reported(valid_extraction: dict[str, Any]) -> None:
    predicted = _case({**valid_extraction, "patient_age": None, "patient_sex": "female"})

    report = evaluate_case(_case(valid_extraction), predicted, "case-001")

    assert (report.age_correct, report.sex_correct) == (False, False)
    assert {"patient_age", "patient_sex"} <= set(report.mismatches)


def test_normalization_matches_backend_rules() -> None:
    assert normalize("  Acute   Appendicitis. ") == "acute appendicitis"
    assert normalize("WBC 14.2 x10^9/L") == "wbc 14.2 x10^9/l"


def test_summary_aggregates_and_lists_failures(valid_extraction: dict[str, Any]) -> None:
    expected = _case(valid_extraction)
    good = evaluate_case(expected, _case(valid_extraction), "ok")
    bad = evaluate_case(expected, _case({**valid_extraction, "patient_age": 30}), "bad")

    summary = summarize([good, bad], provider="fake", model="m", prompt_version="v1")

    assert (summary.total, summary.schema_valid_rate) == (2, 1.0)
    assert summary.age_accuracy == 0.5
    assert summary.exact_case_match_rate == 0.5
    assert [f["example_id"] for f in summary.failures] == ["bad"]


def test_empty_sets_do_not_divide_by_zero() -> None:
    assert SetMetrics.compare(set(), set()) == SetMetrics(1.0, 1.0, 1.0, 0, 0, 0)
    assert SetMetrics.compare({"a"}, set()).f1 == 0.0
