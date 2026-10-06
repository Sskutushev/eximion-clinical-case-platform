"""Our own task models, behind the same contract as Jev.

A task is served here only if a trained artifact exists for it. Anything else
raises instead of quietly asking another provider: which provider answered must
always be visible in the result.
"""

import logging
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

from clinical_extraction.decisioning.schema import (
    Decision,
    DecisionBatch,
    DecisionQuery,
    choice_confidence,
)
from clinical_extraction.decisioning.tasks import TASKS, DecisionTask
from clinical_extraction.errors import UnsupportedDecisionTaskError
from clinical_extraction.ml.model import MANIFEST_FILE, MODELS_DIR, LoadedModel, load_model

logger = logging.getLogger(__name__)


class LocalDecisionProvider:
    def __init__(self, models: Mapping[DecisionTask, LoadedModel]) -> None:
        for task, loaded in models.items():
            if loaded.manifest.task_version != TASKS[task].version:
                raise ValueError(
                    f"{task}: model was trained for {loaded.manifest.task_version}, "
                    f"the task is now {TASKS[task].version}; retrain it"
                )
        self._models = dict(models)

    @classmethod
    def from_directory(cls, directory: Path = MODELS_DIR) -> "LocalDecisionProvider":
        models = {}
        for task in DecisionTask:
            if (directory / task / MANIFEST_FILE).exists():
                models[task] = load_model(directory / task)
        return cls(models)

    @property
    def name(self) -> str:
        return "local"

    @property
    def model(self) -> str:
        versions = sorted(m.manifest.model_version for m in self._models.values())
        return ",".join(versions) or "none"

    def supports(self, task: DecisionTask) -> bool:
        return task in self._models

    def promotable(self, task: DecisionTask) -> bool:
        """Whether the model for this task passed its offline promotion gate."""
        loaded = self._models.get(task)
        return loaded is not None and loaded.manifest.gate.passed

    def decide(self, source_text: str, queries: Sequence[DecisionQuery]) -> DecisionBatch:
        del source_text  # The current local models judge the subject on its own.
        started = time.perf_counter()
        decisions = {}
        for query in queries:
            loaded = self._models.get(query.task)
            if loaded is None:
                raise UnsupportedDecisionTaskError(f"no local model for {query.task}")
            probabilities = loaded.classifier.predict_proba(query.subject)
            decisions[query.id] = Decision(
                query_id=query.id,
                task=query.task,
                label=max(probabilities, key=probabilities.__getitem__),
                probabilities={k: round(v, 6) for k, v in probabilities.items()},
                confidence=choice_confidence(probabilities),
                provider=self.name,
                model=loaded.manifest.model_version,
                task_version=loaded.manifest.task_version,
            )
        return DecisionBatch(
            decisions=decisions,
            provider=self.name,
            model=self.model,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
