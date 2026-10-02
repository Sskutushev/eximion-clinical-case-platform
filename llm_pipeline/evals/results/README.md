# Evaluation results

`gemini-2.5-flash-extract-v1.json` is a real run against the Gemini API, not a
simulation. It is committed as produced, including its failures.

## Provenance: which prompt this measures

The file name carries the prompt version on purpose. The run was made with
`extract-v1`. The current prompt is `extract-v2` (see `PROMPT_VERSION` in
`prompt.py`), which changed the extraction schema, not just the wording: the
model no longer produces `score_weight` for diagnoses. Weights are now assigned
by a deterministic policy after extraction, so the model only reports which
diagnosis the source text establishes.

`extract-v2` has **not** been run live, for the same quota reason described
below. So the honest statement is: the previous prompt was partially verified
against the live model; the current one is covered by the offline eval and the
stubbed-SDK tests, and awaits a paid tier or a Vertex project for its own live
run. The v1 numbers are not presented as a measurement of v2.

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

## What this run shows, and what it does not

The committed run was made on a **free Gemini tier**, whose quota is exhausted
partway through ten cases. So it is a genuine but partial measurement: the cases
that completed are measured honestly, and the rest are recorded as quota errors
rather than silently dropped or retried into looking better.

What the completed cases show: demographics and the answer key were extracted
exactly; findings were extracted well in substance but phrased differently from
the ground truth, which is why the exact-text metric is roughly half the
overlap-based one. That gap is a property of free-text findings, not of the
model — and it is the reason both numbers are reported rather than only the
flattering one.

A full ten-case measurement needs a paid tier or a Vertex AI project. The
command is above and unchanged.
