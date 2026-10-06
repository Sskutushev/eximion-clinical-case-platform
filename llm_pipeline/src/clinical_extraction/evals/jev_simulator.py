"""A local stand-in for the TypeSafe System One API, for end-to-end runs without a key.

It speaks the real wire protocol: POST /v1/systemone with a state and named
questions, answers with labels, probabilities, confidence and token usage. So
everything on our side runs for real: settings, the official SDK, HTTP, retries,
response parsing, routing, the policy and the eval.

What it does not do is think. Answers come from the hand-written ground truth,
with a configurable share of deliberate mistakes and uncertain answers, so the
policy is exercised against an imperfect verifier. Every answer is labelled
with the model name `jev-sim`. Numbers produced against it measure our
pipeline, never Jev.
"""

import hashlib
import json
import logging
import random
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from clinical_extraction.decisioning.schema import DecisionQuery, choice_confidence
from clinical_extraction.decisioning.tasks import NO, TASKS, YES, DecisionTask, TaskKind
from clinical_extraction.evals.dataset import EvalExample
from clinical_extraction.evals.metrics import normalize
from clinical_extraction.schema import ClinicalCaseExtraction, FindingCategory

logger = logging.getLogger(__name__)

SIMULATED_MODEL = "jev-sim"
SYSTEM_ONE_PATH = "/v1/systemone"
# A finding counts as stated when most of its words appear in the source. That
# lets a real extraction split "chest pain and shortness of breath" into two
# findings without either being called invented.
SUPPORT_CONTAINMENT = 0.7

# Which task a question belongs to, recognised by its label set.
_TASK_BY_LABELS = {frozenset(spec.labels): task for task, spec in TASKS.items()}


@dataclass(frozen=True, slots=True)
class SimulatorConfig:
    # Assumptions, not measurements: how often the stand-in answers wrongly or
    # hesitantly. Chosen to exercise the policy, not to predict Jev.
    error_rate: float = 0.05
    unsure_rate: float = 0.05
    min_latency_ms: int = 80
    max_latency_ms: int = 250
    # Every Nth request fails once with 503, to exercise the SDK's retries.
    fail_every: int = 0
    # Changes every random draw; average several seeds for numbers that hold.
    seed: int = 0


def _query_from_question(name: str, question: Mapping[str, Any]) -> DecisionQuery:
    if question.get("type") == "noul":
        task = DecisionTask.DIAGNOSIS_LEAK
    else:
        task = _TASK_BY_LABELS[frozenset(question["criteria"])]
    instructions = question.get("instructions") or {}
    subject = str(
        instructions.get("finding")
        or instructions.get("diagnosis")
        or instructions.get("text")
        or ""
    )
    reference = instructions.get("diagnoses") or instructions.get("extracted_findings") or []
    return DecisionQuery(
        id=name, task=task, target=name, subject=subject, reference=tuple(map(str, reference))
    )


def _words(text: str) -> set[str]:
    return set(normalize(text).replace("/", " ").replace(",", " ").split())


def _containment(part: str, whole: str) -> float:
    """Share of `part`'s words that appear in `whole`, 0..1."""
    words = _words(part)
    return len(words & _words(whole)) / len(words) if words else 0.0


def true_label(query: DecisionQuery, truth: ClinicalCaseExtraction, source: str) -> str:
    """What a careful verifier would answer, from the source text and the ground truth."""
    if query.task is DecisionTask.FINDING_SUPPORT:
        # Stated in the source, or part of a hand-labelled finding (which may
        # itself paraphrase the source).
        stated = _containment(query.subject, source) >= SUPPORT_CONTAINMENT or any(
            _containment(query.subject, f.value) >= SUPPORT_CONTAINMENT for f in truth.findings
        )
        return "supported" if stated else "not_stated"
    if query.task is DecisionTask.FINDING_CATEGORY:
        # The category of the hand-labelled finding this one overlaps most.
        scored = [(_containment(query.subject, f.value), str(f.category)) for f in truth.findings]
        score, category = max(scored, default=(0.0, str(FindingCategory.OTHER)))
        return category if score > 0 else str(FindingCategory.OTHER)
    if query.task is DecisionTask.DIAGNOSIS_STATUS:
        match = next(
            (a for a in truth.answers if normalize(a.text) == normalize(query.subject)), None
        )
        if match is None:
            return "not_stated"
        return "established" if match.is_correct else "differential"
    if query.task is DecisionTask.FINDING_COMPLETENESS:
        # Each hand-labelled finding must be covered by the extracted list as a
        # whole, so one fact split across two findings still counts.
        extracted = " ".join(query.reference)
        covered = all(
            _containment(f.value, extracted) >= SUPPORT_CONTAINMENT for f in truth.findings
        )
        return "complete" if covered else "likely_incomplete"
    leaked = any(normalize(d) in normalize(query.subject) for d in query.reference)
    return YES if leaked else NO


