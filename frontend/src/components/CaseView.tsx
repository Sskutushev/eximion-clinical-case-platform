import { CATEGORY_ICON, UserIcon } from "@/components/icons";
import type { FindingCategory, PublicClinicalCase } from "@/lib/api/types";

const CATEGORY_LABEL: Record<FindingCategory, string> = {
  history: "History",
  symptom: "Symptoms",
  vital_sign: "Vital signs",
  physical_exam: "Physical examination",
  laboratory: "Laboratory",
  imaging: "Imaging",
  other: "Other",
};

/** Clinical reading order, not the order the findings happen to arrive in. */
const CATEGORY_ORDER = Object.keys(CATEGORY_LABEL) as FindingCategory[];

function patientSummary(c: PublicClinicalCase): string {
  const parts: string[] = [];
  if (c.patient_age !== null) parts.push(`${c.patient_age} years`);
  if (c.patient_sex !== null) parts.push(c.patient_sex);
  return parts.length > 0 ? parts.join(", ") : "Not specified";
}

/** Server Component. Nothing here can reach the answer key. */
export function CaseView({ clinicalCase }: { clinicalCase: PublicClinicalCase }) {
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: clinicalCase.findings.filter((f) => f.category === category),
  })).filter((g) => g.items.length > 0);

  return (
    <div className="stack">
      <article className="panel reveal">
        <header>
          <span className="eyebrow">Clinical case</span>
          <h1 className="case-hero__title">{clinicalCase.title}</h1>
          <ul className="chip-row" style={{ marginTop: "0.875rem" }}>
            <li className="chip">
              <UserIcon />
              Patient: {patientSummary(clinicalCase)}
            </li>
          </ul>
        </header>

        <section aria-labelledby="presentation-heading" style={{ marginTop: "1.5rem" }}>
          <h2 className="section-title" id="presentation-heading">
            Presentation
          </h2>
          <p className="presentation">{clinicalCase.presentation}</p>
        </section>
      </article>

      <section className="panel reveal" aria-labelledby="findings-heading">
        <h2 className="section-title" id="findings-heading">
          Findings
        </h2>
        <ul className="findings">
          {groups.map(({ category, items }) => {
            const Icon = CATEGORY_ICON[category];
            return (
              <li key={category} className="finding-group scroll-reveal">
                <h3 className="finding-group__head">
                  <Icon />
                  {CATEGORY_LABEL[category]}
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
