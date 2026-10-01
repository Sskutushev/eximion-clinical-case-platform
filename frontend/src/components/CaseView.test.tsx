import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CaseView } from "@/components/CaseView";
import type { PublicClinicalCase } from "@/lib/api/types";

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
    render(<CaseView clinicalCase={clinicalCase} />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(clinicalCase.title);
    expect(screen.getByText("Patient: 24 years, male")).toBeInTheDocument();
    expect(screen.getByText(clinicalCase.presentation)).toBeInTheDocument();

    const groups = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(groups).toEqual(["Symptoms", "Laboratory"]);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });

  it("handles missing demographics", () => {
    render(<CaseView clinicalCase={{ ...clinicalCase, patient_age: null, patient_sex: null }} />);

    expect(screen.getByText("Patient: Not specified")).toBeInTheDocument();
  });
});
