"""Verify one candidate extraction against its source text."""

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from clinical_extraction.decisioning.policy import (
    ReviewReason,
    ReviewStatus,
    Verdict,
    VerificationPolicy,
)
from clinical_extraction.decisioning.queries import build_queries
from clinical_extraction.decisioning.router import DecisionRouter
from clinical_extraction.decisioning.schema import Decision, ShadowComparison
from clinical_extraction.errors import DecisionError
from clinical_extraction.schema import ClinicalCaseExtraction

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderUsage:
    provider: str
    model: str
    calls: int
    latency_ms: float
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class VerificationReport:
    status: ReviewStatus
    reasons: list[ReviewReason]
    decisions: dict[str, Decision] = field(default_factory=dict)
    shadow: list[ShadowComparison] = field(default_factory=list)
    shadow_errors: int = 0
    usage: list[ProviderUsage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready. Positions, labels and numbers only: safe to store and to log."""
        return {
            "status": self.status,
            "reasons": [
                {
                    "check": r.check,
                    "target": r.target,
                    "verdict": r.verdict,
                    "detail": r.detail,
                    "confidence": r.confidence,
                }
                for r in self.reasons
            ],
            "decisions": {
                query_id: {
                    "label": d.label,
                    "confidence": d.confidence,
                    "provider": d.provider,
                    "model": d.model,
                    "task_version": d.task_version,
                }
                for query_id, d in self.decisions.items()
            },
            "shadow": [
                {
                    "query_id": s.query_id,
                    "primary": s.primary_label,
                    "shadow": s.shadow_label,
                    "shadow_confidence": s.shadow_confidence,
                    "shadow_model": s.shadow_model,
                    "agrees": s.agrees,
                }
                for s in self.shadow
            ],
            "shadow_errors": self.shadow_errors,
            "usage": [
                {
                    "provider": u.provider,
                    "model": u.model,
                    "calls": u.calls,
                    "latency_ms": u.latency_ms,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                }
                for u in self.usage
            ],
        }


class CaseVerifier:
    def __init__(self, router: DecisionRouter, policy: VerificationPolicy | None = None) -> None:
        self._router = router
        self._policy = policy or VerificationPolicy()

    def verify(self, source_text: str, case: ClinicalCaseExtraction) -> VerificationReport:
        queries = build_queries(case)
        try:
            routed = self._router.decide(source_text, queries)
        except DecisionError as exc:
            # Fail closed: no verifier, no automatic acceptance.
            logger.warning("verification unavailable", extra={"error_type": type(exc).__name__})
            return VerificationReport(
                status=ReviewStatus.NEEDS_REVIEW,
                reasons=[
                    ReviewReason(
                        check="verification",
                        target="case",
                        verdict=Verdict.UNAVAILABLE,
                        detail=f"verifier failed: {type(exc).__name__}",
                    )
                ],
            )

        reasons = self._policy.evaluate(case, queries, routed.primary)
        status = ReviewStatus.NEEDS_REVIEW if reasons else ReviewStatus.ACCEPT
        logger.info(
            "verification finished",
            extra={
                "status": status,
                "reasons": dict(Counter(f"{r.check}:{r.verdict}" for r in reasons)),
                "shadow_disagreements": sum(not s.agrees for s in routed.shadow),
            },
        )
        return VerificationReport(
            status=status,
            reasons=reasons,
            decisions=dict(routed.primary),
            shadow=routed.shadow,
            shadow_errors=routed.shadow_errors,
            usage=[
                ProviderUsage(
                    provider=b.provider,
                    model=b.model,
                    calls=b.calls,
                    latency_ms=b.latency_ms,
                    input_tokens=b.input_tokens,
                    output_tokens=b.output_tokens,
                )
                for b in routed.batches
            ],
        )
