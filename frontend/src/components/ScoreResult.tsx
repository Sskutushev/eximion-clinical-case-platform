"use client";

import type { JSX, SVGProps } from "react";

import { CountUp } from "@/components/CountUp";
import { CheckIcon, CrossIcon, PartialIcon } from "@/components/icons";
import { useI18n } from "@/i18n/client";
import type { ScoreOutcome, ScoreResponse } from "@/lib/api/types";

const OUTCOME_ICON: Record<ScoreOutcome, (p: SVGProps<SVGSVGElement>) => JSX.Element> = {
  correct: CheckIcon,
  partially_correct: PartialIcon,
  incorrect: CrossIcon,
};

export function ScoreResult({
  result,
  submittedAnswer,
}: {
  result: ScoreResponse;
  submittedAnswer: string;
}) {
  const { t } = useI18n();
  const Icon = OUTCOME_ICON[result.outcome];
  const label = t.result[result.outcome];
  const percent = result.max_score > 0 ? (result.score / result.max_score) * 100 : 0;

  return (
    <div className={`result result--${result.outcome}`} data-testid="score-result">
      <div className="result__head">
        <span className="result__badge" aria-hidden="true">
          <Icon />
        </span>
        <div>
          <p className="result__outcome">{label}</p>
          <p className="result__answer">
            {t.result.answered}: <q>{submittedAnswer}</q>
          </p>
        </div>
      </div>

      <div>
        <p className="score">
          <span className="score__value">
            <CountUp value={result.score} />
          </span>
          <span className="score__max">/ {result.max_score}</span>
          <span className="visually-hidden">
            {t.result.score(result.score, result.max_score)}
          </span>
        </p>
        <div className="meter" role="presentation">
          <div className="meter__fill" style={{ width: `${percent}%` }} />
          <div className="meter__shine" aria-hidden="true" />
        </div>
      </div>

      <p className="result__feedback">{result.feedback}</p>
    </div>
  );
}
