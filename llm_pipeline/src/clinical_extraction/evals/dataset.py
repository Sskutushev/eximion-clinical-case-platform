import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clinical_extraction.schema import ClinicalCaseExtraction

DEFAULT_DATASET = Path(__file__).resolve().parents[3] / "evals" / "dataset.jsonl"


@dataclass(frozen=True, slots=True)
class EvalExample:
    """One labelled example: raw text plus the hand-written ground truth."""

    id: str
    raw_text: str
    expected: ClinicalCaseExtraction


def load_dataset(path: Path | None = None) -> list[EvalExample]:
    dataset_path = path or DEFAULT_DATASET
    examples: list[EvalExample] = []
    seen: set[str] = set()

    with dataset_path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record: dict[str, Any] = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset_path}:{line_number} is not valid JSON") from exc

            example_id = record["id"]
            if example_id in seen:
                raise ValueError(f"{dataset_path}:{line_number} duplicate example id {example_id}")
            seen.add(example_id)
            # Ground truth is validated with the same contract as model output.
            examples.append(
                EvalExample(
                    id=example_id,
                    raw_text=record["raw_text"],
                    expected=ClinicalCaseExtraction.model_validate(record["expected"]),
                )
            )

    if not examples:
        raise ValueError(f"{dataset_path} contains no examples")
    return examples
