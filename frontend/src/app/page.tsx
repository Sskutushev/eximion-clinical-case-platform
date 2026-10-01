import Link from "next/link";
import type { CSSProperties } from "react";

import { TiltCard } from "@/components/TiltCard";
import { AlertIcon, ArrowRightIcon, InboxIcon } from "@/components/icons";
import { listCases } from "@/lib/api/cases";

export const dynamic = "force-dynamic";

const dateFormat = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export default async function HomePage() {
  const result = await listCases();

  return (
    <div className="stack">
      <header className="reveal">
        <span className="eyebrow">Case library</span>
        <h1 className="page-title">Clinical cases</h1>
        <p className="page-lede">
          Read the presentation, weigh the findings, commit to a diagnosis. Scoring is
          instant and the same every time.
        </p>
      </header>

      {!result.ok ? (
        <div className="notice" role="alert">
          <AlertIcon />
          <div>
            <strong>Cases are unavailable right now.</strong>
            <p className="hint" style={{ marginTop: "0.25rem" }}>
              The case service did not respond. Please try again shortly.
            </p>
          </div>
        </div>
      ) : result.data.items.length === 0 ? (
        <div className="panel empty">
          <InboxIcon />
          <p>
            No cases yet. Create one with <code>POST /api/v1/cases</code> or run{" "}
            <code>make seed</code>.
          </p>
        </div>
      ) : (
        <ul className="case-grid">
          {result.data.items.map((item, index) => (
            <li key={item.id} className="reveal" style={{ "--i": index } as CSSProperties}>
              <TiltCard className="tilt">
                <Link href={`/cases/${item.id}`} className="case-card">
                  <span className="case-card__spot" aria-hidden="true" />
                  <h2 className="case-card__title">{item.title}</h2>
                  <div className="case-card__foot">
                    <time dateTime={item.created_at}>
                      {dateFormat.format(new Date(item.created_at))}
                    </time>
                    <span className="case-card__cta">
                      Solve <ArrowRightIcon />
                    </span>
                  </div>
                </Link>
              </TiltCard>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
