"""The whole verification chain over real HTTP, against the local TypeSafe stand-in."""

import threading
from collections.abc import Iterator

import pytest
from typesafe_sdk import RetryPolicy, TypeSafeClient

from clinical_extraction.config import DecisionSettings
from clinical_extraction.decisioning.policy import ReviewStatus
from clinical_extraction.decisioning.providers.typesafe import TypeSafeDecisionProvider
from clinical_extraction.decisioning.router import DecisionRouter, default_routes
from clinical_extraction.decisioning.verifier import CaseVerifier
from clinical_extraction.evals.dataset import load_dataset
from clinical_extraction.evals.decisions import run_decision_eval
from clinical_extraction.evals.jev_simulator import (
    SIMULATED_MODEL,
    JevSimulator,
    SimulatorConfig,
    make_server,
)

PERFECT = SimulatorConfig(error_rate=0.0, unsure_rate=0.0, min_latency_ms=0, max_latency_ms=0)


def _serve(config: SimulatorConfig) -> Iterator[str]:
    server = make_server(JevSimulator(load_dataset(), config))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def perfect_url() -> Iterator[str]:
    yield from _serve(PERFECT)


def _verifier(base_url: str, *, retries: int = 0) -> CaseVerifier:
    settings = DecisionSettings(_env_file=None, typesafe_api_key="sim", typesafe_base_url=base_url)
    client = TypeSafeClient(
        api_key="sim",
        base_url=base_url,
        retry=RetryPolicy(max_retries=retries, backoff_initial=0.0),
    )
    provider = TypeSafeDecisionProvider(settings, client=client)
    router = DecisionRouter(
        {provider.name: provider}, default_routes(primary=provider.name, shadow_local=False)
    )
    return CaseVerifier(router)


def test_a_clean_case_passes_over_real_http(perfect_url: str) -> None:
    example = load_dataset()[1]

    report = _verifier(perfect_url).verify(example.raw_text, example.expected)

    assert report.status is ReviewStatus.ACCEPT
    [usage] = report.usage
    assert usage.model == SIMULATED_MODEL
    assert usage.input_tokens > 0


def test_a_perfect_stand_in_catches_every_planted_defect(perfect_url: str) -> None:
    examples = load_dataset()

    summary = run_decision_eval(
        _verifier(perfect_url), examples, provider="typesafe", requested_model="jev-latest"
    )

    assert summary.resolved_models == [SIMULATED_MODEL]
    assert summary.verification_unavailable == 0
    assert summary.clean_pass_rate == 1.0
    assert summary.defect_detection_recall == 1.0
    assert summary.external_calls_per_case == 1.0


def test_a_noisy_stand_in_sends_doubt_to_review_not_to_accept() -> None:
    examples = load_dataset()
    noisy = SimulatorConfig(error_rate=0.0, unsure_rate=1.0, min_latency_ms=0, max_latency_ms=0)

    for url in _serve(noisy):
        summary = run_decision_eval(
            _verifier(url), examples[:2], provider="typesafe", requested_model="jev-latest"
        )

    assert summary.clean_pass_rate == 0.0
    assert summary.false_accept_rate == 0.0


def test_a_transient_outage_is_absorbed_by_retries() -> None:
    flaky = SimulatorConfig(
        error_rate=0.0, unsure_rate=0.0, min_latency_ms=0, max_latency_ms=0, fail_every=2
    )
    example = load_dataset()[0]

    for url in _serve(flaky):
        verifier = _verifier(url, retries=2)
        reports = [verifier.verify(example.raw_text, example.expected) for _ in range(3)]

    assert all(r.status is ReviewStatus.ACCEPT for r in reports)


def test_without_retries_an_outage_fails_closed() -> None:
    always_down = SimulatorConfig(min_latency_ms=0, max_latency_ms=0, fail_every=1)
    example = load_dataset()[0]

    for url in _serve(always_down):
        report = _verifier(url).verify(example.raw_text, example.expected)

    assert report.status is ReviewStatus.NEEDS_REVIEW
    assert report.reasons[0].verdict == "unavailable"


def test_the_stand_in_rejects_bad_requests() -> None:
    simulator = JevSimulator(load_dataset(), PERFECT)

    assert simulator.handle({"state": "", "questions": {}})[0] == 422


def test_the_review_load_sweep_follows_the_compounding_formula() -> None:
    from clinical_extraction.evals.review_load import sweep  # noqa: PLC0415

    result = sweep(load_dataset()[:3], shares=(0.0, 0.5), seeds=2)

    clean, noisy = result["rows"]
    assert result["simulated"] is True
    assert clean["clean_pass_rate"] == 1.0
    assert noisy["clean_pass_rate"] < clean["clean_pass_rate"]
    assert noisy["expected_clean_pass_rate"] < 0.01
