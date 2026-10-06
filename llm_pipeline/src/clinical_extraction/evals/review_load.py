"""How a verifier's per-question reliability turns into review load.

Each case gets about twenty questions, and any doubtful or wrong answer sends
it to review. So if a share e of answers is noisy, roughly 1 - (1 - e)^n of
correct cases go to people. This sweep runs the full chain over HTTP against
the Jev simulator at several noise levels, averaged over seeds, and puts the
measured clean pass rate next to that formula.

It says what reliability a live verifier needs, not what Jev achieves.
"""

import statistics
import threading
from dataclasses import asdict, dataclass
from typing import Any

from typesafe_sdk import RetryPolicy, TypeSafeClient

from clinical_extraction.config import DecisionSettings
from clinical_extraction.decisioning.providers.typesafe import TypeSafeDecisionProvider
from clinical_extraction.decisioning.queries import build_queries
from clinical_extraction.decisioning.router import DecisionRouter, default_routes
from clinical_extraction.decisioning.verifier import CaseVerifier
from clinical_extraction.evals.dataset import EvalExample
from clinical_extraction.evals.decisions import run_decision_eval
from clinical_extraction.evals.jev_simulator import JevSimulator, SimulatorConfig, make_server

DEFAULT_SHARES = (0.005, 0.01, 0.02, 0.05, 0.1)


@dataclass(frozen=True, slots=True)
class ReviewLoadRow:
    noisy_answer_share: float
    expected_clean_pass_rate: float
    clean_pass_rate: float
    defect_detection_recall: float
    false_accept_rate: float


def _run_once(examples: list[EvalExample], config: SimulatorConfig) -> tuple[float, float, float]:
    server = make_server(JevSimulator(examples, config))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        settings = DecisionSettings(_env_file=None, typesafe_api_key="sim", typesafe_base_url=url)
        client = TypeSafeClient(api_key="sim", base_url=url, retry=RetryPolicy(max_retries=0))
        provider = TypeSafeDecisionProvider(settings, client=client)
        router = DecisionRouter(
            {provider.name: provider}, default_routes(primary=provider.name, shadow_local=False)
        )
        summary = run_decision_eval(
            CaseVerifier(router), examples, provider="simulator", requested_model="jev-sim"
        )
    finally:
        server.shutdown()
        server.server_close()
    return summary.clean_pass_rate, summary.defect_detection_recall, summary.false_accept_rate


def sweep(
    examples: list[EvalExample],
    *,
    shares: tuple[float, ...] = DEFAULT_SHARES,
    seeds: int = 20,
) -> dict[str, Any]:
    questions = statistics.mean(len(build_queries(e.expected)) for e in examples)
    rows = []
    for share in shares:
        # Half wrong answers, half hesitant ones: both send a correct case to review.
        runs = [
            _run_once(
                examples,
                SimulatorConfig(
                    error_rate=share / 2,
                    unsure_rate=share / 2,
                    min_latency_ms=0,
                    max_latency_ms=0,
                    seed=seed,
                ),
            )
            for seed in range(seeds)
        ]
        rows.append(
            ReviewLoadRow(
                noisy_answer_share=share,
                expected_clean_pass_rate=round((1 - share) ** questions, 3),
                clean_pass_rate=round(statistics.mean(r[0] for r in runs), 3),
                defect_detection_recall=round(statistics.mean(r[1] for r in runs), 4),
                false_accept_rate=round(statistics.mean(r[2] for r in runs), 4),
            )
        )
    return {
        "simulated": True,
        "questions_per_case": round(questions, 1),
        "seeds": seeds,
        "rows": [asdict(row) for row in rows],
    }
