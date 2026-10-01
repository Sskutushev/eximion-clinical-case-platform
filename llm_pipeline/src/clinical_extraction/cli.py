"""Command line entry points.

python -m clinical_extraction.cli eval --provider fake
python -m clinical_extraction.cli eval --provider gemini
python -m clinical_extraction.cli extract --file case.txt
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from clinical_extraction.config import get_extraction_settings
from clinical_extraction.errors import ExtractionError
from clinical_extraction.evals.dataset import DEFAULT_DATASET, load_dataset
from clinical_extraction.evals.fixtures import build_fixtures
from clinical_extraction.evals.runner import run_eval
from clinical_extraction.extractor import ClinicalCaseExtractor
from clinical_extraction.providers.base import ExtractionProvider
from clinical_extraction.providers.fake import FakeProvider
from clinical_extraction.providers.gemini import GeminiProvider

# Gates for the offline eval: the fake dataset has 4 known defects out of 10 cases,
# so these thresholds detect a regression in the harness or the contract itself.
FAKE_THRESHOLDS = {"schema_valid_rate": 0.9, "answer_key_accuracy": 0.85, "findings_f1": 0.9}


def _build_provider(name: str, examples: list[Any]) -> ExtractionProvider:
    if name == "fake":
        return FakeProvider(build_fixtures(examples))
    return GeminiProvider(get_extraction_settings())


def _run_eval(args: argparse.Namespace) -> int:
    examples = load_dataset(args.dataset)
    provider = _build_provider(args.provider, examples)
    summary = run_eval(provider, examples, provider_name=args.provider, delay_seconds=args.delay)
    payload = summary.to_dict()

    print(json.dumps(payload, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if args.provider == "fake":
        breaches = [
            f"{metric}={payload[metric]} < {threshold}"
            for metric, threshold in FAKE_THRESHOLDS.items()
            if payload[metric] < threshold
        ]
        if breaches:
            print("eval gate failed: " + "; ".join(breaches), file=sys.stderr)
            return 1
    return 0


def _run_extract(args: argparse.Namespace) -> int:
    raw_text = args.file.read_text(encoding="utf-8")
    settings = get_extraction_settings()
    extractor = ClinicalCaseExtractor(GeminiProvider(settings), max_attempts=settings.max_attempts)
    try:
        result = extractor.extract(raw_text)
    except (ExtractionError, ValueError) as exc:
        print(f"extraction failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result.to_case_create_payload(), indent=2))
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
    extract_parser.set_defaults(handler=_run_extract)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    args = build_parser().parse_args(argv)
    handler: Any = args.handler
    exit_code: int = handler(args)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
