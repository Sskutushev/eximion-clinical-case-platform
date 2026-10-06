"""Command line entry points.

python -m clinical_extraction.cli eval --provider fake
python -m clinical_extraction.cli eval --provider gemini
python -m clinical_extraction.cli extract --file case.txt [--verify typesafe]
python -m clinical_extraction.cli eval-decisions --provider reference
python -m clinical_extraction.cli train-local --task finding_category
python -m clinical_extraction.cli eval-local --task finding_category
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from clinical_extraction.config import get_decision_settings, get_extraction_settings
from clinical_extraction.decisioning.policy import PolicyThresholds, VerificationPolicy
from clinical_extraction.decisioning.providers.base import DecisionProvider
from clinical_extraction.decisioning.providers.local import LocalDecisionProvider
from clinical_extraction.decisioning.router import DecisionRouter, default_routes
from clinical_extraction.decisioning.tasks import DecisionTask
from clinical_extraction.decisioning.verifier import CaseVerifier
from clinical_extraction.errors import DecisionError, ExtractionError
from clinical_extraction.evals.dataset import DEFAULT_DATASET, load_dataset
from clinical_extraction.evals.decisions import reference_provider, run_decision_eval
from clinical_extraction.evals.fixtures import build_fixtures
from clinical_extraction.evals.runner import run_eval
from clinical_extraction.extractor import ClinicalCaseExtractor
from clinical_extraction.ml.datasets import finding_category_records
from clinical_extraction.ml.evaluation import evaluate_classifier
from clinical_extraction.ml.model import MODELS_DIR, load_model
from clinical_extraction.ml.records import Split, fingerprint
from clinical_extraction.pipeline import ClinicalExtractionPipeline
from clinical_extraction.providers.base import ExtractionProvider
from clinical_extraction.providers.fake import FakeProvider
from clinical_extraction.providers.gemini import GeminiProvider

# Gates for the offline eval: the fake dataset has 4 known defects out of 10 cases,
# so these thresholds detect a regression in the harness or the contract itself.
FAKE_THRESHOLDS = {"schema_valid_rate": 0.9, "answer_key_accuracy": 0.85, "findings_f1": 0.9}
# The same idea for the decision eval: the reference verifier has two known
# misjudgments, so these catch a regression in the checks or the policy.
REFERENCE_THRESHOLDS = {"defect_detection_recall": 0.95, "clean_pass_rate": 0.85}
LOCAL_TASKS = [DecisionTask.FINDING_CATEGORY.value]


def _build_provider(name: str, examples: list[Any]) -> tuple[ExtractionProvider, int]:
    """Return the provider and the retry budget that goes with it.

    The fake provider has no transient failures to retry and no settings to read,
    so its budget is one attempt. Gemini takes MAX_ATTEMPTS from the environment,
    the same value `extract` uses — one knob, not two.
    """
    if name == "fake":
        return FakeProvider(build_fixtures(examples)), 1
    settings = get_extraction_settings()
    return GeminiProvider(settings), settings.max_attempts


def _write_output(payload: dict[str, Any], output: Path | None) -> None:
    print(json.dumps(payload, indent=2))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _gate(payload: dict[str, Any], thresholds: dict[str, float], name: str) -> int:
    breaches = [
        f"{metric}={payload[metric]} < {threshold}"
        for metric, threshold in thresholds.items()
        if payload[metric] < threshold
    ]
    if breaches:
        print(f"{name} gate failed: " + "; ".join(breaches), file=sys.stderr)
        return 1
    return 0


def _run_eval(args: argparse.Namespace) -> int:
    examples = load_dataset(args.dataset)
    provider, max_attempts = _build_provider(args.provider, examples)
    summary = run_eval(
        provider,
        examples,
        provider_name=args.provider,
        delay_seconds=args.delay,
        max_attempts=max_attempts,
    )
    payload = summary.to_dict()
    _write_output(payload, args.output)
    if args.provider == "fake":
        return _gate(payload, FAKE_THRESHOLDS, "eval")
    return 0


def _typesafe_provider() -> DecisionProvider:
    # Imported here so the SDK only loads when Jev is actually used.
    from clinical_extraction.decisioning.providers.typesafe import (  # noqa: PLC0415
        TypeSafeDecisionProvider,
    )

    return TypeSafeDecisionProvider(get_decision_settings())


def _build_verifier(primary: DecisionProvider, *, shadow_local: bool) -> CaseVerifier:
    providers: dict[str, DecisionProvider] = {primary.name: primary}
    if shadow_local:
        local = LocalDecisionProvider.from_directory()
        shadow_local = local.supports(DecisionTask.FINDING_CATEGORY)
        if shadow_local:
            providers[local.name] = local
    settings = get_decision_settings()
    policy = VerificationPolicy(
        PolicyThresholds(
            min_confidence=settings.min_confidence,
            leak_flag_probability=settings.leak_flag_probability,
        )
    )
    routes = default_routes(primary=primary.name, shadow_local=shadow_local)
    return CaseVerifier(DecisionRouter(providers, routes), policy)


def _run_extract(args: argparse.Namespace) -> int:
    raw_text = args.file.read_text(encoding="utf-8")
    settings = get_extraction_settings()
    extractor = ClinicalCaseExtractor(GeminiProvider(settings), max_attempts=settings.max_attempts)
    try:
        if args.verify == "none":
            payload = extractor.extract(raw_text).to_case_create_payload()
        else:
            verifier = _build_verifier(_typesafe_provider(), shadow_local=not args.no_shadow)
            payload = ClinicalExtractionPipeline(extractor, verifier).run(raw_text).to_dict()
    except (ExtractionError, DecisionError, ValueError) as exc:
        print(f"extraction failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2))
    return 0


def _run_eval_decisions(args: argparse.Namespace) -> int:
    examples = load_dataset(args.dataset)
    usd_per_m_input = 0.0
    if args.provider == "reference":
        primary: DecisionProvider = reference_provider(examples)
    else:
        try:
            primary = _typesafe_provider()
        except DecisionError as exc:
            print(f"cannot start: {exc}", file=sys.stderr)
            return 1
        usd_per_m_input = get_decision_settings().typesafe_usd_per_m_input

    summary = run_decision_eval(
        _build_verifier(primary, shadow_local=not args.no_shadow),
        examples,
        provider=args.provider,
        requested_model=primary.model,
        usd_per_m_input=usd_per_m_input,
        delay_seconds=args.delay,
    )
    payload = summary.to_dict()
    _write_output(payload, args.output)
    if args.provider == "reference":
        return _gate(payload, REFERENCE_THRESHOLDS, "decision eval")
    return 0


def _run_train_local(args: argparse.Namespace) -> int:
    # Training needs the optional ml group; keep it out of every other command.
    from clinical_extraction.ml.train import train_task, write_result  # noqa: PLC0415

    records = finding_category_records(load_dataset(args.dataset))
    result = train_task(DecisionTask(args.task), records)
    directory = write_result(result, args.models_dir)
    print(result.manifest.to_json())
    print(f"model written to {directory}", file=sys.stderr)
    return 0


def _run_eval_local(args: argparse.Namespace) -> int:
    loaded = load_model(args.models_dir / args.task)
    records = [r for r in finding_category_records(load_dataset(args.dataset)) if r.trusted]
    metrics = evaluate_classifier(
        loaded.classifier, [r for r in records if r.split is Split.HELD_OUT]
    )
    payload = {
        "model_version": loaded.manifest.model_version,
        # False means the data changed after training: retrain before trusting it.
        "dataset_matches_manifest": (
            fingerprint(records) == loaded.manifest.dataset["fingerprint"]
        ),
        "gate": {"passed": loaded.manifest.gate.passed, "reasons": loaded.manifest.gate.reasons},
        "held_out": metrics.to_dict(),
    }
    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clinical-extraction")
    subparsers = parser.add_subparsers(dest="command", required=True)

    eval_parser = subparsers.add_parser("eval", help="Score extraction against ground truth")
    eval_parser.add_argument("--provider", choices=["fake", "gemini"], default="fake")
    eval_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    eval_parser.add_argument("--output", type=Path, default=None)
    eval_parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="Seconds between requests. Use ~7 on a free Gemini tier (10 RPM).",
    )
    eval_parser.set_defaults(handler=_run_eval)

    extract_parser = subparsers.add_parser("extract", help="Extract one case from a text file")
    extract_parser.add_argument("--file", type=Path, required=True)
    extract_parser.add_argument(
        "--verify",
        choices=["none", "typesafe"],
        default="none",
        help="Check the extraction with Jev before it goes to review. Off by default.",
    )
    extract_parser.add_argument(
        "--no-shadow", action="store_true", help="Do not run local models in shadow."
    )
    extract_parser.set_defaults(handler=_run_extract)

    decisions_parser = subparsers.add_parser(
        "eval-decisions", help="Measure the verifier on clean and deliberately broken cases"
    )
    decisions_parser.add_argument(
        "--provider", choices=["reference", "typesafe"], default="reference"
    )
    decisions_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    decisions_parser.add_argument("--output", type=Path, default=None)
    decisions_parser.add_argument(
        "--no-shadow", action="store_true", help="Do not run local models in shadow."
    )
    decisions_parser.add_argument(
        "--delay", type=float, default=0.0, help="Seconds between requests."
    )
    decisions_parser.set_defaults(handler=_run_eval_decisions)

    train_parser = subparsers.add_parser("train-local", help="Train a local task model")
    train_parser.add_argument("--task", choices=LOCAL_TASKS, required=True)
    train_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    train_parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    train_parser.set_defaults(handler=_run_train_local)

    local_parser = subparsers.add_parser("eval-local", help="Score a local model on held-out data")
    local_parser.add_argument("--task", choices=LOCAL_TASKS, required=True)
    local_parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    local_parser.add_argument("--models-dir", type=Path, default=MODELS_DIR)
    local_parser.set_defaults(handler=_run_eval_local)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    handler: Any = args.handler
    exit_code: int = handler(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
