"""The bounded questions the decision layer asks about an extraction.

One definition per task, shared by every provider: Jev answers these today, a
local model answers the same labels later, and a reviewer labels data against
the same descriptions. If the meaning of a label changes, bump the version, so
old predictions and old training records are never mixed with new ones.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from clinical_extraction.schema import FindingCategory


class DecisionTask(StrEnum):
    FINDING_SUPPORT = "finding_support"
    FINDING_CATEGORY = "finding_category"
    DIAGNOSIS_STATUS = "diagnosis_status"
    DIAGNOSIS_LEAK = "diagnosis_leak"


class TaskKind(StrEnum):
    CHOICE = "choice"
    BINARY = "binary"


YES = "yes"
NO = "no"


@dataclass(frozen=True, slots=True)
class TaskSpec:
    task: DecisionTask
    kind: TaskKind
    version: str
    question: str
    labels: Mapping[str, str]


def _frozen(labels: dict[str, str]) -> Mapping[str, str]:
    # StrEnum keys become plain strings, so labels serialise the same way everywhere.
    return MappingProxyType({str(label): text for label, text in labels.items()})


TASKS: Mapping[DecisionTask, TaskSpec] = MappingProxyType(
    {
        DecisionTask.FINDING_SUPPORT: TaskSpec(
            task=DecisionTask.FINDING_SUPPORT,
            kind=TaskKind.CHOICE,
            version="finding-support-v1",
            question="How does the source clinical text relate to this extracted finding?",
            labels=_frozen(
                {
                    "supported": "The source text states this finding, possibly in other words.",
                    "contradicted": "The source text states something that conflicts with it.",
                    "not_stated": "The source text does not mention this finding at all.",
                }
            ),
        ),
        DecisionTask.FINDING_CATEGORY: TaskSpec(
            task=DecisionTask.FINDING_CATEGORY,
            kind=TaskKind.CHOICE,
            version="finding-category-v1",
            question="Which clinical category does this finding belong to?",
            labels=_frozen(
                {
                    FindingCategory.HISTORY: "Past or background history, medication, exposure.",
                    FindingCategory.SYMPTOM: "A complaint the patient reports.",
                    FindingCategory.VITAL_SIGN: "A measured vital: temperature, pulse, BP, SpO2.",
                    FindingCategory.PHYSICAL_EXAM: "A sign found on examination.",
                    FindingCategory.LABORATORY: "A blood, urine or other laboratory result.",
                    FindingCategory.IMAGING: "A radiology, ultrasound or ECG report.",
                    FindingCategory.OTHER: "None of the categories above.",
                }
            ),
        ),
        DecisionTask.DIAGNOSIS_STATUS: TaskSpec(
            task=DecisionTask.DIAGNOSIS_STATUS,
            kind=TaskKind.CHOICE,
            version="diagnosis-status-v1",
            question="What does the source clinical text say about this diagnosis?",
            labels=_frozen(
                {
                    "established": "The text presents it as the confirmed or final diagnosis.",
                    "differential": "The text lists it as considered or a differential.",
                    "excluded": "The text says it was ruled out.",
                    "not_stated": "The text does not name it, or its status is unclear.",
                }
            ),
        ),
        DecisionTask.DIAGNOSIS_LEAK: TaskSpec(
            task=DecisionTask.DIAGNOSIS_LEAK,
            kind=TaskKind.BINARY,
            version="diagnosis-leak-v1",
            question=(
                "Does this text name any of the listed diagnoses, or give one away "
                "so plainly that a reader would not need to work it out?"
            ),
            labels=_frozen(
                {
                    YES: "The text names or plainly reveals a listed diagnosis.",
                    NO: "The text describes the problem without revealing the diagnosis.",
                }
            ),
        ),
    }
)

# What a diagnosis status implies for `AnswerExtraction.is_correct`.
ESTABLISHED = "established"
