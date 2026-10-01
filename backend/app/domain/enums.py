from enum import StrEnum


class FindingCategory(StrEnum):
    HISTORY = "history"
    SYMPTOM = "symptom"
    VITAL_SIGN = "vital_sign"
    PHYSICAL_EXAM = "physical_exam"
    LABORATORY = "laboratory"
    IMAGING = "imaging"
    OTHER = "other"


class PatientSex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


class ScoreOutcome(StrEnum):
    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially_correct"
    INCORRECT = "incorrect"
