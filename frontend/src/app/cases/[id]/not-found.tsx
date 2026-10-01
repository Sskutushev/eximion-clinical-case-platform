import Link from "next/link";

export default function CaseNotFound() {
  return (
    <main className="layout">
      <div className="card">
        <h1>Case not found</h1>
        <p>This clinical case does not exist or is no longer available.</p>
        <Link href="/">Back to all cases</Link>
      </div>
    </main>
  );
}
