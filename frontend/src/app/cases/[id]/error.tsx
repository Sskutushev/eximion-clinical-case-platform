"use client";

import { useEffect } from "react";

import { AlertIcon } from "@/components/icons";

export default function CaseError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // The digest ties this to a server log entry; no internals reach the user.
    console.error("case page failed", { digest: error.digest });
  }, [error]);

  return (
    <div className="panel empty" role="alert">
      <AlertIcon />
      <div>
        <h1 className="page-title" style={{ fontSize: "1.5rem" }}>
          Something went wrong
        </h1>
        <p className="hint" style={{ marginTop: "0.5rem" }}>
          The case could not be loaded right now.
        </p>
      </div>
      <button type="button" className="btn btn--ghost" onClick={reset}>
        Try again
      </button>
    </div>
  );
}
