# Eximion Clinical Case Platform

One vertical slice, one domain contract:

```
raw clinical text ─► Gemini structured extraction ─► ClinicalCase ─► FastAPI ─► PostgreSQL
                                                                          │
                                   Next.js (Server Component) ◄───────────┘
                                   diagnosis ─► Server Action ─► deterministic scoring
```

Physicians open a case, submit a diagnosis and get a score. Cases can be authored by
hand or extracted from free clinical text by an LLM — both paths produce the same
validated `ClinicalCase`, so there is exactly one schema to reason about.

Built for the Eximion take-home assignment (three tasks: FastAPI + PostgreSQL,
Next.js + TypeScript, LLM pipeline + GCP), deliberately as **one** repository rather
than three: the three parts are one system joined by one contract.

## Architecture

```mermaid
flowchart LR
    subgraph authoring["Authoring (admin)"]
        RAW["raw clinical text"] --> EX["clinical_extraction<br/>Gemini structured output"]
        EX -->|"validated ClinicalCase"| API
        EVAL["eval harness<br/>deterministic metrics"] -.-> EX
    end

    subgraph serving["Serving"]
        WEB["Next.js App Router<br/>Server + Client Components"] -->|"server-side fetch"| API
        API["FastAPI<br/>schemas · services · domain"] --> DB[("PostgreSQL<br/>normalized, Alembic")]
    end

    API -->|"OpenAPI"| TYPES["contracts/openapi.json<br/>→ generated TS types"]
    TYPES -.-> WEB

    classDef secure fill:#fff3cd,stroke:#9a6700
    class DB,API secure
```

**The answer key never leaves the backend.** `PublicClinicalCase` has no answer fields,
the public read path does not even load the `answers` relationship, and that invariant is
asserted three ways: an API test on the raw HTTP body, a contract test on the published
OpenAPI document, and the end-to-end smoke test (which also checks the rendered HTML).

## Repository layout

```
backend/        FastAPI, SQLAlchemy 2, Alembic, pytest        (Python 3.12)
frontend/       Next.js App Router, TypeScript strict, vitest (Node 22)
llm_pipeline/   Gemini extraction + eval harness             (Python 3.12)
contracts/      openapi.json — the shared contract, committed and drift-checked
infra/          DEPLOYMENT.md — Cloud Run + Cloud SQL runbook
scripts/        smoke.sh — end-to-end check of the real stack
docs/           IMPLEMENTATION_PLAN.md, REPORT.md
```

## Quick start

