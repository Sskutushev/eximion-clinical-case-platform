import Link from "next/link";
import type { CSSProperties } from "react";

import { TiltCard } from "@/components/TiltCard";
import { AlertIcon, ArrowRightIcon, InboxIcon } from "@/components/icons";
import { getTranslations } from "@/i18n/server";
import { listCases } from "@/lib/api/cases";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [{ locale, t }, result] = await Promise.all([getTranslations(), listCases()]);
  const dateFormat = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });

  return (
    <div className="stack">
      <header className="reveal">
        <span className="eyebrow">{t.home.eyebrow}</span>
        <h1 className="page-title">{t.home.title}</h1>
        <p className="page-lede">{t.home.lede}</p>
      </header>

      {!result.ok ? (
        <div className="notice" role="alert">
          <AlertIcon />
          <div>
            <strong>{t.home.unavailableTitle}</strong>
            <p className="hint" style={{ marginTop: "0.25rem" }}>
              {t.home.unavailableBody}
            </p>
          </div>
        </div>
      ) : result.data.items.length === 0 ? (
        <div className="panel empty">
          <InboxIcon />
          <p>{t.home.empty}</p>
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
                      {t.home.solve} <ArrowRightIcon />
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
