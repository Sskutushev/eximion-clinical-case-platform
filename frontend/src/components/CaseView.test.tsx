import { describe, expect, it } from "vitest";

import { CaseView } from "@/components/CaseView";
import { getDictionary } from "@/i18n/dictionaries";
import type { PublicClinicalCase } from "@/lib/api/types";
import { render, screen } from "@/test/render";

const en = getDictionary("en");
const ru = getDictionary("ru");

const clinicalCase: PublicClinicalCase = {
  id: "6f1a2b3c-0000-4000-8000-000000000002",
  title: "Acute right lower quadrant pain",
  patient_age: 24,
  patient_sex: "male",
  presentation: "Migratory abdominal pain for 18 hours.",
  findings: [
    { category: "laboratory", value: "WBC 14.2 x10^9/L" },
    { category: "symptom", value: "Pain migrating to the right lower quadrant" },
    { category: "symptom", value: "Nausea" },
  ],
  created_at: "2026-10-01T10:00:00Z",
};

describe("CaseView", () => {
  it("renders patient info and groups findings by category in clinical order", () => {
    render(<CaseView clinicalCase={clinicalCase} t={en} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(clinicalCase.title);
    expect(screen.getByText(/Patient:\s*24 years, male/)).toBeInTheDocument();
    expect(screen.getByText(clinicalCase.presentation)).toBeInTheDocument();

    const groups = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(groups).toEqual([en.category.symptom, en.category.laboratory]);
    // 3 findings + 2 category groups + 1 patient chip
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
  });

  it("handles missing demographics", () => {
    render(<CaseView clinicalCase={{ ...clinicalCase, patient_age: null, patient_sex: null }} t={en} />);

    expect(screen.getByText(/Patient:\s*Not specified/)).toBeInTheDocument();
  });

  it("translates the interface but never the clinical content", () => {
    render(<CaseView clinicalCase={clinicalCase} t={ru} />, { locale: "ru" });

    expect(screen.getByRole("heading", { name: ru.case.presentation })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(`${ru.case.patient}:\\s*24 ${ru.case.years}`))).toBeInTheDocument();
    // Clinical text stays exactly as authored — translating a finding would be
    // a clinical claim this system must not make.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(clinicalCase.title);
    expect(screen.getByText(clinicalCase.presentation)).toBeInTheDocument();
    expect(screen.getByText("WBC 14.2 x10^9/L")).toBeInTheDocument();
  });
});
