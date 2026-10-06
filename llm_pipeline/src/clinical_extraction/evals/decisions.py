"""Does the verifier catch what it is meant to catch, and what does that cost?

Each vignette is verified as written (clean) and with one known defect planted
at a time. Then:

    defect_detection_recall   share of planted defects sent to review
    false_accept_rate         share of planted defects that passed (1 - recall)
    clean_pass_rate           share of correct candidates accepted
    false_review_rate         share of correct candidates sent to review

A verifier that flags everything gets perfect recall and is useless, so the
two sides are always reported together.

Defects come from the hand-written ground truth, not from a model, so they are
known exactly. A dropped finding is planted too; the check that should catch it,
finding_completeness, is experimental and reported on its own line.
"""

import copy
import logging
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from clinical_extraction.decisioning.policy import ReviewStatus
from clinical_extraction.decisioning.providers.fake import FakeDecisionProvider
from clinical_extraction.decisioning.schema import DecisionQuery
from clinical_extraction.decisioning.tasks import NO, YES, DecisionTask
from clinical_extraction.decisioning.verifier import CaseVerifier, VerificationReport
from clinical_extraction.evals.dataset import EvalExample
from clinical_extraction.evals.metrics import (
    SIMILARITY_THRESHOLD,
    normalize,
    percentile,
    similarity,
)
from clinical_extraction.ml.datasets import split_for
from clinical_extraction.ml.records import Split
from clinical_extraction.schema import ClinicalCaseExtraction, FindingCategory

logger = logging.getLogger(__name__)

CLEAN = "clean"


@dataclass(frozen=True, slots=True)
class Scenario:
    example_id: str
    defect: str
    source_text: str
    candidate: ClinicalCaseExtraction

    @property
    def is_clean(self) -> bool:
        return self.defect == CLEAN


Mutation = Callable[[dict[str, Any], EvalExample, list[EvalExample]], dict[str, Any] | None]


def _unsupported_finding(
    payload: dict[str, Any], example: EvalExample, examples: list[EvalExample]
) -> dict[str, Any]:
    # Borrow a finding from the next vignette: real clinical wording, absent here.
    donor = examples[(examples.index(example) + 1) % len(examples)]
    payload["findings"].append(donor.expected.findings[0].model_dump(mode="json"))
    return payload


def _wrong_category(
    payload: dict[str, Any], example: EvalExample, examples: list[EvalExample]
) -> dict[str, Any]:
    del example, examples
    categories = list(FindingCategory)
    current = FindingCategory(payload["findings"][0]["category"])
    payload["findings"][0]["category"] = categories[(categories.index(current) + 1) % 7]
    return payload


def _differential_marked_established(
    payload: dict[str, Any], example: EvalExample, examples: list[EvalExample]
) -> dict[str, Any] | None:
    del example, examples
    differential = next((a for a in payload["answers"] if not a["is_correct"]), None)
    if differential is None:
        return None
    differential["is_correct"] = True
    return payload


def _established(payload: dict[str, Any]) -> str:
    return str(next(a["text"] for a in payload["answers"] if a["is_correct"]))


def _title_leak(
    payload: dict[str, Any], example: EvalExample, examples: list[EvalExample]
) -> dict[str, Any]:
    del example, examples
    payload["title"] = f"{_established(payload)}: {payload['title']}"[:200]
    return payload


def _presentation_leak(
    payload: dict[str, Any], example: EvalExample, examples: list[EvalExample]
) -> dict[str, Any]:
    del example, examples
    payload["presentation"] += f" Final diagnosis: {_established(payload)}."
    return payload


def _missing_finding(
    payload: dict[str, Any], example: EvalExample, examples: list[EvalExample]
) -> dict[str, Any] | None:
    del example, examples
    if len(payload["findings"]) < 2:  # noqa: PLR2004 - the contract needs one finding
        return None
    payload["findings"] = payload["findings"][:-1]
    return payload


MUTATIONS: dict[str, Mutation] = {
    "unsupported_finding": _unsupported_finding,
    "missing_finding": _missing_finding,
    "wrong_category": _wrong_category,
    "wrong_diagnosis_status": _differential_marked_established,
    "title_leak": _title_leak,
    "presentation_leak": _presentation_leak,
}

# Which check is supposed to catch each defect.
EXPECTED_CHECK = {
    "unsupported_finding": DecisionTask.FINDING_SUPPORT,
    "missing_finding": DecisionTask.FINDING_COMPLETENESS,
    "wrong_category": DecisionTask.FINDING_CATEGORY,
    "wrong_diagnosis_status": DecisionTask.DIAGNOSIS_STATUS,
    "title_leak": DecisionTask.DIAGNOSIS_LEAK,
    "presentation_leak": DecisionTask.DIAGNOSIS_LEAK,
}


