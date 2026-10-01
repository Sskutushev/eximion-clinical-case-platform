import { getTranslations } from "@/i18n/server";

/** Skeleton mirrors the real layout, so nothing jumps when the case lands. */
export default async function CaseLoading() {
  const { t } = await getTranslations();

  return (
    <div className="stack" aria-busy="true">
      <span className="visually-hidden" role="status">
        {t.case.loading}
      </span>
      <div className="case-layout">
        <div className="stack">
          <div className="panel skeleton-stack">
            <div className="skeleton skeleton--title" />
            <div className="skeleton skeleton--line" />
            <div className="skeleton skeleton--line" />
            <div className="skeleton skeleton--line" />
          </div>
          <div className="panel skeleton-stack">
            <div className="skeleton skeleton--block" />
            <div className="skeleton skeleton--block" />
          </div>
        </div>
        <div className="panel skeleton-stack">
          <div className="skeleton skeleton--line" />
          <div className="skeleton skeleton--block" />
        </div>
      </div>
    </div>
  );
}
