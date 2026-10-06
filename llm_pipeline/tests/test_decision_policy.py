from collections.abc import Callable
from typing import Any

import pytest

from clinical_extraction.decisioning.policy import ReviewStatus, Verdict
from clinical_extraction.decisioning.providers.fake import FakeDecisionProvider
from clinical_extraction.decisioning.queries import build_queries
from clinical_extraction.decisioning.router import DecisionRouter, default_routes
from clinical_extraction.decisioning.schema import DecisionQuery
from clinical_extraction.decisioning.tasks import NO, YES, DecisionTask
from clinical_extraction.decisioning.verifier import CaseVerifier, VerificationReport
from clinical_extraction.schema import ClinicalCaseExtraction

SOURCE = "A 24-year-old man with migratory abdominal pain. Diagnosis: acute appendicitis."

# What a verifier that agrees with the extraction in `valid_extraction` answers.
AGREEING = {
    DecisionTask.FINDING_SUPPORT: "supported",
    DecisionTask.DIAGNOSIS_LEAK: NO,
    DecisionTask.FINDING_COMPLETENESS: "complete",
}
STATUS = {"Acute appendicitis": "established", "Appendicitis": "established"}


def _agreeing(case: ClinicalCaseExtraction) -> Callable[[str, DecisionQuery], tuple[str, float]]:
    def answer(source_text: str, query: DecisionQuery) -> tuple[str, float]:
        del source_text
        if query.task is DecisionTask.FINDING_CATEGORY:
            assert query.index is not None
            return str(case.findings[query.index].category), 0.95
        if query.task is DecisionTask.DIAGNOSIS_STATUS:
            return STATUS.get(query.subject, "differential"), 0.95
        return AGREEING[query.task], 0.95

    return answer


def _verify(
    case: ClinicalCaseExtraction,
    override: dict[str, tuple[str, float]] | None = None,
) -> VerificationReport:
    base = _agreeing(case)
    overrides = override or {}

    def answer(source_text: str, query: DecisionQuery) -> tuple[str, float]:
        return overrides.get(query.id) or base(source_text, query)

    provider = FakeDecisionProvider(answer)
    router = DecisionRouter({"fake": provider}, default_routes(primary="fake", shadow_local=False))
    return CaseVerifier(router).verify(SOURCE, case)


@pytest.fixture
def case(valid_extraction: dict[str, Any]) -> ClinicalCaseExtraction:
    return ClinicalCaseExtraction.model_validate(valid_extraction)


def test_a_candidate_the_verifier_agrees_with_is_accepted(case: ClinicalCaseExtraction) -> None:
    report = _verify(case)

    assert report.status is ReviewStatus.ACCEPT
    assert report.reasons == []
    assert len(report.decisions) == len(build_queries(case))


def test_every_check_is_asked_in_one_call(case: ClinicalCaseExtraction) -> None:
    queries = build_queries(case)

    # 2 findings x (support, category) + 3 answers + title + presentation + completeness
    assert len(queries) == 2 * 2 + 3 + 2 + 1
    assert len({q.id for q in queries}) == len(queries)


@pytest.mark.parametrize(
    ("query_id", "answer", "verdict"),
    [
        ("findings.0.support", ("not_stated", 0.95), Verdict.FLAGGED),
        ("findings.1.support", ("contradicted", 0.95), Verdict.FLAGGED),
        ("findings.1.category", ("imaging", 0.95), Verdict.FLAGGED),
        ("answers.2.status", ("established", 0.95), Verdict.FLAGGED),
        ("answers.0.status", ("differential", 0.95), Verdict.FLAGGED),
        ("answers.1.status", ("not_stated", 0.95), Verdict.FLAGGED),
        ("title.leak", (YES, 0.9), Verdict.FLAGGED),
        ("presentation.leak", (YES, 0.6), Verdict.FLAGGED),
        ("findings.completeness", ("likely_incomplete", 0.95), Verdict.FLAGGED),
        # p(yes) = 0.4: not a leak by the threshold, but not a confident "no" either.
        ("title.leak", (NO, 0.6), Verdict.UNCERTAIN),
        # Agreeing, but not sure enough to act on.
        ("findings.0.category", ("symptom", 0.3), Verdict.UNCERTAIN),
        ("findings.0.support", ("supported", 0.3), Verdict.UNCERTAIN),
    ],
)
def test_disagreement_or_doubt_sends_the_case_to_review(
    case: ClinicalCaseExtraction,
    query_id: str,
    answer: tuple[str, float],
    verdict: Verdict,
) -> None:
    report = _verify(case, {query_id: answer})

    assert report.status is ReviewStatus.NEEDS_REVIEW
    [reason] = report.reasons
    assert reason.verdict is verdict
    parts = query_id.split(".")
    expected_target = f"{parts[0]}[{parts[1]}]" if len(parts) == 3 else parts[0]
    assert reason.target == expected_target


def test_a_differential_is_not_flagged_for_being_a_differential(
    case: ClinicalCaseExtraction,
) -> None:
    report = _verify(case, {"answers.2.status": ("excluded", 0.95)})

    assert report.status is ReviewStatus.ACCEPT


def test_a_confident_no_leak_passes(case: ClinicalCaseExtraction) -> None:
    # p(yes) = 0.1
    report = _verify(case, {"title.leak": (NO, 0.9)})

    assert report.status is ReviewStatus.ACCEPT


def test_the_verifier_never_edits_the_candidate(case: ClinicalCaseExtraction) -> None:
    before = case.model_dump()

    _verify(case, {"findings.1.category": ("imaging", 0.99)})

    assert case.model_dump() == before


def test_reasons_carry_no_clinical_text(case: ClinicalCaseExtraction) -> None:
    report = _verify(
        case,
        {"findings.0.support": ("not_stated", 0.95), "title.leak": (YES, 0.95)},
    )

    rendered = str(report.to_dict())
    for text in [f.value for f in case.findings] + [a.text for a in case.answers] + [case.title]:
        assert text not in rendered
