"""How an extracted answer becomes a scored one.

The model is not asked how many points a differential is worth. Judging that a
diagnosis is "clinically close" and therefore worth three points is a clinical
judgement, and nothing in the source text supports it — so the model would be
inventing it.

These are product defaults, applied after extraction. An editor reviewing the
case can change them, and the decision is visible in one place rather than
buried in a prompt.
"""

ESTABLISHED_DIAGNOSIS_WEIGHT = 10
DIFFERENTIAL_WEIGHT = 0


def weight_for(is_correct: bool) -> int:  # noqa: FBT001
    """Points for an extracted answer.

    A differential starts at zero: partial credit is a decision about how a
    competition is scored, and an author should make it deliberately rather
    than inherit it from an extraction run.
    """
    return ESTABLISHED_DIAGNOSIS_WEIGHT if is_correct else DIFFERENTIAL_WEIGHT
