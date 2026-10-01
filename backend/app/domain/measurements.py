"""Turn a finding's text into a plottable measurement, where one is present.

The text stays the source of truth. This adds an optional, derived annotation so
the interface can show a value against its reference range instead of a number
in a sentence. Anything this cannot parse confidently is left alone.

Reference ranges are adult values, deliberately conservative, and are shown as
context for a teaching case — not as a clinical decision aid.
"""

import re
from dataclasses import dataclass
from enum import StrEnum


class MeasurementFlag(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class ReferenceRange:
    label: str
    unit: str
    low: float
    high: float
    # Axis bounds for plotting, so a wildly abnormal value stays on the chart.
    axis_min: float
    axis_max: float


@dataclass(frozen=True, slots=True)
class Measurement:
    label: str
    value: float
    unit: str
    reference_low: float
    reference_high: float
    axis_min: float
    axis_max: float
    flag: MeasurementFlag

    @property
    def position(self) -> float:
        """Where the value sits on the axis, 0..1, clamped to the ends."""
        span = self.axis_max - self.axis_min
        if span <= 0:
            return 0.0
        return min(max((self.value - self.axis_min) / span, 0.0), 1.0)


# label -> (regex over the finding text, reference range)
# Each pattern anchors on the measurement name so "heart rate 96" is matched but
# a bare "96" in prose is not.
_PATTERNS: list[tuple[re.Pattern[str], ReferenceRange]] = [
    (
        re.compile(r"\b(?:heart rate|pulse|hr)\b[^0-9]{0,12}(\d{2,3})", re.I),
        ReferenceRange("Heart rate", "/min", 60, 100, 30, 180),
    ),
    (
        re.compile(r"\b(?:respiratory rate|rr)\b[^0-9]{0,12}(\d{1,2})", re.I),
        ReferenceRange("Respiratory rate", "/min", 12, 20, 6, 40),
    ),
    (
        re.compile(r"\btemperature\b[^0-9]{0,12}(\d{2}(?:\.\d)?)\s*(?:°\s*)?C", re.I),
        ReferenceRange("Temperature", "°C", 36.1, 37.5, 34.0, 41.0),
    ),
    (
        re.compile(r"\b(?:spo2|oxygen saturation|o2 sat)\b[^0-9]{0,12}(\d{2,3})\s*%", re.I),
        ReferenceRange("Oxygen saturation", "%", 95, 100, 70, 100),
    ),
    (
        re.compile(r"\b(?:blood pressure|bp)\b[^0-9]{0,12}(\d{2,3})\s*/\s*\d{2,3}", re.I),
        ReferenceRange("Systolic blood pressure", "mmHg", 90, 130, 60, 220),
    ),
    (
        re.compile(r"\b(?:white cell count|wbc)\b[^0-9]{0,12}(\d{1,3}(?:\.\d)?)\s*x10\^9", re.I),
        ReferenceRange("White cell count", "x10^9/L", 4.0, 11.0, 0.0, 30.0),
    ),
    (
        re.compile(r"\bcrp\b[^0-9]{0,12}(\d{1,3})\s*mg/L", re.I),
        ReferenceRange("CRP", "mg/L", 0, 5, 0, 300),
    ),
    (
        re.compile(r"\btroponin[^0-9]{0,24}?(\d{1,5})\s*ng/L", re.I),
        ReferenceRange("Troponin T", "ng/L", 0, 14, 0, 1000),
    ),
    (
        re.compile(r"\b(?:capillary )?glucose\b[^0-9]{0,12}(\d{1,2}(?:\.\d)?)\s*mmol/L", re.I),
        ReferenceRange("Glucose", "mmol/L", 3.9, 7.8, 0.0, 35.0),
    ),
    (
        re.compile(r"\b(?:venous )?pH\b[^0-9]{0,12}(\d\.\d{1,2})"),
        ReferenceRange("pH", "", 7.35, 7.45, 6.9, 7.7),
    ),
    (
        re.compile(r"\bbicarbonate\b[^0-9]{0,12}(\d{1,2})\s*mmol/L", re.I),
        ReferenceRange("Bicarbonate", "mmol/L", 22, 29, 0, 45),
    ),
    (
        re.compile(r"\b(?:serum )?ketones\b[^0-9]{0,12}(\d{1,2}(?:\.\d)?)\s*mmol/L", re.I),
        ReferenceRange("Ketones", "mmol/L", 0.0, 0.6, 0.0, 8.0),
    ),
    (
        re.compile(r"\b(?:serum )?lipase\b[^0-9]{0,12}(\d{2,5})\s*U/L", re.I),
        ReferenceRange("Lipase", "U/L", 13, 60, 0, 2000),
    ),
    (
        re.compile(r"\balt\b[^0-9]{0,12}(\d{1,4})\s*U/L", re.I),
        ReferenceRange("ALT", "U/L", 7, 40, 0, 400),
    ),
    (
        re.compile(r"\bd-dimer\b[^0-9]{0,12}(\d{2,6})\s*ng/mL", re.I),
        ReferenceRange("D-dimer", "ng/mL", 0, 500, 0, 5000),
    ),
    (
        re.compile(r"\btsh\b[^0-9]{0,12}(\d{1,3}(?:\.\d)?)\s*mIU/L", re.I),
        ReferenceRange("TSH", "mIU/L", 0.4, 4.0, 0.0, 30.0),
    ),
    (
        re.compile(r"\bfree t4\b[^0-9]{0,12}(\d{1,3}(?:\.\d)?)\s*pmol/L", re.I),
        ReferenceRange("Free T4", "pmol/L", 12.0, 22.0, 0.0, 40.0),
    ),
    (
        re.compile(r"\bbilirubin\b[^0-9]{0,12}(\d{1,4})\s*µmol/L", re.I),
        ReferenceRange("Bilirubin", "µmol/L", 0, 21, 0, 200),
    ),
]


def _flag(value: float, ref: ReferenceRange) -> MeasurementFlag:
    if value < ref.low:
        return MeasurementFlag.LOW
    if value > ref.high:
        return MeasurementFlag.HIGH
    return MeasurementFlag.NORMAL


def parse_measurements(text: str) -> list[Measurement]:
    """Every measurement in the text, in pattern order.

    One finding often carries two, as in "Heart rate 118/min, respiratory rate
    24/min". Returns an empty list when there is nothing to plot.
    """
    found: list[Measurement] = []
    for pattern, ref in _PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        try:
            value = float(match.group(1))
        except ValueError:  # pragma: no cover - the patterns only capture numbers
            continue
        found.append(
            Measurement(
                label=ref.label,
                value=value,
                unit=ref.unit,
                reference_low=ref.low,
                reference_high=ref.high,
                axis_min=ref.axis_min,
                axis_max=ref.axis_max,
                flag=_flag(value, ref),
            )
        )
    return found
