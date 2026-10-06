# Evaluation results

Every file here is committed as produced, including its failures.

| File | What it is |
|---|---|
| `gemini-2.5-flash-extract-v2.json` | live Gemini run of the current prompt, all 10 cases (2026-10-06) |
| `gemini-2.5-flash-extract-v1.json` | earlier live run of the previous prompt, 2 of 10 cases (free-tier quota) |
| `fake-eval.json` | offline run, fake provider with four planted defects |
| `decision-eval-reference.json` | offline verifier eval, see `docs/DECISION_MODEL_MIGRATION.md` |

## The current prompt, live

`extract-v2` on `gemini-2.5-flash`, ten cases, `--delay 7`, no provider errors:

| Metric | Value |
|---|---|
| schema valid | 1.0 (10/10) |
| age / sex | 1.0 / 1.0 |
| answer key | 0.9 (case-004 differs) |
| findings F1, token overlap | 0.51 (precision 0.44, recall 0.61) |
| findings F1, exact text | 0.17 |
| category accuracy on matched findings | 0.97 |
| latency p50 / p95 | 4.0 s / 7.7 s |
| tokens, all ten cases | 4,314 in / 3,024 out |

Structure, demographics and the answer key are solid. Findings are where the model
and the ground truth part ways: the model often splits or merges facts differently
from the hand-written list, so the overlap metric undercounts real matches and the
exact-text metric undercounts them much more. That is a measurement limit as much as
a model one, and it is why both numbers are shown.

The output token count excludes Gemini 2.5's thinking tokens, which are billed as
output. Cost estimates built on it are a lower bound.

## The earlier run: which prompt it measures

The file name carries the prompt version on purpose. The v1 run was made with
`extract-v1`. The current prompt is `extract-v2` (see `PROMPT_VERSION` in
`prompt.py`), which changed the extraction schema, not just the wording: the
model no longer produces `score_weight` for diagnoses. Weights are now assigned
by a deterministic policy after extraction, so the model only reports which
diagnosis the source text establishes.

The v1 numbers are not presented as a measurement of v2; v2 has its own run above.

## Reproducing it

The pipeline accepts either path. For a quick run, a Gemini Developer API key is
enough and needs no GCP project:

```bash
# https://aistudio.google.com/apikey
export GEMINI_API_KEY="your-key"

cd llm_pipeline
uv sync
uv run clinical-extraction eval --provider gemini --delay 7 \
  --output evals/results/gemini-2.5-flash-extract-v2.json
```

For the production path, use Vertex AI instead — no key is stored anywhere, the
credentials come from the service account:

```bash
export GOOGLE_CLOUD_PROJECT="your-project"
export GOOGLE_CLOUD_LOCATION="us-central1"
gcloud auth application-default login
uv run clinical-extraction eval --provider gemini --delay 2
```

`GOOGLE_CLOUD_PROJECT` takes precedence. If it is set in your shell from another
project, a Developer API key is ignored — unset it, or the run will try Vertex
and fail on credentials.

`--delay` paces the requests. A free tier allows only a handful per minute, so
without it the back half of a run is nothing but quota errors.

## Reading the numbers

| Field | Meaning |
|---|---|
| `scored` / `total` | how many cases produced an extraction that could be scored |
| `provider_errors` | requests that never reached the model — quota, transport |
| `model_blocked` | requests the model declined to answer — a safety block |
| `schema_valid_rate` | of the responses the model **did** return, how many satisfied the contract; provider errors and blocks are outside the denominator |
| `findings_f1` | findings matched by token overlap ≥ 0.6 |
| `findings_f1_exact_text` | the same, requiring identical text — a strict lower bound |
| `finding_category_accuracy` | of matched findings, how many were filed under the right category |

A provider error is deliberately not counted as a schema failure. A 429 means
the request never reached the model, and charging it against model accuracy
would understate the model. A safety block is kept apart from both: it is the
model declining, which is neither an outage nor a malformed answer, and it is
worth seeing on its own because clinical text can trip a safety filter.

## What the v1 run shows, and what it does not

The v1 run was made on a **free Gemini tier** without `--delay`, so the
requests-per-minute limit ran out partway through ten cases. So it is a genuine but partial measurement: the cases
that completed are measured honestly, and the rest are recorded as quota errors
rather than silently dropped or retried into looking better.

What the completed cases show: demographics and the answer key were extracted
exactly; findings were extracted well in substance but phrased differently from
the ground truth, which is why the exact-text metric is roughly half the
overlap-based one. That gap is a property of free-text findings, not of the
model — and it is the reason both numbers are reported rather than only the
flattering one.

The v2 run above used the same free tier with `--delay 7` and completed all ten.
