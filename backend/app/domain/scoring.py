"""Answer normalization and scoring. Pure functions: no I/O, no LLM."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.enums import ScoreOutcome

_WHITESPACE = re.compile(r"\s+")
_EDGE_PUNCTUATION = " .,;:!?\"'()[]{}"


def normalize_answer(text: str) -> str:
    """NFKC -> casefold -> collapse whitespace -> strip edge punctuation.

    "  Acute  Appendicitis. " and "acute appendicitis" give the same key.
    Inner punctuation is kept: "type 2 diabetes" != "type-2 diabetes".
    """
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = _WHITESPACE.sub(" ", normalized)
    return normalized.strip(_EDGE_PUNCTUATION)


@dataclass(frozen=True, slots=True)
class AnswerKeyEntry:
    answer_id: int
    normalized_answer: str
    is_correct: bool
    score_weight: int


@dataclass(frozen=True, slots=True)
class ScoreResult:
    normalized_answer: str
    score: int
    max_score: int
    outcome: ScoreOutcome
    matched_answer_id: int | None

    @property
    def is_correct(self) -> bool:
        return self.outcome is ScoreOutcome.CORRECT


def max_score(answer_key: Sequence[AnswerKeyEntry]) -> int:
    return max((a.score_weight for a in answer_key if a.is_correct), default=0)


def score_answer(submitted: str, answer_key: Sequence[AnswerKeyEntry]) -> ScoreResult:
    normalized = normalize_answer(submitted)
    ceiling = max_score(answer_key)
    match = next((a for a in answer_key if a.normalized_answer == normalized), None)

    if match is None:
        return ScoreResult(normalized, 0, ceiling, ScoreOutcome.INCORRECT, None)
    if match.is_correct:
        outcome = ScoreOutcome.CORRECT
    elif match.score_weight > 0:
        outcome = ScoreOutcome.PARTIALLY_CORRECT
    else:
        outcome = ScoreOutcome.INCORRECT
    return ScoreResult(
        normalized, min(match.score_weight, ceiling), ceiling, outcome, match.answer_id
    )
