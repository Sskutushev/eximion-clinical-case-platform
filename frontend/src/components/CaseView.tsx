import { CATEGORY_ICON, UserIcon } from "@/components/icons";
import type { Dictionary } from "@/i18n/dictionaries";
import type { FindingCategory, PublicClinicalCase } from "@/lib/api/types";

/** Clinical reading order, not the order the findings happen to arrive in. */
const CATEGORY_ORDER: FindingCategory[] = [
  "history",
  "symptom",
  "vital_sign",
  "physical_exam",
  "laboratory",
  "imaging",
  "other",
];

function patientSummary(c: PublicClinicalCase, t: Dictionary): string {
  const parts: string[] = [];
  if (c.patient_age !== null) parts.push(`${c.patient_age} ${t.case.years}`);
  if (c.patient_sex !== null) parts.push(t.sex[c.patient_sex]);
  return parts.length > 0 ? parts.join(", ") : t.case.notSpecified;
}

/** Server Component. Nothing here can reach the answer key. */
export function CaseView({
  clinicalCase,
  t,
}: {
  clinicalCase: PublicClinicalCase;
  t: Dictionary;
}) {
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: clinicalCase.findings.filter((f) => f.category === category),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="stack">
      <article className="panel reveal">
        <header>
          <span className="eyebrow">{t.case.eyebrow}</span>
          <h1 className="case-hero__title">{clinicalCase.title}</h1>
          <ul className="chip-row" style={{ marginTop: "0.875rem" }}>
            <li className="chip">
              <UserIcon />
              {t.case.patient}: {patientSummary(clinicalCase, t)}
            </li>
          </ul>
        </header>

        <section aria-labelledby="presentation-heading" style={{ marginTop: "1.5rem" }}>
          <h2 className="section-title" id="presentation-heading">
            {t.case.presentation}
          </h2>
          <p className="presentation">{clinicalCase.presentation}</p>
        </section>
      </article>

      <section className="panel reveal" aria-labelledby="findings-heading">
        <h2 className="section-title" id="findings-heading">
          {t.case.findings}
        </h2>
        <ul className="findings">
          {groups.map(({ category, items }) => {
            const Icon = CATEGORY_ICON[category];
            return (
              <li key={category} className="finding-group scroll-reveal">
                <h3 className="finding-group__head">
                  <Icon />
                  {t.category[category]}
                </h3>
                <ul className="finding-list">
                  {items.map((finding, index) => (
                    <li key={`${category}-${index}`}>{finding.value}</li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      </section>
    </div>
  );
}
