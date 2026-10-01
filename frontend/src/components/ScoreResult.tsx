import type { JSX, SVGProps } from "react";

import { CheckIcon, CrossIcon, PartialIcon } from "@/components/icons";
import type { ScoreOutcome, ScoreResponse } from "@/lib/api/types";

const OUTCOME: Record<
  ScoreOutcome,
  { label: string; Icon: (p: SVGProps<SVGSVGElement>) => JSX.Element }
> = {
  correct: { label: "Correct", Icon: CheckIcon },
  partially_correct: { label: "Partially correct", Icon: PartialIcon },
  incorrect: { label: "Incorrect", Icon: CrossIcon },
};

export function ScoreResult({
  result,
  submittedAnswer,
}: {
  result: ScoreResponse;
  submittedAnswer: string;
}) {
  const { label, Icon } = OUTCOME[result.outcome];
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
            You answered: <q>{submittedAnswer}</q>
          </p>
        </div>
      </div>

      <div>
        <p className="score">
          <span className="score__value">{result.score}</span>
          <span className="score__max">/ {result.max_score}</span>
          <span className="visually-hidden">
            Score: {result.score} out of {result.max_score}
          </span>
        </p>
        <div className="meter" role="presentation">
          <div className="meter__fill" style={{ width: `${percent}%` }} />
        </div>
      </div>

      <p className="result__feedback">{result.feedback}</p>
    </div>
  );
}
