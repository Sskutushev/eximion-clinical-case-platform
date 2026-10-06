# Eximion — Test Assignment Report

**Sergei Kutushev** · October 2026
Repository: https://github.com/Sskutushev/eximion-clinical-case-platform

---

## 1. Objective and approach

The assignment lists three tasks: a FastAPI + PostgreSQL service, a Next.js + TypeScript
page, and an LLM extraction pipeline packaged for Cloud Run. I built them as **one
repository**, because they are not three independent exercises — they are one system
joined by one domain contract:

```
raw clinical text → Gemini structured extraction → ClinicalCase → FastAPI → PostgreSQL
                                                        ↓
                          Next.js (Server Component) → diagnosis → deterministic scoring
```

Treating it as one slice made the assignment's "shared types between API and frontend"
requirement a real mechanism rather than a convention: FastAPI publishes OpenAPI, the
frontend generates its types from it, and the extraction pipeline validates its output
against the same document. CI fails if any of the three drift apart.

### Assumptions

The assignment supplies no JSON schema, so I fixed one and stated it in the README
instead of asking:

- `title`, optional `patient_age` (0–130) and `patient_sex`, `presentation`
- `findings[]` — at least one, each with a category from a closed 7-value enum
- `answers[]` — the answer key: at least one correct answer with `score_weight > 0`;
  multiple correct synonyms allowed; differentials may carry partial credit but may not
  outweigh the correct answer
- optional `provenance` (`manual` or `llm_extraction` with model and prompt version)

All clinical content in the repository is synthetic. No real patient data anywhere.

---

## 2. Architecture

| Layer | Choice | Reasoning |
|---|---|---|
| API | FastAPI, Pydantic v2 | request validation and the OpenAPI contract come from the same models |
| Persistence | SQLAlchemy 2 (sync), PostgreSQL 17, Alembic | a few short queries per request; async would add a second driver and contagion without changing throughput at this scale |
| Frontend | Next.js App Router, TypeScript strict | Server Component renders, Client Component only interacts |
| Extraction | `google-genai`, Gemini structured output | schema-constrained generation, not parsing |
| Contract | `contracts/openapi.json`, committed | generated TS types and the pipeline's alignment test both derive from it |

Separation inside the backend: `schemas` (API contract) / `services` (use cases and
transactions) / `domain` (pure scoring logic) / `db` (persistence). ORM entities are never
serialized to a client. There is no repository layer — services use SQLAlchemy directly,
because a second persistence target does not exist and the indirection would not pay for
itself.

---

## 3. Backend

### Data model

Four normalized tables: `clinical_cases`, `case_findings`, `case_answers`,
`case_submissions`. Findings and answers are rows, not a JSONB blob, so they are
queryable and constrainable. The database enforces what the application should not be
trusted to: `CHECK` constraints on the category and sex enums, age range, score weight
range and `score <= max_score`; `UNIQUE (case_id, normalized_answer)` so one case cannot
hold two colliding keys; `ON DELETE CASCADE` for findings and answers, but
`ON DELETE RESTRICT` for submissions — a case with recorded attempts must not lose its
audit trail. `JSONB` is used only for optional extraction provenance, which carries no
schema obligations.

The initial migration is hand-written, with explicit constraint names from a naming
convention, and `alembic check` runs in CI so the models and migrations cannot drift.
`create_all` is not used anywhere, including in tests — the test database is built by
running the real migration.

### Scoring

Pure functions, no I/O and no LLM. Normalization is
`NFKC → casefold → collapse whitespace → strip edge punctuation`, so
`"  ACUTE   Appendicitis. "` and `"acute appendicitis"` match, `Straße` folds to
`strasse`, and inner punctuation stays significant (`type-2` ≠ `type 2`). A matched
correct answer scores its weight, a matched differential scores partial credit, anything
else scores zero. Every attempt is persisted with both the raw and the normalized answer
and the answer row it matched.

Feedback states the outcome but never reveals the correct answer: participants can retry,
so `GET` and `POST /score` both have to stay useless as an answer source.

### The security invariant

> The answer key is stored by the backend and never leaves it before a submission.

`PublicClinicalCase` has no answer-related fields at all, and the public read path uses
`selectinload(findings)` only — with `lazy="raise"` on `answers`, the answer key is not
even loaded into memory on that path. The invariant is asserted three independent ways:

1. an API test that greps the **raw HTTP body** for the diagnosis strings and for
   `is_correct` / `score_weight` / `answer`;
2. a contract test asserting the published OpenAPI `PublicClinicalCase` schema contains
   no such property;
3. the end-to-end smoke test, which checks both the API response and the **rendered HTML**.

That third check earned its place: the diagnosis form originally carried the placeholder
hint *"e.g. Acute appendicitis"*, which is exactly the answer to the smoke-test case. The
smoke test failed, and the hint was rewritten. A unit test would not have caught it.

