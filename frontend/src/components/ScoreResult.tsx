import type { ScoreOutcome, ScoreResponse } from "@/lib/api/types";

const OUTCOME_LABEL: Record<ScoreOutcome, string> = {
  correct: "Correct",
  partially_correct: "Partially correct",
  incorrect: "Incorrect",
};

export function ScoreResult({
  result,
  submittedAnswer,
}: {
  result: ScoreResponse;
  submittedAnswer: string;
}) {
  return (
    <div className={`result result--${result.outcome}`} data-testid="score-result">
      <p className="result__outcome">{OUTCOME_LABEL[result.outcome]}</p>
      <p className="result__score">
        Score:{" "}
        <strong>
          {result.score} / {result.max_score}
        </strong>
      </p>
      <p className="result__answer">
        You answered: <q>{submittedAnswer}</q>
      </p>
      <p className="result__feedback">{result.feedback}</p>
    </div>
  );
}
