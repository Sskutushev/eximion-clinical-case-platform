export default function CaseLoading() {
  return (
    <main className="layout" aria-busy="true">
      <div className="card skeleton" role="status">
        <p>Loading clinical case…</p>
      </div>
    </main>
  );
}
