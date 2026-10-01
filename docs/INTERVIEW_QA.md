# Разбор вопросов по тестовому

Подготовка к разговору с CEO и техническими проверяющими Eximion.

Формат: **вопрос** (как его зададут) → **что ответить** (готовая английская фраза) →
*почему так* (заметка для себя).

Главное правило: отвечай коротко, затем остановись. Длинный ответ без паузы
читается как неуверенность. Если не знаешь — скажи «I have not done that; here is
what I would do» и дай план. Это сильнее, чем попытка натянуть.

---

## 1. Архитектура и общие решения

**Why one repository instead of three?**

> The three tasks share one domain contract. FastAPI publishes OpenAPI, the frontend
> generates its types from it, and the extraction pipeline validates its output against
> the same document. In one repo, CI can fail when any of the three drift apart. In three
> repos that is a convention; here it is a gate.

*Это твой самый сильный архитектурный ответ. Начинай с него, если спросят про структуру.*

---

**Walk me through the request flow.**

> A physician opens `/cases/{id}`. That is a Server Component, so the fetch happens on the
> server and the browser never talks to the API directly. It renders the case without the
> answer key. The diagnosis form is the only Client Component. Submitting goes through a
> Server Action to `POST /cases/{id}/score`, the backend normalizes the answer, matches it
> against the stored key, persists the submission and returns the score.

---

**Why is scoring server-side? Could it not be done in the browser?**

> Only if the browser had the answer key, which is exactly what must never happen.
> The key stays in the database and the score is computed there.

---

**What was the hardest decision here?**

> Scoring. Exact match is explainable and reproducible — a physician can be told precisely
> why an answer scored what it did, and the same answer always scores the same. Semantic
> matching would accept more phrasings but needs its own evaluation, a confidence threshold
> and an appeal path before it can be trusted to score a competition. I modelled synonyms
> explicitly as extra answer rows instead: a product decision, not a model guess.

*Лучший ответ на «что было сложным» — не технический баг, а решение с trade-off.*

---

## 2. Backend и база

**Why synchronous SQLAlchemy and not async?**

> A few short queries per request. Async adds a second driver and colours every call site
> without changing throughput at this scale. Cloud Run scales out by instance, and the pool
> is sized for that. If a slow external call entered the request path, I would reconsider.

---

**Why normalized tables and not JSONB?**

> Findings and answers need to be queryable and constrainable. Each enum and range is a
> `CHECK`, answer uniqueness is a `UNIQUE`, and `score <= max_score` is enforced by the
> database rather than trusted from the application. JSONB holds only optional extraction
> provenance, which has no schema obligations.

---

**Why `ON DELETE RESTRICT` on submissions but `CASCADE` elsewhere?**

> Findings and answers belong to the case. Submissions are an audit record of a competition
> — a case with recorded attempts must not lose its trail because someone deleted the case.

*Это тот ответ, который отличает «написал CRUD» от «подумал о домене».*

---

**How do you handle migrations in production?**

> As a separate Cloud Run Job, run deliberately before the new revision. Not on container
> startup: with autoscaling, N instances would race on the same DDL, and a failed migration
> would crash-loop the service instead of failing one job. The job runs under its own
> service account that has Cloud SQL access but is not attached to any serving revision.

---

**How do you know the models and migrations have not drifted?**

> `alembic check` runs in CI. It fails if the ORM models no longer match the migrations.
> Tests also build the database by running the real migration, never `create_all`.

---

**How did you size the connection pool?**

> Cloud Run multiplies connections by instance count. Max instances times pool plus overflow
> is 10 × 7 = 70 against `max_connections` of 200, which leaves headroom for the migration
> job and operator sessions. Raising max instances without lowering the pool is the standard
> way to exhaust a Cloud SQL instance, so the two numbers are reviewed together.

*Если спросят про GCP — вот конкретика, которая показывает прод-опыт.*

---

## 3. Фронтенд

**How do the frontend and backend share types?**

> FastAPI's OpenAPI document is the source of truth. It is exported to
> `contracts/openapi.json`, `openapi-typescript` generates the TypeScript types from it, and
> the frontend uses them through a typed `openapi-fetch` client. Both artefacts are
> committed and CI regenerates them and fails on any diff, so the contract cannot drift.

---

**Why a Server Action rather than fetching from the client?**

> The browser then never calls the API. The backend URL is server-side only, so it is not in
> the bundle, and there is no CORS surface to configure. In production the backend can be
> deployed with internal ingress and only the frontend's service account can invoke it.

---

**What is a Client Component here and why?**

> Only the diagnosis form. It needs pending state and a result. Everything else — the case,
> the findings, the layout — is a Server Component, so none of it ships JavaScript and none
> of it can reach the answer key.

---

**How do you handle a backend failure in the UI?**

> API failures are a typed result: `not_found`, `invalid` or `unavailable`, not thrown
> strings. Each is handled explicitly, the user gets a sensible message, and the details stay
> in the server log. The page has `loading`, `not-found` and `error` boundaries.

