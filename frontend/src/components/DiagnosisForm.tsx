"use client";

import { useActionState, useId } from "react";

import type { ScoreFormState } from "@/app/cases/[id]/actions";
import { ScoreResult } from "@/components/ScoreResult";
import { AlertIcon, StethoscopeIcon } from "@/components/icons";

type DiagnosisAction = (state: ScoreFormState, formData: FormData) => Promise<ScoreFormState>;

const INITIAL: ScoreFormState = { status: "idle" };

export function DiagnosisForm({ action }: { action: DiagnosisAction }) {
  const [state, formAction, pending] = useActionState(action, INITIAL);
  const inputId = useId();
  const hintId = useId();
  const errorId = useId();
  const hasError = state.status === "error";

  return (
    <section className="panel" aria-labelledby={`${inputId}-heading`}>
      <span className="eyebrow">Your answer</span>
      <h2 className="section-title" id={`${inputId}-heading`}>
        Your diagnosis
      </h2>

      <form action={formAction} className="form" noValidate>
        <label className="form__label" htmlFor={inputId}>
          Most likely diagnosis
        </label>

        <div className="field">
          <StethoscopeIcon className="field__icon" />
          <input
            id={inputId}
            name="answer"
            type="text"
            required
            maxLength={300}
            autoComplete="off"
            placeholder="Type a diagnosis…"
            disabled={pending}
            aria-describedby={hasError ? `${hintId} ${errorId}` : hintId}
            aria-invalid={hasError || undefined}
          />
        </div>

        <p className="hint" id={hintId}>
          Free text. Capitalisation, extra spaces and trailing punctuation do not matter.
        </p>

        {hasError ? (
          <p className="form__error" id={errorId} role="alert">
            <AlertIcon />
            {state.message}
          </p>
        ) : null}

        <button type="submit" className="btn" disabled={pending} aria-busy={pending}>
          {pending ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Scoring…
            </>
          ) : (
            "Submit diagnosis"
          )}
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
