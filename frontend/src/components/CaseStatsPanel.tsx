import type { Dictionary } from "@/i18n/dictionaries";
import type { CaseStats, ScoreOutcome } from "@/lib/api/types";

const ORDER: ScoreOutcome[] = ["correct", "partially_correct", "incorrect"];

/**
 * How the field has done on this case.
 *
 * Counts only — which answers were given would leak the key, so the endpoint
 * never returns them. This is difficulty, not a spoiler.
 */
export function CaseStatsPanel({ stats, t }: { stats: CaseStats; t: Dictionary }) {
  if (stats.submissions === 0) return null;

  const byOutcome = new Map(stats.outcomes.map((o) => [o.outcome, o.count]));
  const correct = byOutcome.get("correct") ?? 0;
  const successRate = Math.round((correct / stats.submissions) * 100);

  return (
    <section className="panel panel--tight stats" aria-labelledby="stats-heading">
      <h2 className="section-title" id="stats-heading">
        {t.stats.heading}
      </h2>

      <dl className="stats__figures">
        <div>
          <dt>{t.stats.attempts}</dt>
          <dd>{stats.submissions}</dd>
        </div>
        <div>
          <dt>{t.stats.solved}</dt>
          <dd>{successRate}%</dd>
        </div>
        <div>
          <dt>{t.stats.average}</dt>
          <dd>
            {stats.average_score}
            <span className="stats__of"> / {stats.max_score}</span>
          </dd>
        </div>
      </dl>

      <div className="stats__bar" role="img" aria-label={t.stats.distribution}>
        {ORDER.map((outcome) => {
          const count = byOutcome.get(outcome) ?? 0;
          if (count === 0) return null;
          return (
            <span
              key={outcome}
              className={`stats__segment stats__segment--${outcome}`}
              style={{ flexGrow: count }}
            />
          );
        })}
      </div>

      <ul className="stats__legend">
        {ORDER.map((outcome) => (
          <li key={outcome}>
            <span className={`stats__dot stats__dot--${outcome}`} aria-hidden="true" />
            {t.result[outcome]}
            <span className="stats__count">{byOutcome.get(outcome) ?? 0}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
