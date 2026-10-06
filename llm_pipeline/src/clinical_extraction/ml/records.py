"""Labelled records: the dataset the local models learn from.

Every record says where its label came from. Only trusted sources are used for
training and evaluation; a provider's prediction, Jev's included, is a weak
label. Training a local model to copy Jev and then calling it good because it
agrees with Jev would measure nothing.
"""

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum


class LabelSource(StrEnum):
    HUMAN_REVIEWED = "human_reviewed"
    SYNTHETIC_GROUND_TRUTH = "synthetic_ground_truth"
    SYNTHETIC_SEED = "synthetic_seed"
    # A model's prediction, kept to find disagreements and prioritise review.
    WEAK_LABEL = "weak_label"


TRUSTED_SOURCES = frozenset(
    {LabelSource.HUMAN_REVIEWED, LabelSource.SYNTHETIC_GROUND_TRUTH, LabelSource.SYNTHETIC_SEED}
)


class Split(StrEnum):
    TRAIN = "train"
    # For choosing thresholds; never trained on, never used for the final score.
    DEV = "dev"
    HELD_OUT = "held_out"


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    record_id: str
    task: str
    task_version: str
    # Every record derived from one vignette shares this id, and the split is
    # made on it, so near-duplicates of one case never sit on both sides.
    case_group_id: str
    text: str
    label: str
    label_source: LabelSource
    split: Split

    @property
    def trusted(self) -> bool:
        return self.label_source in TRUSTED_SOURCES

    def to_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in asdict(self).items()}


def fingerprint(records: Iterable[DecisionRecord]) -> str:
    """Stable hash of a dataset, so a manifest pins exactly what a model saw."""
    lines = sorted(json.dumps(r.to_dict(), sort_keys=True) for r in records)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()
