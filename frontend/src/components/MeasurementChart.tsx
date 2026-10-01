import type { Dictionary } from "@/i18n/dictionaries";
import type { FindingMeasurement } from "@/lib/api/types";

/**
 * A value plotted against its reference range.
 *
 * Reading a number out of a sentence is slow; seeing it sit outside the normal
 * band is instant. The band is drawn to scale on the axis, the marker sits at
 * the value, and the colour carries the flag.
 *
 * Pure SVG and CSS: a charting library would be a dependency, a bundle and a
 * theming problem for one shape.
 */
export function MeasurementChart({
  measurement,
  t,
}: {
  measurement: FindingMeasurement;
  t: Dictionary;
}) {
  const span = measurement.axis_max - measurement.axis_min;
  const toPercent = (value: number) =>
    span > 0 ? Math.min(Math.max(((value - measurement.axis_min) / span) * 100, 0), 100) : 0;

  const bandStart = toPercent(measurement.reference_low);
  const bandEnd = toPercent(measurement.reference_high);
  const marker = toPercent(measurement.value);

  const formatted = Number.isInteger(measurement.value)
    ? measurement.value.toString()
    : measurement.value.toFixed(measurement.value < 10 ? 2 : 1).replace(/\.?0+$/, "");

  return (
    <figure className={`gauge gauge--${measurement.flag}`}>
      <figcaption className="gauge__head">
        <span className="gauge__label">{measurement.label}</span>
        <span className="gauge__value">
          <strong>{formatted}</strong>
          {measurement.unit ? <span className="gauge__unit">{measurement.unit}</span> : null}
          {measurement.flag !== "normal" ? (
            <span className="gauge__flag">{t.measurement[measurement.flag]}</span>
          ) : null}
        </span>
      </figcaption>

      <div
        className="gauge__track"
        role="img"
        aria-label={`${measurement.label} ${formatted} ${measurement.unit}, ${
          t.measurement[measurement.flag]
        }. ${t.measurement.reference} ${measurement.reference_low}–${measurement.reference_high}`}
      >
        <span
          className="gauge__band"
          style={{ insetInlineStart: `${bandStart}%`, width: `${bandEnd - bandStart}%` }}
        />
        <span className="gauge__marker" style={{ insetInlineStart: `${marker}%` }} />
      </div>

      <div className="gauge__scale" aria-hidden="true">
        <span>{measurement.axis_min}</span>
        <span className="gauge__ref">
          {t.measurement.reference} {measurement.reference_low}–{measurement.reference_high}
        </span>
        <span>{measurement.axis_max}</span>
      </div>
    </figure>
  );
}