### Other hardening

Authoring (`POST /cases`) requires `X-Admin-API-Key`, compared with
`hmac.compare_digest`. With `ENVIRONMENT=production` the app refuses to start without
that key and disables `/docs` and `/openapi.json`. Errors return
`{"detail": "..."}` — no stack traces, SQL or connection strings. Logs are structured
JSON with a request id, and carry ids, status, duration and field paths, never bodies or
prompts. Each response gets `nosniff`, `X-Frame-Options: DENY`, `no-referrer`,
`no-store`. The connection pool is small and has an explicit connect timeout, so an
unreachable database fails fast instead of holding request slots.

---

## 4. Frontend and the shared contract

`/cases/[id]` is a Server Component: it fetches the case and renders the title,
demographics, presentation and findings grouped by category, with `loading.tsx`,
`not-found.tsx` and `error.tsx` for the paths that are not the happy one. The Client
Component owns only the diagnosis form — its pending state, validation message and
result. It never computes a score.

Submission goes through a **Server Action**, so the browser never calls the API directly.
`API_BASE_URL` is read server-side only (not `NEXT_PUBLIC_*`), which means the backend
URL never reaches the bundle and there is no CORS surface to configure. Backend failures
are modelled as a discriminated result (`not_found | invalid | unavailable`) rather than
thrown strings, so each one is handled explicitly and the user sees a sensible message
while details stay in the server log.

Types are **generated**, never hand-copied: `backend → contracts/openapi.json →
openapi-typescript → src/generated/api.d.ts`, consumed through a typed `openapi-fetch`
client. Both artefacts are committed, and CI regenerates them and fails on any diff.

---

## 5. LLM pipeline and evaluation

### Extraction

`raw clinical text → ClinicalCaseExtraction`, a contract that mirrors the backend's
create schema so the result is POSTable unchanged.

- **Structured output, not parsing.** Gemini is constrained with `response_json_schema`
  at `temperature=0`. No regex, no markdown scraping.
- **Validation is mandatory.** Every response is validated with Pydantic. A violation
  raises `SchemaValidationError` and is **not** retried and **not** repaired with a
  fallback — a malformed clinical extraction must surface.
- **Retries are narrow.** Bounded exponential backoff for transient provider errors
  (429, 5xx) only; 4xx and safety blocks fail immediately.
- **The model does not diagnose.** The prompt restricts it to diagnoses the source text
  states, and requires `null` for unstated age or sex instead of an estimate.
- **The model does not score either.** The first prompt asked it to weight a differential
  "by clinical proximity" — a number the source text does not contain, invented by the
  model, in a pipeline whose first rule is to invent nothing. Extraction (`extract-v2`)
  now records only which diagnosis the source establishes; score weights are assigned
  afterwards by an explicit deterministic policy, so the number is a product decision an
  editor can change rather than a model guess.
- **Provider boundary.** A `Protocol` with a Gemini implementation and a fake one, so the
  pipeline, the harness and the tests all run with no network and no credentials.
- **Provenance and logging.** The model name and prompt version travel with each
  extracted case; logs carry field paths and error types, never clinical text.

One finding worth calling out, because it came from reviewing my own code rather than
from a test: a validation failure was originally logged with `logger.exception`, which
is the idiomatic choice and what the linter pushes you toward. But Pydantic embeds the
offending *input values* in its error message — here, the clinical narrative — so the
traceback would have written patient text into the logs, defeating the logging policy
stated two lines above. Validation failures now log field paths and error types with no
`exc_info`, and a regression test asserts the clinical marker never reaches the log.

### Eval methodology

10 synthetic, de-identified vignettes with hand-written ground truth, covering synonym
answer keys, differentials with partial credit, all seven finding categories, and one
case with unstated demographics (to test that the model returns `null` rather than
guessing).

Metrics are deterministic against that ground truth — no LLM-as-a-judge, because with
labels available an exact metric is both cheaper and more defensible: `schema_valid_rate`,
age and sex accuracy, `answer_key_accuracy` (exact set match of accepted correct
diagnoses — a missed synonym silently rejects valid physician answers in production),
findings precision / recall / F1, finding-category accuracy, `exact_case_match_rate`, and
the id and reason for every failure.

The offline fixtures deliberately inject four known defects: a dropped finding, a missing
synonym, a nulled age, and an invalid category. The harness is therefore *proven* to
detect errors rather than always reporting a perfect score, and CI asserts those exact
four failures:

