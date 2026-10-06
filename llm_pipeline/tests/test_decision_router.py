import logging
from typing import Any

import pytest

from clinical_extraction.decisioning.policy import ReviewStatus, Verdict
from clinical_extraction.decisioning.providers.fake import FakeDecisionProvider
from clinical_extraction.decisioning.queries import build_queries
from clinical_extraction.decisioning.router import DecisionRouter, Route, default_routes
from clinical_extraction.decisioning.schema import DecisionBatch, DecisionQuery
from clinical_extraction.decisioning.tasks import NO, DecisionTask
from clinical_extraction.decisioning.verifier import CaseVerifier
from clinical_extraction.errors import DecisionProviderError
from clinical_extraction.schema import ClinicalCaseExtraction

SOURCE = "Synthetic source text about migratory abdominal pain."


def _answer(source_text: str, query: DecisionQuery) -> tuple[str, float]:
    del source_text
    answers = {
        DecisionTask.FINDING_SUPPORT: "supported",
        DecisionTask.FINDING_CATEGORY: "symptom" if query.index == 0 else "laboratory",
        DecisionTask.DIAGNOSIS_STATUS: "differential" if query.index == 2 else "established",
        DecisionTask.DIAGNOSIS_LEAK: NO,
        DecisionTask.FINDING_COMPLETENESS: "complete",
    }
    return answers[query.task], 0.95


@pytest.fixture
def case(valid_extraction: dict[str, Any]) -> ClinicalCaseExtraction:
    return ClinicalCaseExtraction.model_validate(valid_extraction)


def test_each_provider_is_called_once_per_case(case: ClinicalCaseExtraction) -> None:
    primary = FakeDecisionProvider(_answer)
    router = DecisionRouter({"fake": primary}, default_routes(primary="fake", shadow_local=False))

    routed = router.decide(SOURCE, build_queries(case))

    assert primary.calls == 1
    assert len(routed.primary) == len(build_queries(case))


def test_tasks_can_be_split_between_providers(case: ClinicalCaseExtraction) -> None:
    jev = FakeDecisionProvider(_answer, name="jev")
    local = FakeDecisionProvider(_answer, name="mine", tasks={DecisionTask.FINDING_CATEGORY})
    routes = default_routes(primary="jev", shadow_local=False)
    routes[DecisionTask.FINDING_CATEGORY] = Route(primary="mine")

    routed = DecisionRouter({"jev": jev, "mine": local}, routes).decide(SOURCE, build_queries(case))

    assert {d.provider for q, d in routed.primary.items() if q.endswith(".category")} == {"mine"}
    assert {d.provider for q, d in routed.primary.items() if not q.endswith(".category")} == {"jev"}


def test_a_shadow_is_recorded_but_never_decides(case: ClinicalCaseExtraction) -> None:
    def contrarian(source_text: str, query: DecisionQuery) -> tuple[str, float]:
        del source_text, query
        return "imaging", 0.99

    shadow = FakeDecisionProvider(contrarian, name="shadow", tasks={DecisionTask.FINDING_CATEGORY})
    routes = default_routes(primary="fake", shadow_local=False)
    routes[DecisionTask.FINDING_CATEGORY] = Route(primary="fake", shadow="shadow")
    router = DecisionRouter({"fake": FakeDecisionProvider(_answer), "shadow": shadow}, routes)

    report = CaseVerifier(router).verify(SOURCE, case)

    assert report.status is ReviewStatus.ACCEPT
    assert len(report.shadow) == len(case.findings)
    assert not any(s.agrees for s in report.shadow)


