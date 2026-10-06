"""Which provider answers which task, and which one runs alongside in shadow.

Migration happens here, one task at a time, by editing a route:

    finding_category: primary=typesafe, shadow=local    (today)
    finding_category: primary=local,    shadow=typesafe (after the gate)
    finding_category: primary=local                     (Jev out of the hot path)

The pipeline and the policy do not change when a route does.
"""

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from clinical_extraction.decisioning.providers.base import DecisionProvider
from clinical_extraction.decisioning.providers.local import LocalDecisionProvider
from clinical_extraction.decisioning.schema import (
    Decision,
    DecisionBatch,
    DecisionQuery,
    RoutedDecisions,
    ShadowComparison,
)
from clinical_extraction.decisioning.tasks import DecisionTask
from clinical_extraction.errors import DecisionError, DecisionProviderError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Route:
    primary: str
    shadow: str | None = None


def default_routes(
    *, primary: str = "typesafe", shadow_local: bool = True
) -> dict[DecisionTask, Route]:
    """Everything on the primary provider; the local model shadows what it can."""
    routes = {task: Route(primary=primary) for task in DecisionTask}
    if shadow_local:
        routes[DecisionTask.FINDING_CATEGORY] = Route(primary=primary, shadow="local")
    return routes


class DecisionRouter:
    def __init__(
        self,
        providers: Mapping[str, DecisionProvider],
        routes: Mapping[DecisionTask, Route],
        *,
        allow_ungated_local: bool = False,
    ) -> None:
        for task, route in routes.items():
            for role, name in (("primary", route.primary), ("shadow", route.shadow)):
                if name is None:
                    continue
                provider = providers.get(name)
                if provider is None:
                    raise ValueError(f"{task}: {role} provider {name!r} is not configured")
                if not provider.supports(task):
                    raise ValueError(f"{task}: {role} provider {name!r} cannot answer it")
            primary = providers[route.primary]
            # Local predictions stay in shadow until the held-out gate is met.
            if (
                isinstance(primary, LocalDecisionProvider)
                and not primary.promotable(task)
                and not allow_ungated_local
            ):
                raise ValueError(f"{task}: the local model has not passed its promotion gate")
        self._providers = dict(providers)
        self._routes = dict(routes)

    @property
    def routes(self) -> Mapping[DecisionTask, Route]:
        return self._routes

    def decide(self, source_text: str, queries: Sequence[DecisionQuery]) -> RoutedDecisions:
        """Ask every primary provider once, then the shadows.

        A primary failure propagates: the caller must not treat an unverified
        candidate as verified. A shadow failure is logged and counted, and never
        changes the outcome.
        """
        batches: list[DecisionBatch] = []
        primary: dict[str, Decision] = {}
        for name, group in self._group(queries, shadow=False).items():
            batch = self._providers[name].decide(source_text, group)
            missing = [q.id for q in group if q.id not in batch.decisions]
            if missing:
                raise DecisionProviderError(f"{name} left {len(missing)} question(s) unanswered")
            batches.append(batch)
            primary.update(batch.decisions)

        shadow: list[ShadowComparison] = []
        shadow_errors = 0
        for name, group in self._group(queries, shadow=True).items():
            try:
                batch = self._providers[name].decide(source_text, group)
            except DecisionError as exc:
                shadow_errors += len(group)
                logger.warning(
                    "shadow provider failed",
                    extra={"provider": name, "error_type": type(exc).__name__},
                )
                continue
            batches.append(batch)
            for query in group:
                decision = batch.decisions.get(query.id)
                if decision is None:
                    shadow_errors += 1
                    continue
                shadow.append(
                    ShadowComparison(
                        query_id=query.id,
                        task=query.task,
                        primary_label=primary[query.id].label,
                        shadow_label=decision.label,
                        shadow_confidence=decision.confidence,
                        shadow_model=decision.model,
                    )
                )
        return RoutedDecisions(
            primary=primary, batches=batches, shadow=shadow, shadow_errors=shadow_errors
        )

    def _group(
        self, queries: Sequence[DecisionQuery], *, shadow: bool
    ) -> dict[str, list[DecisionQuery]]:
        groups: dict[str, list[DecisionQuery]] = defaultdict(list)
        for query in queries:
            route = self._routes.get(query.task)
            if route is None:
                raise ValueError(f"no route for {query.task}")
            name = route.shadow if shadow else route.primary
            if name is not None:
                groups[name].append(query)
        return groups
