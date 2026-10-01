/** Skeleton mirrors the real layout, so nothing jumps when the case lands. */
export default function CaseLoading() {
  return (
    <div className="stack" aria-busy="true">
      <span className="visually-hidden" role="status">
        Loading clinical case
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
