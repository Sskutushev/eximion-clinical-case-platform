"use client";

import { useEffect } from "react";

export default function CaseError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Digest correlates with the server-side log entry; no internals reach the user.
    console.error("case page failed", { digest: error.digest });
  }, [error]);

  return (
    <main className="layout">
      <div className="card" role="alert">
        <h1>Something went wrong</h1>
        <p>The case could not be loaded right now.</p>
        <button type="button" onClick={reset}>
          Try again
        </button>
      </div>
    </main>
  );
}