Requires Docker, and (for running from source) Python 3.12 with [uv](https://docs.astral.sh/uv/)
and Node 22.

```bash
git clone https://github.com/Sskutushev/eximion-clinical-case-platform.git
cd eximion-clinical-case-platform
cp .env.example .env            # local defaults work as-is

docker compose up -d --build --wait    # PostgreSQL → migrations → API → frontend
bash scripts/smoke.sh                  # proves the whole slice works
```

| URL | What |
|---|---|
| http://localhost:3000 | case list → case page → submit a diagnosis |
| http://localhost:8000/docs | interactive API (local/test only — disabled in production) |
| http://localhost:8000/health/ready | readiness, including the database |

Load two demo cases to click through:

```bash
cd backend && uv sync && uv run python -m scripts.seed
```

### Running from source

```bash
docker compose up -d --wait postgres

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload --port 8000

cd ../frontend
npm install
npm run dev                     # http://localhost:3000
```

`make help` lists every task (`make up`, `make migrate`, `make test`, `make types`,
`make eval`, `make smoke`, `make check`). On Windows without `make`, the commands in
each recipe run as-is in Git Bash or PowerShell.

## API

```bash
ADMIN=local-dev-admin-key

# Author a case (admin only; the answer key lives here)
curl -X POST localhost:8000/api/v1/cases \
  -H 'Content-Type: application/json' -H "X-Admin-API-Key: ${ADMIN}" \
  -d '{
    "title": "Acute right lower quadrant pain",
    "patient_age": 24, "patient_sex": "male",
    "presentation": "Migratory abdominal pain for 18 hours with nausea.",
    "findings": [
      {"category": "symptom", "value": "Pain migrating to the right lower quadrant"},
      {"category": "laboratory", "value": "White cell count 14.2 x10^9/L"}
    ],
    "answers": [
      {"text": "Acute appendicitis", "is_correct": true, "score_weight": 10},
      {"text": "Appendicitis", "is_correct": true, "score_weight": 10},
      {"text": "Mesenteric lymphadenitis", "is_correct": false, "score_weight": 3}
    ]
  }'
# → 201 {"id": "..."}  + Location header

# Read it as a participant — no answers, no is_correct, no score_weight
curl localhost:8000/api/v1/cases/<id>

# Submit a diagnosis; normalization makes this equal to "Acute appendicitis"
curl -X POST localhost:8000/api/v1/cases/<id>/score \
  -H 'Content-Type: application/json' -d '{"answer": "  ACUTE   Appendicitis. "}'
# → {"score": 10, "max_score": 10, "is_correct": true, "outcome": "correct", ...}
```

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/cases` | author a case with its answer key (requires `X-Admin-API-Key`) |
| `GET /api/v1/cases` | list case summaries |
| `GET /api/v1/cases/{id}` | the case as a participant sees it |
| `POST /api/v1/cases/{id}/score` | score a diagnosis, persist the submission |
| `GET /health`, `/health/ready` | liveness, readiness |

## Data model

```mermaid
erDiagram
    clinical_cases ||--|{ case_findings : has
    clinical_cases ||--|{ case_answers  : "answer key"
    clinical_cases ||--o{ case_submissions : receives
    case_answers   ||--o{ case_submissions : "matched by"

    clinical_cases {
        uuid id PK
        varchar(200) title
        smallint patient_age "0..130, nullable"
        varchar(16) patient_sex "enum, nullable"
        text presentation
        jsonb provenance "manual | llm_extraction"
        timestamptz created_at
    }
    case_findings {
        bigint id PK
        uuid case_id FK "cascade"
        varchar(32) category "7-value enum"
        text value
        smallint position "unique per case"
    }
    case_answers {
        bigint id PK
        uuid case_id FK "cascade"
        varchar(300) answer_text
        varchar(300) normalized_answer "unique per case"
        boolean is_correct
        smallint score_weight "0..100"
        smallint position
    }
    case_submissions {
        uuid id PK
        uuid case_id FK "restrict"
        bigint matched_answer_id FK "set null"
        varchar(300) submitted_answer
        varchar(300) normalized_answer
        smallint score "0..max_score"
        smallint max_score
        boolean is_correct
        timestamptz created_at
    }
```

Normalized, not a JSONB blob: findings and answers are queryable rows, each enum and
range is a `CHECK`, answer uniqueness is a `UNIQUE` constraint, and `score <= max_score`
is enforced by the database rather than trusted from the application. `JSONB` is used
only for optional extraction provenance, which has no schema obligations.

`case_submissions` uses `ON DELETE RESTRICT` — a case with recorded attempts cannot be
deleted out from under its audit trail — while findings and answers cascade.

## Scoring

Deterministic and LLM-free. A submission is normalized
(`NFKC → casefold → collapse whitespace → strip edge punctuation`) and compared against
the stored normalized key:

| Submitted | Result |
|---|---|
| `Acute appendicitis` | 10/10 — correct |
| `  ACUTE   Appendicitis. ` | 10/10 — same key after normalization |
| `appendicitis` | 10/10 — accepted synonym (its own row) |
| `Mesenteric lymphadenitis` | 3/10 — partially correct (differential) |
| `Migraine` | 0/10 — incorrect |

Case-folding is Unicode-aware (`Straße` → `strasse`) and inner punctuation is
significant (`type-2 diabetes` ≠ `type 2 diabetes`), so the rule stays predictable.
Feedback states the outcome but never reveals the correct answer — participants may
retry, and `GET` must stay useless as an answer source.

## Shared types

FastAPI's OpenAPI document is the single source of truth. There are no hand-copied DTOs:

```bash
make types     # backend → contracts/openapi.json → frontend/src/generated/api.d.ts
```

Both artefacts are committed, and CI regenerates them and fails on any diff — the
contract cannot drift from the code. The frontend consumes them through a typed
`openapi-fetch` client; `llm_pipeline` validates its output against the same document
in `tests/test_contract_alignment.py`.

## Frontend

- **Server Component** (`/cases/[id]`) fetches and renders the case; `loading.tsx`,
  `not-found.tsx` and `error.tsx` cover the non-happy paths.
- **Client Component** owns only the interaction: the diagnosis form, its pending and
  error states, and the result. It never computes a score.
- Submission goes through a **Server Action**, so the browser never talks to the API.
  `API_BASE_URL` is server-side only — no `NEXT_PUBLIC_*`, no CORS surface, no backend
  URL in the bundle.
- Backend failures are a discriminated result (`not_found | invalid | unavailable`)
  rather than thrown strings, so every case is handled explicitly.

## LLM extraction pipeline

```bash
cd llm_pipeline && uv sync

uv run clinical-extraction eval --provider fake      # offline, no credentials, runs in CI
uv run clinical-extraction eval --provider gemini    # real Vertex AI / Gemini run
uv run clinical-extraction extract --file case.txt   # one case → POSTable JSON
```

- **Structured output, not parsing.** Gemini is constrained by
  `response_json_schema` at `temperature=0`; there is no regex or markdown scraping.
- **Validation is mandatory.** Every response is validated with Pydantic. A schema
  violation raises `SchemaValidationError` — never retried, never "repaired" with a
  fallback. A malformed clinical extraction must surface loudly.
- **Retries are narrow.** Bounded exponential backoff for transient provider errors
  (429/5xx) only; 4xx and safety blocks fail immediately.
- **The model does not diagnose.** It records only diagnoses the source text states,
  and returns `null` for an unstated age or sex instead of estimating.
- **Provider boundary.** A `Protocol` with a Gemini implementation and a fake one, so
  the pipeline, the harness and the tests run with no network and no credentials.
- **Provenance.** Model name and prompt version travel with every extracted case.
- **Logging.** Field paths and error counts, never clinical text.

### Eval methodology

`llm_pipeline/evals/dataset.jsonl` holds 10 synthetic, de-identified vignettes with
hand-written ground truth, covering synonym answer keys, differentials, all seven
finding categories and one case with unstated demographics.

Metrics are deterministic — no LLM-as-a-judge: `schema_valid_rate`, age/sex accuracy,
`answer_key_accuracy` (exact set match of accepted correct diagnoses), findings
precision / recall / F1, finding-category accuracy, `exact_case_match_rate`, plus the
id and reason for every failure.

The offline fixtures deliberately inject four known defects (a dropped finding, a
missing synonym, a nulled age, an invalid category), so the harness is *proven* to
detect errors instead of always reporting a perfect score. CI asserts those exact four
failures and gates on the resulting metrics.

> `--provider gemini` was **not** run for this submission: no GCP project with Vertex AI
> billing was provisioned for the assignment. `evals/results/` therefore contains only
> the offline run. Nothing is fabricated — see `docs/REPORT.md`.

## Tests and checks

| Suite | What it covers |
|---|---|
| `backend` — 41 tests, 98% | real PostgreSQL via Alembic; create/read/score; answer-key non-leakage on the raw body; normalization; submission persistence; transaction rollback; migration up/down/up; drift check; production fail-closed config; 503 readiness; no internals in errors |
| `llm_pipeline` — 48 tests, 94% | structured-output config; validation failures with no fallback; retry boundaries; input guards; every eval metric; dataset integrity and PHI markers; contract alignment with the live OpenAPI; Gemini error classification against a stubbed SDK |
| `frontend` — 4 tests | form submission, pending state, score rendering, accessible error handling, finding grouping |
| `scripts/smoke.sh` | the real stack: auth required, create → read → score → persist, answer key absent from both API and rendered HTML |

```bash
make check     # lint + typecheck + tests + offline eval
make smoke     # against a running stack
```

CI (`.github/workflows/ci.yml`) runs all of it plus a Docker build with the smoke test,
contract-drift checks, `gitleaks` over the full history, `pip-audit` and `npm audit`.
It needs no secrets.

## Security decisions

| Decision | Why |
|---|---|
| Answer key never in a public response | the obvious failure mode is a `CaseResponse` that ships `is_correct` and is read straight off the Network tab |
| Authoring behind `X-Admin-API-Key`, compared with `hmac.compare_digest` | writing cases and answer keys is privileged; constant-time comparison avoids a timing oracle |
| Fail closed in production | `ENVIRONMENT=production` without `ADMIN_API_KEY` refuses to start, and `/docs` + `/openapi.json` are disabled |
| Strict input validation | `extra="forbid"`, length and range limits on every field, `UUID` path types, and DB `CHECK` constraints as the last line |
| Generic error bodies | handlers return `{"detail": "..."}`; stack traces, SQL and connection strings stay in the logs |
| No clinical text in logs | structured JSON logs carry ids, status, duration, field paths — never bodies or prompts. Pydantic embeds offending input values in its messages, so validation failures are logged without `exc_info`; a test asserts it |
| LLM output is untrusted input | schema-constrained generation *and* Pydantic validation before anything reaches the database |
| Secrets never in git | `.env` ignored, `.env.example` only, Secret Manager in production, `gitleaks` over full history in CI |
| Security headers | `nosniff`, `DENY`, `no-referrer`, `no-store` on API responses; the same set on the frontend |
| Bounded DB pool | Cloud Run multiplies connections by instances; pool size and `max-instances` are sized together (see `infra/DEPLOYMENT.md`) |

## Trade-offs

1. **Sync SQLAlchemy, not async.** This workload is a handful of short queries per
   request; async would add contagion and a second driver without changing throughput
   at this scale. Cloud Run scales out by instance, and the pool is sized for that.
2. **Monorepo, not three repositories.** The three tasks share one contract. A single
   repo makes the OpenAPI → TypeScript generation and the contract-alignment test real
   CI gates instead of a convention.
3. **No repository layer.** Services own transactions and use SQLAlchemy directly. A
   repository abstraction here would add indirection without a second persistence target.
4. **Exact-match scoring, not semantic.** Explainable and reproducible: a physician can
   be told exactly why an answer scored what it did, and the same submission always
   scores the same. Synonyms are modelled explicitly as extra answer rows — a product
   decision, not a model guess. Semantic matching would need its own eval and an appeal path.
5. **Fake provider in CI, real Gemini opt-in.** CI stays free, offline and deterministic
   while still exercising the whole pipeline; the real run is one flag away.
6. **Admin API key, not full auth.** It closes the authoring hole within the assignment's
   scope without pretending to be an identity system.

## Production next steps

Deliberately out of scope here, in rough priority order: participant authentication and
authorization (who may solve what, one scored attempt per case); rate limiting on
`/score`; an append-only audit trail with actor identity; idempotency keys for authoring;
a PHI/privacy, retention and BAA review before any real patient data; alerting and uptime
checks on top of the structured logs; a human review queue for LLM-extracted cases before
they go live; and a larger eval set with inter-rater agreement on the ground truth.

## Documentation

- [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — assumptions, schema decisions, stages
- [`docs/REPORT.md`](docs/REPORT.md) — the written report: what was built, what was actually executed, and what was not
- [`infra/DEPLOYMENT.md`](infra/DEPLOYMENT.md) — Cloud Run + Cloud SQL runbook, including pool sizing and rollback
- [`llm_pipeline/evals/README.md`](llm_pipeline/evals/README.md) — the eval dataset and how it is built

## Assumptions

The assignment gives no exact JSON schema, so this one is fixed and stated here:
`title`, optional `patient_age` / `patient_sex`, `presentation`, at least one finding
from a closed 7-value category enum, and an answer key of at least one correct answer
with `score_weight > 0`. Several correct synonyms and partial-credit differentials are
allowed; a differential may not outweigh the correct answer. All clinical content in
this repository is **synthetic** — no real patient data, anywhere.
