"""Build task datasets from what the project already has labelled.

Today that is the synthetic eval set (hand-written ground truth) and a small
synthetic seed list. Reviewed production decisions join the same record format
later; nothing downstream has to change when they do.
"""

import hashlib
import json
from pathlib import Path

from clinical_extraction.decisioning.tasks import TASKS, DecisionTask
from clinical_extraction.evals.dataset import EvalExample
from clinical_extraction.ml.records import DecisionRecord, LabelSource, Split

SEED_DIR = Path(__file__).resolve().parents[3] / "training"

# The ten original vignettes keep a hand-picked split: these three cover all
# seven categories, so the held-out score is not blind to any label, and the
# committed model was trained against exactly this split.
HELD_OUT_CASES = frozenset({"case-002", "case-008", "case-009"})
PINNED_TRAIN_CASES = frozenset(f"case-{n:03d}" for n in range(1, 11)) - HELD_OUT_CASES

# Every other case group, such as human-reviewed production cases, is split by
# a stable hash of its id: 20% held-out, 10% dev, 70% train. The held-out set
# then grows with the data instead of staying at three vignettes, and a case
# never changes sides when more data arrives.
HELD_OUT_BUCKETS = frozenset({0, 1})
DEV_BUCKETS = frozenset({2})


def split_for(case_group_id: str) -> Split:
    if case_group_id in HELD_OUT_CASES:
        return Split.HELD_OUT
    if case_group_id in PINNED_TRAIN_CASES:
        return Split.TRAIN
    bucket = int(hashlib.sha256(case_group_id.encode("utf-8")).hexdigest(), 16) % 10
    if bucket in HELD_OUT_BUCKETS:
        return Split.HELD_OUT
    if bucket in DEV_BUCKETS:
        return Split.DEV
    return Split.TRAIN


def finding_category_records(
    examples: list[EvalExample], seed_path: Path | None = None
) -> list[DecisionRecord]:
    task_version = TASKS[DecisionTask.FINDING_CATEGORY].version
    records = [
        DecisionRecord(
            record_id=f"{example.id}/findings/{index}",
            task=DecisionTask.FINDING_CATEGORY,
            task_version=task_version,
            case_group_id=example.id,
            text=finding.value,
            label=str(finding.category),
            label_source=LabelSource.SYNTHETIC_GROUND_TRUTH,
            split=split_for(example.id),
        )
        for example in examples
        for index, finding in enumerate(example.expected.findings)
    ]

    path = seed_path or SEED_DIR / "finding_category_seed.jsonl"
    labels = TASKS[DecisionTask.FINDING_CATEGORY].labels
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row["label"] not in labels:
                raise ValueError(f"{path.name}:{line_number} unknown label {row['label']!r}")
            # Seed phrases are standalone, not taken from any vignette, so they
            # only ever train; scoring on them would flatter the model.
            records.append(
                DecisionRecord(
                    record_id=row["id"],
                    task=DecisionTask.FINDING_CATEGORY,
                    task_version=task_version,
                    case_group_id=row["id"],
                    text=row["text"],
                    label=row["label"],
                    label_source=LabelSource.SYNTHETIC_SEED,
                    split=Split.TRAIN,
                )
            )
    return records