---

**Internationalisation — why, and what did it cost?**

> Seven languages, and Arabic drives the real work: the document carries `dir="rtl"` and the
> CSS uses logical properties, so padding, insets and icons follow the reading direction.
> Clinical content is never translated — a translated finding is a clinical claim, and this
> system should not make one. Only the interface switches.

*Если спросят «зачем столько» — честный ответ: «the product is international; Arabic was
the one that forced the layout to be correct rather than merely translated».*

---

## 4. LLM-пайплайн

**How do you get structured output from Gemini?**

> Native structured output: the model is constrained by `response_json_schema` at temperature
> zero. There is no regex and no markdown scraping. Every response is then validated with
> Pydantic against the same contract the API accepts.

---

**What happens when the model returns something invalid?**

> It raises a typed `SchemaValidationError`. It is not retried and not repaired with a
> fallback. A malformed clinical extraction has to be loud — a silent fallback would put
> guessed clinical data into the database.

*Сильный ответ для MedTech. Подчеркни «no silent fallback».*

---

**When do you retry then?**

> Only transient provider errors — 429 and 5xx — with bounded exponential backoff. A 4xx or
> a safety block fails immediately, because retrying will not change the answer.

---

**How do you stop the model from inventing a diagnosis?**

> The prompt restricts it to diagnoses the source text states, and requires `null` for an
> unstated age or sex rather than an estimate. The eval measures exactly that: if the model
> fills in a field the source does not contain, the metric drops.

---

**How do you evaluate extraction quality?**

> Ten synthetic vignettes with hand-written ground truth and deterministic metrics: schema
> validity rate, age and sex accuracy, answer-key accuracy as an exact set match, findings
> precision, recall and F1, and the reason for every failure. No LLM-as-a-judge — with labels
> available, an exact metric is cheaper and more defensible.

---

**How do you know the eval harness itself works?**

> The offline fixtures inject four known defects on purpose: a dropped finding, a missing
> synonym, a nulled age and an invalid category. CI asserts those exact four failures. So the
> harness is shown to catch errors rather than always printing a perfect score.

*Это вопрос, который задаст сильный интервьюер. У тебя есть готовый ответ — используй.*

---

**Why answer-key accuracy as an exact set match?**

> Because a missed synonym silently rejects a valid physician answer in production. If the
> model extracts the diagnosis but drops an accepted phrasing, a doctor typing that phrasing
> gets zero. That is a user-facing failure, so the metric has to be strict.

---

**Did you run it against the real Gemini API?**

> No. No GCP project with Vertex AI billing was provisioned for this assignment, so the
> committed results are the offline run only. The Gemini path is covered by tests against a
> stubbed SDK client — structured-output configuration, error classification by status,
> empty-response handling — but I am not claiming a live run that did not happen.

*Говори это прямо и без извинений. Честность здесь — плюс, а не минус.*

---

## 5. GCP и деплой

**Walk me through the deployment.**

> Artifact Registry with images tagged by commit SHA, never `latest`. Cloud SQL on a private
> IP with point-in-time recovery. Secrets in Secret Manager, mounted at runtime, never baked
> into a layer. Four service accounts, one per workload, least privilege. Migrations as a
> Job before the new revision. Backend with internal ingress, frontend public. Rollback is a
> traffic shift to the previous revision — no rebuild.

---

**Have you deployed this to Cloud Run?**

> Not this project — there was no billing account for the assignment. The runbook is complete
> and reproducible, and I have run this shape of deployment before. I did not want to claim a
> live URL I do not have.

---

**How does the pipeline reach Vertex AI?**

> Application Default Credentials through the job's service account. There is no API key
> anywhere — not in the image, not in the environment, not in git.

---

**How would you roll back a bad release?**

> Shift traffic to the previous revision. For schema changes the rollout order matters:
> backwards-compatible DDL first, then the new revision, then drop what is unused in a later
> release. That keeps the previous revision runnable, which is what makes rollback real.

*Этот ответ показывает, что ты реально катал релизы, а не только читал про них.*

---

## 6. Безопасность

**What is the main security concern in this product?**

> The answer key. The easy failure is a response object that ships `is_correct` and gets read
> straight off the Network tab. So the public schema has no answer fields, the public read
> path does not even load the answers relationship, and the invariant is asserted three ways:
> an API test on the raw HTTP body, a contract test on the published OpenAPI, and the smoke
> test on the rendered HTML.

---

**Why the smoke test on the rendered HTML — is the API test not enough?**

> No, and that check earned its place. The diagnosis form originally had a placeholder hint
> reading "e.g. Acute appendicitis", which was the answer to the smoke-test case. The API was
> clean; the page leaked it. A unit test would not have caught that.

*Расскажи этот случай, даже если не спросят напрямую. Он очень сильный.*

---

**Tell me about a bug you found in your own code.**