```json
{
  "provider": "fake", "model": "fake-extractor-1", "prompt_version": "extract-v2",
  "total": 10, "scored": 9, "provider_errors": 0, "model_blocked": 0,
  "schema_valid_rate": 0.9, "age_accuracy": 0.8889, "sex_accuracy": 1.0,
  "answer_key_accuracy": 0.8889, "findings_f1": 0.9899, "exact_case_match_rate": 0.6,
  "failures": ["case-003 findings", "case-005 answer_key", "case-007 patient_age",
               "case-009 schema_invalid"]
}
```

---

## 6. Docker and GCP

Three images, all multi-stage and running as a non-root user. `backend` and `frontend`
are services; `llm_pipeline` is a batch container whose entry point is the extraction
CLI, deployed as a Cloud Run Job rather than a service: extraction is authoring work,
not request-path work, so it should neither idle nor be able to take traffic.

For the two services: the backend resolves dependencies
from `uv.lock` in a builder stage and ships only the venv and source; the frontend uses
Next.js `output: "standalone"`, so the runtime image carries a minimal server rather than
`node_modules`. Both read `PORT` from the environment, as Cloud Run requires, and no
secret is baked into a layer. `docker compose up --wait` brings up PostgreSQL, runs
migrations as a **separate one-shot service**, then starts the API and the frontend — the
same ordering as production.

`infra/DEPLOYMENT.md` is the full runbook: Artifact Registry → images tagged with the
commit SHA → Cloud SQL (PostgreSQL 17, private IP, PITR, regional) → Secret Manager →
four least-privilege service accounts → migrations as a Cloud Run **Job** → backend and
frontend services → the extraction Job → smoke test and log check → rollback by traffic shift.

Two deliberate decisions in there:

**Migrations are a controlled step, not on startup.** With autoscaling, N instances would
race on the same DDL, and a failed migration would crash-loop the service instead of
failing one job. The job runs under its own service account, which has Cloud SQL access
and the DB password but is not attached to any serving revision.

**Pool sizing is derived, not guessed.** Cloud Run multiplies connections by instance
count: `max-instances × (pool_size + max_overflow)` = `10 × 7` = 70 against
`max_connections=200`, leaving headroom for the migration job and operator sessions.
Raising `max-instances` without lowering the pool is the standard way to exhaust a Cloud
SQL instance, so the two are reviewed together.

The browser never calls the API, so the backend is deployed with
`--no-allow-unauthenticated`, and only the frontend's service account holds
`roles/run.invoker` on it. Ingress is `all`, deliberately: IAM closes the service on any
network, whereas internal ingress is a *network* control that would require the frontend
to egress through a VPC — without that it does not harden the service, it breaks it. One
lock that works rather than two where one is wrong.

Three details in that path are easy to get wrong, and I had all three wrong in the first
version of the runbook:

**`run.invoker` permits a call; it does not authenticate one.** A private Cloud Run
service still requires a Google-signed ID token whose audience is the target service URL.
The frontend now fetches one from the instance metadata server and attaches it to every
backend request; outside Cloud Run it adds nothing, so local development is unchanged.
Without this the deployment would have failed on the first request.

**Cloud Run does not expand variable references inside environment values.** A
`DATABASE_URL` containing `${DB_PASSWORD}` arrives with that literal text as the password.
The service now receives the parts separately and assembles the URL at runtime, which also
escapes a generated password containing `/`, `@` or `:` correctly — a test covers both.

**A private-IP Cloud SQL instance needs more than `--no-assign-ip`.** It needs Private
Services Access for Google to peer the instance into, and a path out of Cloud Run into
that VPC — Direct VPC egress, which is the current recommended option over a Serverless
VPC Access connector. And the application then has to use that path: it connects to the
instance's private address on 5432 as an ordinary PostgreSQL client, with TLS required
on the instance. The managed `/cloudsql` Unix socket is the Auth Proxy's public-IP path,
and a runbook that pairs it with a private-only instance has two half-paths and no
connection. The runbook now has one.

---

## 7. What was actually executed

Everything below was run locally on this machine, and the numbers are the real output.

| Check | Command | Result |
|---|---|---|
| Backend lint / format / types | `ruff check`, `ruff format --check`, `mypy --strict` | clean |
| Backend tests (real PostgreSQL) | `uv run pytest --cov` | **53 passed**, coverage **98.31%** (gate 90%) |
| Migration integrity | `alembic upgrade head`, `alembic check`, up/down/up in a test | no drift |
| Pipeline lint / types | `ruff`, `mypy --strict` | clean |
| Pipeline tests | `uv run pytest --cov` | **128 passed**, coverage **95.47%** (gate 85%) |
| Offline eval | `clinical-extraction eval --provider fake` | gate passed; 4 injected defects detected |
| Offline decision eval | `clinical-extraction eval-decisions` | gate passed; 2 injected verifier misjudgments detected |
| Live extraction eval | `clinical-extraction eval --provider gemini --delay 7` | `extract-v2`, 10/10 scored |
| Frontend lint | `eslint . --max-warnings 0` | clean |
| Frontend types | `tsc --noEmit` (prod + test configs) | clean |
| Frontend tests | `vitest run` | **34 passed** |
| Frontend build | `next build` | success |
| Docker images | `docker compose up --build --wait` | all services healthy |
| Extraction container | `docker run eximion-llm eval --provider fake` | uid 1001, eval passes in-container |
| End-to-end smoke | `bash scripts/smoke.sh` | **SMOKE PASS** |

