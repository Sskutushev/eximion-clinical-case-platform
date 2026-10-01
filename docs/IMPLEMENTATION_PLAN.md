# Implementation plan

## Scope

One vertical slice, one contract:

```
raw clinical text ─► LLM extraction ─► ClinicalCaseCreate ─► FastAPI ─► PostgreSQL
                                                                 │
                     Next.js (Server Component render) ◄─────────┘
                     Client form ─► Server Action ─► POST /score ─► deterministic scoring
```

## Assumptions (the assignment gives no exact JSON schema)

| Topic | Decision |
|---|---|
| Case schema | `title`, `patient_age?`, `patient_sex?`, `presentation`, `findings[{category, value}]`, `answers[{text, is_correct, score_weight}]`, `provenance?` |
| Finding categories | closed enum: `history, symptom, vital_sign, physical_exam, laboratory, imaging, other` |
| Answer key | several accepted (synonym) diagnoses per case allowed; optional partial-credit answers (`is_correct=false`, `score_weight>0`) |
| Scoring | NFKC → casefold → collapse whitespace → strip edge punctuation, then exact match against the stored normalized key. No LLM in scoring. |
| `max_score` | highest weight among correct answers |
| Feedback | outcome (`correct / partially_correct / incorrect`) — the correct answer is **not** revealed (competition setting, repeated attempts) |
| Authoring | `POST /cases` is an authoring operation guarded by `X-Admin-API-Key` (mandatory in production); solving/scoring is public |
| Patient data | only synthetic examples; no PHI anywhere in repo, logs or fixtures |

## Security invariant

The answer key is stored by the backend and **never** leaves it before a submission:
ORM models are never serialized; `PublicClinicalCase` schema has no answer fields;
the public query does not even load the `answers` relationship. Covered by tests that
inspect the raw HTTP body.

## Shared types

FastAPI OpenAPI is the source of truth → `contracts/openapi.json` (committed, drift-checked in CI)
→ `openapi-typescript` → `frontend/src/generated/api.d.ts` → typed `openapi-fetch` client.
The LLM pipeline validates its output against the same `ClinicalCaseCreate` JSON Schema in tests.

## Stages

| Stage | Deliverable | Gate |
|---|---|---|
| A | repo bootstrap, plan, configs | — |
| B | DB models, Alembic migration, services, API | ruff, mypy --strict |
| C | backend tests on real PostgreSQL | pytest (+ `alembic check` drift) |
| D | OpenAPI export → TS types, Next.js pages | contract drift check |
| E | frontend lint/typecheck/tests/build | eslint, tsc, vitest, next build |
| F | LLM extraction: provider boundary, Gemini, fake | ruff, mypy, pytest |
| G | eval dataset + harness + CI thresholds | fake eval gate |
| H | Dockerfiles, compose, local e2e smoke | compose up + smoke script |
| I | CI/CD, security scanning, GCP deployment docs | GitHub Actions green |
| J | README, REPORT.md, Word | — |
| K | clean-checkout audit | all of the above from a fresh clone |

## Out of scope (documented as production next steps)

End-user auth/authz, rate limiting, audit trail, HIPAA/BAA review, data retention policy,
idempotency keys for authoring, multi-step cases.