> Validation failures were logged with `logger.exception`, which is the idiomatic choice and
> what the linter pushes you toward. But Pydantic embeds the offending input values in its
> error message — here, the clinical narrative. The traceback would have written patient text
> into the logs, against the logging policy stated two lines above it. Now validation
> failures log field paths and error types with no `exc_info`, and a test asserts a clinical
> marker never reaches the log.

---

**Is this HIPAA compliant?**

> No, and I would not claim it is. There is no real patient data in it, and compliance is not
> a library you add — it needs a privacy and retention review, a BAA with the cloud provider,
> an audit trail with actor identity and access controls. I listed those as production next
> steps rather than pretending the assignment covered them.

*Никогда не говори «да» на этот вопрос. Правильный ответ — именно такой.*

---

**How is authoring protected?**

> An admin API key compared with `hmac.compare_digest`, and the app refuses to start in
> production without it. That closes the hole within the scope of the assignment without
> pretending to be an identity system. Participant authentication is the first production
> next step.

---

## 7. Тестирование и качество

**What do you test, and why those things?**

> Backend: 41 tests against a real PostgreSQL built by the real migration — create, read,
> score, normalization, submission persistence, transaction rollback, migration round trip,
> production fail-closed config, and the answer key not leaking. Pipeline: 48 tests covering
> validation failures with no fallback, retry boundaries, every eval metric, dataset
> integrity and contract alignment. Frontend: component behaviour and dictionary
> completeness. Plus an end-to-end smoke test on the real stack.

---

**Why real PostgreSQL rather than SQLite or mocks?**

> The constraints are the point. `CHECK`, `UNIQUE`, cascade behaviour and transaction
> rollback are what I am relying on, and SQLite would not enforce them the same way. A mock
> would test my assumptions rather than the database.

---

**What does your CI do?**

> Twenty-four jobs, one concern each, so a red check names the problem instead of hiding in a
> monolith: lint, format and typecheck per package; migrations with a drift check and a
> downgrade round trip; tests with coverage gates; the contract drift check; the offline eval;
> secret scanning over full history; dependency audits; workflow and shell linting; per-image
> Docker builds with a non-root assertion; and the end-to-end smoke test. No secrets needed.

---

**How long did this take?**

> *(Отвечай честно и конкретно. Не занижай — это читается как хвастовство, и не завышай —
> это читается как медленно.)*

---

## 8. Продукт и процесс

**What would you build next if this were the real product?**

> Participant authentication and how many scored attempts a case allows — that is a product
> decision before it is a technical one. Then rate limiting on scoring, an append-only audit
> trail with actor identity, and a human review queue for LLM-extracted cases before they go
> live. A physician should never see a case that no human approved.

---

**How do you work when requirements are unclear?**

> I pull the requirement out of whoever owns it, decompose it, check what already exists,
> then build the smallest thing that can be validated and show it. Here there was no JSON
> schema given, so I fixed one, stated it as an assumption in the README, and moved on rather
> than blocking on a question.

---

**You used AI to build this. How much?**

> AI did a significant share of the implementation. I set the architecture, the constraints
> and the acceptance criteria, and I own the review and validation. The decisions you are
> asking me about — the answer-key invariant, the retry boundaries, the pool sizing — are
> mine, and the checks that prove them are in CI.

*Не говори «нейронка пишет код быстрее меня». Говори про architecture / constraints /
acceptance criteria / review. Для MedTech это критично.*

---

## 9. Что спросить у них

Хорошие вопросы — часть собеседования. Выбери два-три.

- How formed is the LLM pipeline today, and which part of it would be mine?
- How do cases get authored now — are physicians writing them, or is extraction meant to
  replace that?
- Who reviews an extracted case before a physician sees it?
- What does scoring look like in the real product — exact match, rubric, or human review?
- What is the current GCP setup, and what is painful about it?
- Where does the team feel slowest right now?

---

## 10. Слабые места — и как отвечать

| Риск | Честный ответ |
|---|---|
| Разговорный английский | Не извиняйся и не объясняй. Говори медленнее, короче, с паузами. Лучше простая верная фраза, чем сложная с ошибками. |
| Cloud Run / Cloud SQL — ограниченный опыт | «I have production experience with BigQuery, Cloud Storage and the APIs. Cloud Run and Cloud SQL I have set up but not owned at scale. The runbook in this repo is the shape I would follow.» |
| Нет живого деплоя | Уже отвечено выше. Прямо, без оправданий. |
| Нет реального прогона Gemini | То же. Укажи, что путь покрыт тестами на стабе. |

**Три вещи, которые надо успеть сказать за встречу:**

1. Один контракт на всю систему, и CI падает при расхождении.
2. Answer key не утекает, и это проверено тремя независимыми способами — причём
   smoke-тест поймал утечку, которую юнит-тест не поймал бы.
3. LLM под контролем: structured output, обязательная валидация, никаких silent fallback,
   и eval, в который специально вшиты дефекты, чтобы доказать, что он их ловит.
