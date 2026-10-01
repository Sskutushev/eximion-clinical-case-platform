import pytest

from app.domain.measurements import MeasurementFlag, parse_measurements


@pytest.mark.parametrize(
    ("text", "label", "value", "flag"),
    [
        ("Heart rate 96/min", "Heart rate", 96.0, MeasurementFlag.NORMAL),
        ("Heart rate 124/min", "Heart rate", 124.0, MeasurementFlag.HIGH),
        ("Heart rate 54/min", "Heart rate", 54.0, MeasurementFlag.LOW),
        ("Temperature 38.1 °C", "Temperature", 38.1, MeasurementFlag.HIGH),
        ("SpO2 91% on room air", "Oxygen saturation", 91.0, MeasurementFlag.LOW),
        ("Venous pH 7.18", "pH", 7.18, MeasurementFlag.LOW),
        ("High-sensitivity troponin T 820 ng/L", "Troponin T", 820.0, MeasurementFlag.HIGH),
        ("Blood pressure 148/92 mmHg", "Systolic blood pressure", 148.0, MeasurementFlag.HIGH),
        ("White cell count 14.2 x10^9/L", "White cell count", 14.2, MeasurementFlag.HIGH),
    ],
)
def test_parses_value_and_flags_against_reference(
    text: str, label: str, value: float, flag: MeasurementFlag
) -> None:
    measurement = next(m for m in parse_measurements(text) if m.label == label)

    assert measurement.value == value
    assert measurement.flag is flag


def test_parses_every_measurement_in_one_finding() -> None:
    found = parse_measurements("Heart rate 118/min, respiratory rate 24/min")

    assert [m.label for m in found] == ["Heart rate", "Respiratory rate"]
    assert [m.value for m in found] == [118.0, 24.0]


@pytest.mark.parametrize(
    "text",
    [
        "Crackles and dullness over the right lower zone",
        "Tenderness at McBurney's point with rebound",
        "",
        "The patient is 24 years old and lives at number 96",
    ],
)
def test_text_without_a_measurement_yields_nothing(text: str) -> None:
    """A bare number in prose must not be plotted as if it were a vital sign."""
    assert parse_measurements(text) == []


def test_position_is_clamped_to_the_axis() -> None:
    off_scale = parse_measurements("Troponin T 99999 ng/L")[0]
    in_range = parse_measurements("Heart rate 80/min")[0]

    assert off_scale.position == 1.0
    assert 0.0 < in_range.position < 1.0


def test_reference_range_is_inclusive_at_the_boundaries() -> None:
    low_edge = parse_measurements("Heart rate 60/min")[0]
    high_edge = parse_measurements("Heart rate 100/min")[0]

    assert low_edge.flag is MeasurementFlag.NORMAL
    assert high_edge.flag is MeasurementFlag.NORMAL
