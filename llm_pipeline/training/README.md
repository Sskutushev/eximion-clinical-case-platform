# Training data for the local models

`finding_category_seed.jsonl` holds 84 short finding phrases, 12 per category,
written by hand for this project. They are synthetic, like the eval set: no
patient, record or publication behind them.

Rules for this folder:

- Seed phrases only ever go into the training split. Scoring a model on them would
  flatter it.
- A test checks that no seed phrase repeats a finding from `evals/dataset.jsonl`,
  so the held-out score stays honest.
- No real patient data here, ever. Reviewed production labels belong in a
  governed store with retention rules, not in git.

Change anything here and the committed model in `models/finding_category` no longer
matches its manifest; CI then fails until it is retrained:

```bash
uv sync --group ml
uv run clinical-extraction train-local --task finding_category
```