def build_scenarios(examples: list[EvalExample]) -> list[Scenario]:
    scenarios = []
    for example in examples:
        scenarios.append(Scenario(example.id, CLEAN, example.raw_text, example.expected))
        for defect, mutate in MUTATIONS.items():
            payload = mutate(example.expected.model_dump(mode="json"), example, examples)
            if payload is None:
                continue
            candidate = ClinicalCaseExtraction.model_validate(copy.deepcopy(payload))
            scenarios.append(Scenario(example.id, defect, example.raw_text, candidate))
    return scenarios


# ── Offline stand-in for Jev ──────────────────────────────────────────────────
# Answers from the ground truth, like the fake extraction provider. Two known
# misjudgments are built in, so the eval is shown to register verifier errors
# instead of always printing a perfect score.
INJECTED_MISJUDGMENTS: dict[str, str] = {
    "case-004": "unsure about the first finding's category (a clean case goes to review)",
    "case-008": "misses a diagnosis in the title (a title leak is accepted)",
}
REFERENCE_CONFIDENCE = 0.95
UNSURE_PROBABILITY = 0.3


def _true_label(
    truth: ClinicalCaseExtraction, query: DecisionQuery, categories: dict[str, str]
) -> str:
    if query.task is DecisionTask.FINDING_SUPPORT:
        supported = any(
            similarity(query.subject, f.value) >= SIMILARITY_THRESHOLD for f in truth.findings
        )
        return "supported" if supported else "not_stated"
    if query.task is DecisionTask.FINDING_CATEGORY:
        return categories.get(normalize(query.subject), str(FindingCategory.OTHER))
    if query.task is DecisionTask.DIAGNOSIS_STATUS:
        match = next(
            (a for a in truth.answers if normalize(a.text) == normalize(query.subject)), None
        )
        if match is None:
            return "not_stated"
        return "established" if match.is_correct else "differential"
    if query.task is DecisionTask.FINDING_COMPLETENESS:
        covered = all(
            any(
                similarity(f.value, extracted) >= SIMILARITY_THRESHOLD
                for extracted in query.reference
            )
            for f in truth.findings
        )
        return "complete" if covered else "likely_incomplete"
    leaked = any(normalize(d) in normalize(query.subject) for d in query.reference)
    return YES if leaked else NO


def reference_provider(examples: list[EvalExample]) -> FakeDecisionProvider:
    by_source = {example.raw_text: example for example in examples}
    categories = {
        normalize(finding.value): str(finding.category)
        for example in examples
        for finding in example.expected.findings
    }

    def answer(source_text: str, query: DecisionQuery) -> tuple[str, float]:
        example = by_source[source_text]
        label = _true_label(example.expected, query, categories)
        if example.id == "case-008" and query.target == "title":
            label = NO
        unsure = (
            example.id == "case-004"
            and query.task is DecisionTask.FINDING_CATEGORY
            and query.index == 0
        )
        return label, UNSURE_PROBABILITY if unsure else REFERENCE_CONFIDENCE

    return FakeDecisionProvider(answer, name="reference", model="reference-ground-truth")


# ── Running and summarising ──────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class ScenarioResult:
    example_id: str
    defect: str
    split: Split
    status: ReviewStatus
    caught_by_expected_check: bool
    unavailable: bool
    latency_ms: float
    calls: int
    input_tokens: int
    shadow: list[tuple[str, str, str]]  # (query_id, shadow_label, primary_label)
    models: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionEvalSummary:
    provider: str
    # What was asked for (an alias such as jev-latest) and what actually answered
    # (jev-1.13.0). Only the second makes a committed result reproducible.
    requested_model: str
    resolved_models: list[str]
    scenarios: int
    clean_cases: int
    planted_defects: int
    clean_pass_rate: float
    false_review_rate: float
    defect_detection_recall: float
    false_accept_rate: float
    caught_by_expected_check_rate: float
    recall_by_defect: dict[str, float]
    held_out: dict[str, float]
    verification_unavailable: int
    external_calls_per_case: float
    latency_ms_p50: float
    latency_ms_p95: float
    input_tokens_per_case: float
    estimated_usd_per_1000_cases: float
    shadow: dict[str, Any]
    failures: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _run_scenario(verifier: CaseVerifier, scenario: Scenario) -> ScenarioResult:
    started = time.perf_counter()
    report: VerificationReport = verifier.verify(scenario.source_text, scenario.candidate)
    elapsed_ms = (time.perf_counter() - started) * 1000
    expected_check = EXPECTED_CHECK.get(scenario.defect)
    return ScenarioResult(
        example_id=scenario.example_id,
        defect=scenario.defect,
        split=split_for(scenario.example_id),
        status=report.status,
        caught_by_expected_check=any(r.check == expected_check for r in report.reasons),
        unavailable=any(r.verdict == "unavailable" for r in report.reasons),
        latency_ms=elapsed_ms,
        calls=sum(u.calls for u in report.usage if u.provider != "local"),
        input_tokens=sum(u.input_tokens for u in report.usage),
        shadow=[(s.query_id, s.shadow_label, s.primary_label) for s in report.shadow],
        models=tuple(u.model for u in report.usage if u.provider != "local"),
    )


