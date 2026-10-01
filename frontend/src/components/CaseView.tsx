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

const CATEGORY_ORDER = Object.keys(CATEGORY_LABEL) as FindingCategory[];

function formatPatient(clinicalCase: PublicClinicalCase): string {
  const parts: string[] = [];
  if (clinicalCase.patient_age !== null) parts.push(`${clinicalCase.patient_age} years`);
  if (clinicalCase.patient_sex !== null) parts.push(clinicalCase.patient_sex);
  return parts.length > 0 ? parts.join(", ") : "Not specified";
}

/** Server Component: renders the public case. Nothing here can access the answer key. */
export function CaseView({ clinicalCase }: { clinicalCase: PublicClinicalCase }) {
  const grouped = CATEGORY_ORDER.map((category) => ({
    category,
    items: clinicalCase.findings.filter((f) => f.category === category),
  })).filter((group) => group.items.length > 0);

  return (
    <article className="card">
      <header>
        <h1>{clinicalCase.title}</h1>
        <p className="meta">
          <span>Patient: {formatPatient(clinicalCase)}</span>
        </p>
      </header>

      <section aria-labelledby="presentation-heading">
        <h2 id="presentation-heading">Presentation</h2>
        <p className="presentation">{clinicalCase.presentation}</p>
      </section>

      <section aria-labelledby="findings-heading">
        <h2 id="findings-heading">Findings</h2>
        {grouped.map(({ category, items }) => (
          <div key={category} className="finding-group">
            <h3>{CATEGORY_LABEL[category]}</h3>
            <ul>
              {items.map((finding, index) => (
                <li key={`${category}-${index}`}>{finding.value}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    </article>
  );
}
