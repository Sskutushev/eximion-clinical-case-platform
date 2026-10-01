import Link from "next/link";

import { listCases } from "@/lib/api/cases";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const result = await listCases();

  return (
    <main className="layout">
      <div className="card">
        <h1>Clinical cases</h1>
        {!result.ok ? (
          <p role="alert" className="error">
            Cases are temporarily unavailable. Please try again shortly.
          </p>
        ) : result.data.items.length === 0 ? (
          <p>No cases yet. Create one through the API to get started.</p>
        ) : (
          <ul className="case-list">
            {result.data.items.map((item) => (
              <li key={item.id}>
                <Link href={`/cases/${item.id}`}>{item.title}</Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