class JevSimulator:
    def __init__(self, examples: list[EvalExample], config: SimulatorConfig | None = None) -> None:
        self._by_source = {normalize(e.raw_text): e for e in examples}
        self._config = config or SimulatorConfig()
        self._requests = 0
        self._lock = threading.Lock()

    def _rng(self, state: str, name: str, question: Mapping[str, Any]) -> random.Random:
        # Seeded by the content, so the same request always gets the same answer.
        digest = hashlib.sha256(
            json.dumps([self._config.seed, state, name, question], sort_keys=True).encode("utf-8")
        ).hexdigest()
        return random.Random(int(digest[:16], 16))  # noqa: S311 - simulation, not security

    def _answer(self, state: str, name: str, question: Mapping[str, Any]) -> dict[str, Any]:
        query = _query_from_question(name, question)
        spec = TASKS[query.task]
        example = self._by_source.get(normalize(state))
        rng = self._rng(state, name, question)
        labels = list(spec.labels)

        label = true_label(query, example.expected, state) if example else str(rng.choice(labels))
        roll = rng.random()
        if roll < self._config.error_rate:
            label = rng.choice([other for other in labels if other != label])
            top = rng.uniform(0.55, 0.85)
        elif roll < self._config.error_rate + self._config.unsure_rate:
            top = rng.uniform(1 / len(labels) + 0.02, 0.6)
        else:
            top = rng.uniform(0.85, 0.99)

        if spec.kind is TaskKind.BINARY:
            yes = top if label == YES else 1 - top
            return {"type": "noul", "noul": round(yes, 4)}
        rest = (1 - top) / (len(labels) - 1)
        probabilities = {name_: (top if name_ == label else rest) for name_ in labels}
        return {
            "type": "choice",
            "choice": label,
            "confidence": choice_confidence(probabilities),
            "probabilities": {k: round(v, 4) for k, v in probabilities.items()},
        }

    def handle(self, body: Mapping[str, Any]) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._requests += 1
            number = self._requests
        if self._config.fail_every and number % self._config.fail_every == 0:
            return 503, {"detail": "simulated outage"}

        state = str(body.get("state", ""))
        questions: Mapping[str, Any] = body.get("questions") or {}
        if not state or not questions:
            return 422, {"detail": "state and questions are required"}
        delay = random.uniform(self._config.min_latency_ms, self._config.max_latency_ms)  # noqa: S311
        time.sleep(delay / 1000)
        answers = {name: self._answer(state, name, q) for name, q in questions.items()}
        return 200, {
            "model": SIMULATED_MODEL,
            "answers": answers,
            # Roughly four characters per token, the usual rule of thumb.
            "usage": {"input_tokens": len(json.dumps(body)) // 4, "output_tokens": len(answers)},
        }


def make_server(simulator: JevSimulator, port: int = 0) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            if self.path != SYSTEM_ONE_PATH:
                self._send(404, {"detail": "not found"})
                return
            if not self.headers.get("Authorization", "").startswith("Bearer "):
                self._send(401, {"detail": "missing API key"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            status, payload = simulator.handle(body)
            self._send(status, payload)

        def _send(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format: str, *args: Any) -> None:
            del format, args  # Keep the console quiet; the eval reports what matters.

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
