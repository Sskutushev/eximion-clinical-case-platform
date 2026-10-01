from hypothesis import given
from hypothesis import strategies as st

from app.domain.enums import ScoreOutcome
from app.domain.scoring import AnswerKeyEntry, normalize_answer, score_answer

KEY = [
    AnswerKeyEntry(1, "acute appendicitis", is_correct=True, score_weight=10),
    AnswerKeyEntry(2, "mesenteric lymphadenitis", is_correct=False, score_weight=3),
    AnswerKeyEntry(3, "gastroenteritis", is_correct=False, score_weight=0),
]


def test_normalization_rules() -> None:
    assert normalize_answer("  Acute\tAppendicitis.\n") == "acute appendicitis"
    assert normalize_answer(chr(0xFF21) + "CUTE") == "acute"  # NFKC full-width
    assert normalize_answer("Straße") == "strasse"  # casefold, not lower
    assert normalize_answer("type-2 diabetes") != normalize_answer("type 2 diabetes")


@given(st.text(max_size=200))
def test_normalization_is_idempotent(text: str) -> None:
    once = normalize_answer(text)
    assert normalize_answer(once) == once


@given(st.text(max_size=200))
def test_score_is_bounded(text: str) -> None:
    result = score_answer(text, KEY)
    assert 0 <= result.score <= result.max_score == 10


def test_zero_weight_match_is_incorrect() -> None:
    result = score_answer("Gastroenteritis", KEY)
    assert (result.score, result.outcome, result.matched_answer_id) == (
        0,
        ScoreOutcome.INCORRECT,
        3,
    )


def test_empty_key_scores_zero() -> None:
    result = score_answer("anything", [])
    assert (result.score, result.max_score, result.is_correct) == (0, 0, False)