**Not executed, and why:**

- **Live GCP deployment.** No project with Vertex AI and Cloud SQL billing was
  provisioned for this assignment, so nothing was deployed to Cloud Run. The runbook is
  complete and reproducible, but I have not run it end to end, and I am not claiming a
  live URL.
- **Jev (TypeSafe) live.** The decision layer added after the interview is tested
  against the real TypeSafe SDK with a mocked HTTP layer, and its eval runs offline.
  No TypeSafe key was available, so there is no live Jev measurement yet. See
  `docs/DECISION_MODEL_MIGRATION.md`.

**Since executed:** a complete live run of the current prompt, `extract-v2`, all ten
cases, committed as `evals/results/gemini-2.5-flash-extract-v2.json`: schema 10/10,
age and sex 1.0, answer key 0.9, findings F1 0.51 by token overlap, category accuracy
0.97, latency p50 4.0 s. The earlier `extract-v1` file is kept as it was: a partial
free-tier run of two cases.

The first live run was worth doing: it found two faults the offline harness could not.

**Gemini could not accept the schema at all.** Constrained decoding rejected it with
*"the specified schema produces a constraint that has too many states for serving"* —
the length limits, numeric ranges and array bounds on the Pydantic contract. The model
is now sent a simplified schema carrying the shape, enums and required fields, while
Pydantic still enforces every bound on the response. Nothing is lost: the model guides
generation, the validator decides what is acceptable.

**My own metric was wrong twice.** A 429 counted against `schema_valid_rate`, which
charged a quota failure to model accuracy — provider errors are now reported separately.
And findings were compared by exact text, so a paraphrase ("Temperature 38.1 C" for
"Temperature 38.1 °C") scored as a miss. Findings now match on token overlap, with the
exact-text figure still reported as a strict lower bound. On the completed cases that is
the difference between F1 0.32 and 0.62 — the same extraction, measured honestly.

---

## 8. Trade-offs

1. **Sync SQLAlchemy, not async.** A handful of short queries per request; async adds a
   second driver and colours every call site without changing throughput at this scale.
   Cloud Run scales out by instance, and the pool is sized for that.
2. **One repository, not three.** The three tasks share one contract. A monorepo turns
   the OpenAPI → TypeScript generation and the contract-alignment test into real CI gates
   instead of documentation.
3. **Exact-match scoring, not semantic.** Explainable and reproducible: a physician can
   be told precisely why an answer scored what it did, and the same submission always
   scores the same. Synonyms are a product decision expressed as extra answer rows, not a
   model guess. Semantic matching would need its own eval, a confidence threshold and an
   appeal path before it could be trusted to score a competition.
4. **Fake provider in CI, real Gemini opt-in.** CI stays free, offline and deterministic
   while still exercising the entire pipeline including its failure paths; the real run is
   one flag away.
5. **Admin API key, not full authentication.** It closes the authoring hole inside the
   scope of this assignment without pretending to be an identity system. Participant
   auth is the first item in production next steps.

---

## 9. Production next steps

Participant authentication and authorization (who may solve what, how many scored
attempts per case); rate limiting on `/score`; an append-only audit trail with actor
identity; idempotency keys for authoring; a PHI, retention and BAA review before any real
patient data touches the system; alerting and uptime checks on top of the structured
logs; a human review queue for LLM-extracted cases before they go live; and a larger eval
set with inter-rater agreement on the ground truth.

---

## 10. Repository

https://github.com/Sskutushev/eximion-clinical-case-platform

```
backend/        FastAPI, SQLAlchemy 2, Alembic, pytest
frontend/       Next.js App Router, TypeScript strict, vitest
llm_pipeline/   Gemini structured extraction + eval harness
contracts/      openapi.json — the shared contract (committed, drift-checked)
infra/          DEPLOYMENT.md — Cloud Run + Cloud SQL runbook
scripts/        smoke.sh — end-to-end check of the running stack
docs/           IMPLEMENTATION_PLAN.md, REPORT.md
```

Reviewer path — clone, then:

```bash
cp .env.example .env
docker compose up -d --build --wait
bash scripts/smoke.sh
cd llm_pipeline && uv sync && uv run clinical-extraction eval --provider fake
```

`README.md` covers the architecture diagrams, the data model, the API with examples, type
generation, every check and the security rationale.
