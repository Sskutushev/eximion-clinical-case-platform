"use client";

import { useEffect } from "react";

import { AlertIcon } from "@/components/icons";
import { useI18n } from "@/i18n/client";

export default function CaseError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useI18n();

  useEffect(() => {
    // The digest ties this to a server log entry; no internals reach the user.
    console.error("case page failed", { digest: error.digest });
  }, [error]);

  return (
    <div className="panel empty" role="alert">
      <AlertIcon />
      <div>
        <h1 className="page-title" style={{ fontSize: "1.5rem" }}>
          {t.case.errorTitle}
        </h1>
        <p className="hint" style={{ marginTop: "0.5rem" }}>
          {t.case.errorBody}
        </p>
      </div>
      <button type="button" className="btn btn--ghost" onClick={reset}>
        {t.case.retry}
      </button>
    </div>
  );
}