def _shadow_summary(
    results: list[ScenarioResult], examples: dict[str, EvalExample]
) -> dict[str, Any]:
    """How the shadow model compares, on clean candidates only (each finding once)."""
    compared = agreed = 0
    correct_by_split: dict[str, list[bool]] = defaultdict(list)
    for result in results:
        if result.defect != CLEAN:
            continue
        findings = examples[result.example_id].expected.findings
        for query_id, shadow_label, primary_label in result.shadow:
            compared += 1
            agreed += shadow_label == primary_label
            index = int(query_id.split(".")[1])
            truth = str(findings[index].category)
            correct_by_split[result.split].append(shadow_label == truth)
    return {
        "compared": compared,
        "agreement_with_primary": _rate(agreed, compared),
        # Train-split accuracy is shown only to make the gap visible; the
        # held-out number is the one that counts.
        "accuracy_held_out": _rate(
            sum(correct_by_split[Split.HELD_OUT]), len(correct_by_split[Split.HELD_OUT])
        ),
        "held_out_examples": len(correct_by_split[Split.HELD_OUT]),
        "accuracy_train_split": _rate(
            sum(correct_by_split[Split.TRAIN]), len(correct_by_split[Split.TRAIN])
        ),
    }


def run_decision_eval(
    verifier: CaseVerifier,
    examples: list[EvalExample],
    *,
    provider: str,
    requested_model: str,
    usd_per_m_input: float = 0.0,
    delay_seconds: float = 0.0,
) -> DecisionEvalSummary:
    scenarios = build_scenarios(examples)
    results = []
    for index, scenario in enumerate(scenarios):
        if delay_seconds > 0 and index > 0:
            time.sleep(delay_seconds)
        results.append(_run_scenario(verifier, scenario))

    clean = [r for r in results if r.defect == CLEAN]
    planted = [r for r in results if r.defect != CLEAN]
    accepted_clean = sum(r.status is ReviewStatus.ACCEPT for r in clean)
    caught = sum(r.status is ReviewStatus.NEEDS_REVIEW for r in planted)

    by_defect: dict[str, list[ScenarioResult]] = defaultdict(list)
    for result in planted:
        by_defect[result.defect].append(result)

    held_clean = [r for r in clean if r.split is Split.HELD_OUT]
    held_planted = [r for r in planted if r.split is Split.HELD_OUT]
    tokens = [r.input_tokens for r in results]
    mean_tokens = sum(tokens) / len(tokens) if tokens else 0.0

    return DecisionEvalSummary(
        provider=provider,
        requested_model=requested_model,
        resolved_models=sorted({model for r in results for model in r.models}),
        scenarios=len(results),
        clean_cases=len(clean),
        planted_defects=len(planted),
        clean_pass_rate=_rate(accepted_clean, len(clean)),
        false_review_rate=_rate(len(clean) - accepted_clean, len(clean)),
        defect_detection_recall=_rate(caught, len(planted)),
        false_accept_rate=_rate(len(planted) - caught, len(planted)),
        caught_by_expected_check_rate=_rate(
            sum(r.caught_by_expected_check for r in planted), len(planted)
        ),
        recall_by_defect={
            defect: _rate(sum(r.status is ReviewStatus.NEEDS_REVIEW for r in group), len(group))
            for defect, group in sorted(by_defect.items())
        },
        held_out={
            "clean_pass_rate": _rate(
                sum(r.status is ReviewStatus.ACCEPT for r in held_clean), len(held_clean)
            ),
            "defect_detection_recall": _rate(
                sum(r.status is ReviewStatus.NEEDS_REVIEW for r in held_planted),
                len(held_planted),
            ),
        },
        verification_unavailable=sum(r.unavailable for r in results),
        external_calls_per_case=round(sum(r.calls for r in results) / len(results), 2)
        if results
        else 0.0,
        latency_ms_p50=percentile([r.latency_ms for r in results], 50),
        latency_ms_p95=percentile([r.latency_ms for r in results], 95),
        input_tokens_per_case=round(mean_tokens, 1),
        estimated_usd_per_1000_cases=round(mean_tokens * 1000 * usd_per_m_input / 1e6, 4),
        shadow=_shadow_summary(results, {e.id: e for e in examples}),
        failures=[
            {"example_id": r.example_id, "defect": r.defect, "status": r.status}
            for r in results
            if (r.defect == CLEAN) == (r.status is ReviewStatus.NEEDS_REVIEW)
        ],
    )
