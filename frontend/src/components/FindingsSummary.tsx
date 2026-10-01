import { CATEGORY_ICON } from "@/components/icons";
import type { Dictionary } from "@/i18n/dictionaries";
import type { FindingCategory, PublicClinicalCase } from "@/lib/api/types";

const ORDER: FindingCategory[] = [
  "history",
  "symptom",
  "vital_sign",
  "physical_exam",
  "laboratory",
  "imaging",
  "other",
];

/**
 * What the case is made of, and how much of it is abnormal.
 *
 * Gives a participant the shape of the case before reading it, and makes an
 * unbalanced case obvious to whoever authored it.
 */
export function FindingsSummary({
  clinicalCase,
  t,
}: {
  clinicalCase: PublicClinicalCase;
  t: Dictionary;
}) {
  const counts = ORDER.map((category) => ({
    category,
    count: clinicalCase.findings.filter((f) => f.category === category).length,
  })).filter((row) => row.count > 0);

  const peak = Math.max(...counts.map((row) => row.count));
  const measurements = clinicalCase.findings.flatMap((f) => f.measurements);
  const abnormal = measurements.filter((m) => m.flag !== "normal").length;

  return (
    <section className="panel panel--tight composition" aria-labelledby="composition-heading">
      <h2 className="section-title" id="composition-heading">
        {t.composition.heading}
      </h2>

      <dl className="stats__figures">
        <div>
          <dt>{t.composition.findings}</dt>
          <dd>{clinicalCase.findings.length}</dd>
        </div>
        <div>
          <dt>{t.composition.measured}</dt>
          <dd>{measurements.length}</dd>
        </div>
        <div>
          <dt>{t.composition.abnormal}</dt>
          <dd className={abnormal > 0 ? "composition__alert" : undefined}>{abnormal}</dd>
        </div>
      </dl>

      <ul className="composition__rows">
        {counts.map(({ category, count }) => {
          const Icon = CATEGORY_ICON[category];
          return (
            <li key={category}>
              <Icon />
              <span className="composition__name">{t.category[category]}</span>
              <span className="composition__track">
                <span
                  className="composition__fill"
                  style={{ width: `${(count / peak) * 100}%` }}
                />
              </span>
              <span className="composition__count">{count}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
