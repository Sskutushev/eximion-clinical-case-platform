import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ScoreFormState } from "@/app/cases/[id]/actions";
import { DiagnosisForm } from "@/components/DiagnosisForm";

const correct: ScoreFormState = {
  status: "success",
  submittedAnswer: "Acute appendicitis",
  result: {
    submission_id: "6f1a2b3c-0000-4000-8000-000000000001",
    score: 10,
    max_score: 10,
    is_correct: true,
    outcome: "correct",
    feedback: "Correct diagnosis.",
  },
};

describe("DiagnosisForm", () => {
  it("submits the diagnosis, shows a pending state and renders the score", async () => {
    let resolve!: (state: ScoreFormState) => void;
    const action = vi.fn(
      (_state: ScoreFormState, _formData: FormData) =>
        new Promise<ScoreFormState>((r) => {
          resolve = r;
        }),
    );
    const user = userEvent.setup();

    render(<DiagnosisForm action={action} />);

    await user.type(screen.getByLabelText("Most likely diagnosis"), "Acute appendicitis");
    await user.click(screen.getByRole("button", { name: "Submit diagnosis" }));

    expect(await screen.findByRole("button", { name: "Scoring…" })).toBeDisabled();
    expect(action).toHaveBeenCalledTimes(1);
    expect(action.mock.calls[0]?.[1].get("answer")).toBe("Acute appendicitis");

    resolve(correct);

    const result = await screen.findByTestId("score-result");
    expect(result).toHaveTextContent("Correct");
    expect(result).toHaveTextContent("10 / 10");
    expect(result).toHaveTextContent("Acute appendicitis");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Submit diagnosis" })).toBeEnabled(),
    );
  });

  it("shows an accessible error message when scoring fails", async () => {
    const action = vi.fn(
      async (_state: ScoreFormState, _formData: FormData): Promise<ScoreFormState> => ({
        status: "error",
        message: "Scoring is temporarily unavailable. Please try again.",
      }),
    );
    const user = userEvent.setup();

    render(<DiagnosisForm action={action} />);

    await user.type(screen.getByLabelText("Most likely diagnosis"), "Migraine");
    await user.click(screen.getByRole("button", { name: "Submit diagnosis" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("temporarily unavailable");
    expect(screen.getByLabelText("Most likely diagnosis")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByTestId("score-result")).not.toBeInTheDocument();
  });
});
