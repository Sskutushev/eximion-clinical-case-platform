"use server";

import { getTranslations } from "@/i18n/server";
import { scoreCase } from "@/lib/api/cases";
import type { ScoreResponse } from "@/lib/api/types";

export type ScoreFormState =
  | { status: "idle" }
  | { status: "success"; result: ScoreResponse; submittedAnswer: string }
  | { status: "error"; message: string };

const MAX_ANSWER_LENGTH = 300;

/**
 * Server Action: the browser posts the form here; the backend call happens on
 * the server. Scoring is never computed client-side.
 */
export async function submitDiagnosis(
  caseId: string,
  _previous: ScoreFormState,
  formData: FormData,
): Promise<ScoreFormState> {
  const { t } = await getTranslations();
  const raw = formData.get("answer");
  const answer = typeof raw === "string" ? raw.trim() : "";

  if (answer.length === 0 || answer.length > MAX_ANSWER_LENGTH) {
    return { status: "error", message: t.form.tooLong };
  }

  const result = await scoreCase(caseId, answer);
  if (result.ok) {
    return { status: "success", result: result.data, submittedAnswer: answer };
  }
  switch (result.kind) {
    case "not_found":
      return { status: "error", message: t.form.gone };
    case "invalid":
      return { status: "error", message: t.form.rejected };
    case "unavailable":
      return { status: "error", message: t.form.unavailable };
  }
}
