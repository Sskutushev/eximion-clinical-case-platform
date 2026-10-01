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
 * What the case is made of: how many findings, and of which kind.
 *
 * Counts only. Judging whether a value is abnormal is clinical interpretation,
 * and that belongs to the case author, not to this application.
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
  const categories = counts.length;

  return (
    <section className="panel panel--tight composition" aria-labelledby="composition-heading">
      <h2 className="section-title" id="composition-heading">
        {t.composition.heading}
      </h2>

      <dl className="stats__figures stats__figures--pair">
        <div>
          <dt>{t.composition.findings}</dt>
          <dd>{clinicalCase.findings.length}</dd>
        </div>
        <div>
          <dt>{t.composition.categories}</dt>
          <dd>{categories}</dd>
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
