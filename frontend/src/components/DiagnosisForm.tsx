"use client";

import { useActionState, useId } from "react";

import type { ScoreFormState } from "@/app/cases/[id]/actions";
import { ScoreResult } from "@/components/ScoreResult";

type DiagnosisAction = (state: ScoreFormState, formData: FormData) => Promise<ScoreFormState>;

const INITIAL: ScoreFormState = { status: "idle" };

export function DiagnosisForm({ action }: { action: DiagnosisAction }) {
  const [state, formAction, pending] = useActionState(action, INITIAL);
  const inputId = useId();
  const hintId = useId();
  const errorId = useId();
  const hasError = state.status === "error";

  return (
    <section className="card" aria-labelledby={`${inputId}-heading`}>
      <h2 id={`${inputId}-heading`}>Your diagnosis</h2>
      <form action={formAction} className="diagnosis-form" noValidate>
        <label htmlFor={inputId}>Most likely diagnosis</label>
        <input
          id={inputId}
          name="answer"
          type="text"
          required
          maxLength={300}
          autoComplete="off"
          disabled={pending}
          aria-describedby={hasError ? `${hintId} ${errorId}` : hintId}
          aria-invalid={hasError || undefined}
        />
        <p id={hintId} className="hint">
          Free text, e.g. “Acute appendicitis”. Case and punctuation do not matter.
        </p>
        {hasError ? (
          <p id={errorId} role="alert" className="error">
            {state.message}
          </p>
        ) : null}
        <button type="submit" disabled={pending} aria-busy={pending}>
          {pending ? "Scoring…" : "Submit diagnosis"}
        </button>
      </form>

      <div aria-live="polite">
        {state.status === "success" ? (
          <ScoreResult result={state.result} submittedAnswer={state.submittedAnswer} />
        ) : null}
      </div>
    </section>
  );
}