def test_a_failing_shadow_does_not_change_the_outcome(case: ClinicalCaseExtraction) -> None:
    broken = FakeDecisionProvider(
        _answer, name="shadow", tasks={DecisionTask.FINDING_CATEGORY}, fail=True
    )
    routes = default_routes(primary="fake", shadow_local=False)
    routes[DecisionTask.FINDING_CATEGORY] = Route(primary="fake", shadow="shadow")
    router = DecisionRouter({"fake": FakeDecisionProvider(_answer), "shadow": broken}, routes)

    report = CaseVerifier(router).verify(SOURCE, case)

    assert report.status is ReviewStatus.ACCEPT
    assert report.shadow_errors == len(case.findings)


def test_an_unavailable_verifier_fails_closed(
    case: ClinicalCaseExtraction, caplog: pytest.LogCaptureFixture
) -> None:
    broken = FakeDecisionProvider(_answer, fail=True)
    router = DecisionRouter({"fake": broken}, default_routes(primary="fake", shadow_local=False))

    with caplog.at_level(logging.DEBUG):
        report = CaseVerifier(router).verify(SOURCE, case)

    assert report.status is ReviewStatus.NEEDS_REVIEW
    [reason] = report.reasons
    assert reason.verdict is Verdict.UNAVAILABLE
    assert SOURCE not in caplog.text


def test_an_unanswered_question_is_an_error(case: ClinicalCaseExtraction) -> None:
    class Forgetful(FakeDecisionProvider):
        def decide(self, source_text: str, queries: Any) -> DecisionBatch:
            return super().decide(source_text, queries[:-1])

    router = DecisionRouter(
        {"fake": Forgetful(_answer)}, default_routes(primary="fake", shadow_local=False)
    )

    with pytest.raises(DecisionProviderError, match="unanswered"):
        router.decide(SOURCE, build_queries(case))


def test_routes_are_checked_when_the_router_is_built() -> None:
    fake = FakeDecisionProvider(_answer)
    narrow = FakeDecisionProvider(_answer, name="narrow", tasks=set())

    with pytest.raises(ValueError, match="not configured"):
        DecisionRouter({"fake": fake}, default_routes(primary="missing", shadow_local=False))
    with pytest.raises(ValueError, match="cannot answer"):
        DecisionRouter({"narrow": narrow}, default_routes(primary="narrow", shadow_local=False))


def test_one_provider_in_two_roles_is_still_called_once(case: ClinicalCaseExtraction) -> None:
    """Mid-migration: local answers categories, Jev shadows them and answers the rest."""
    jev = FakeDecisionProvider(_answer, name="jev")
    local = FakeDecisionProvider(_answer, name="mine", tasks={DecisionTask.FINDING_CATEGORY})
    routes = default_routes(primary="jev", shadow_local=False)
    routes[DecisionTask.FINDING_CATEGORY] = Route(primary="mine", shadow="jev")

    routed = DecisionRouter({"jev": jev, "mine": local}, routes).decide(SOURCE, build_queries(case))

    assert (jev.calls, local.calls) == (1, 1)
    assert len(routed.shadow) == len(case.findings)
    assert {d.provider for q, d in routed.primary.items() if q.endswith(".category")} == {"mine"}


def test_a_failure_in_a_provider_with_primary_work_is_not_hidden(
    case: ClinicalCaseExtraction,
) -> None:
    jev = FakeDecisionProvider(_answer, name="jev", fail=True)
    local = FakeDecisionProvider(_answer, name="mine", tasks={DecisionTask.FINDING_CATEGORY})
    routes = default_routes(primary="jev", shadow_local=False)
    routes[DecisionTask.FINDING_CATEGORY] = Route(primary="mine", shadow="jev")

    with pytest.raises(DecisionProviderError):
        DecisionRouter({"jev": jev, "mine": local}, routes).decide(SOURCE, build_queries(case))


def test_a_provider_cannot_shadow_itself() -> None:
    fake = FakeDecisionProvider(_answer)
    routes = {DecisionTask.FINDING_CATEGORY: Route(primary="fake", shadow="fake")}

    with pytest.raises(ValueError, match="shadow itself"):
        DecisionRouter({"fake": fake}, routes)
