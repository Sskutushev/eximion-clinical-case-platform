import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { submitDiagnosis } from "@/app/cases/[id]/actions";
import { CaseView } from "@/components/CaseView";
import { DiagnosisForm } from "@/components/DiagnosisForm";
import { ArrowLeftIcon } from "@/components/icons";
import { getCase } from "@/lib/api/cases";

type Props = { params: Promise<{ id: string }> };

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const result = await getCase(id);
  return { title: result.ok ? result.data.title : "Clinical case" };
}

export default async function CasePage({ params }: Props) {
  const { id } = await params;
  const result = await getCase(id);

  if (!result.ok) {
    if (result.kind === "not_found") notFound();
    // Rendered by error.tsx. The message stays generic; details stay in the logs.
    throw new Error("The case service is currently unavailable.");
  }

  const action = submitDiagnosis.bind(null, result.data.id);

  return (
    <div className="stack">
      <nav aria-label="Breadcrumb">
        <Link href="/" className="back-link">
          <ArrowLeftIcon />
          All cases
        </Link>
      </nav>

      <div className="case-layout">
        <CaseView clinicalCase={result.data} />
        <aside className="case-layout__aside">
          <DiagnosisForm action={action} />
        </aside>
      </div>
    </div>
  );
}
