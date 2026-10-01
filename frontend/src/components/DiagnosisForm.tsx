"use client";

import { useActionState, useId } from "react";

import type { ScoreFormState } from "@/app/cases/[id]/actions";
import { ScoreResult } from "@/components/ScoreResult";
import { AlertIcon, StethoscopeIcon } from "@/components/icons";
import { useI18n } from "@/i18n/client";

type DiagnosisAction = (state: ScoreFormState, formData: FormData) => Promise<ScoreFormState>;

const INITIAL: ScoreFormState = { status: "idle" };

export function DiagnosisForm({ action }: { action: DiagnosisAction }) {
  const { t } = useI18n();
  const [state, formAction, pending] = useActionState(action, INITIAL);
  const inputId = useId();
  const hintId = useId();
  const errorId = useId();
  const hasError = state.status === "error";

  return (
    <section className="panel reveal" aria-labelledby={`${inputId}-heading`}>
      <span className="eyebrow">{t.form.eyebrow}</span>
      <h2 className="section-title" id={`${inputId}-heading`}>
        {t.form.heading}
      </h2>

      <form action={formAction} className="form" noValidate>
        <label className="form__label" htmlFor={inputId}>
          {t.form.label}
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
            placeholder={t.form.placeholder}
            disabled={pending}
            aria-describedby={hasError ? `${hintId} ${errorId}` : hintId}
            aria-invalid={hasError || undefined}
          />
        </div>

        <p className="hint" id={hintId}>
          {t.form.hint}
        </p>

        {hasError ? (
          <p className="form__error" id={errorId} role="alert">
            <AlertIcon />
            {state.message}
          </p>
        ) : null}

        <button type="submit" className="btn btn--shine" disabled={pending} aria-busy={pending}>
          {pending ? (
            <>
              <span className="spinner" aria-hidden="true" />
              {t.form.pending}
            </>
          ) : (
            t.form.submit
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
