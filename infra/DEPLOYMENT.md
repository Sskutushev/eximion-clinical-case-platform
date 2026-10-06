# Deployment: Cloud Run + Cloud SQL

> **Status:** the commands below are the reproducible deployment path for this service.
> A live GCP deployment was **not performed** for this assignment — no project or billing
> account was provisioned for it. Everything else in this repo (migrations, tests, the
> Docker images, the end-to-end smoke test) was executed locally; see `docs/REPORT.md`.

Architecture:

```
Artifact Registry ──► Cloud Run (frontend, public)
                             │  server-side fetch, ID token
                             ▼
                      Cloud Run (backend, IAM-only: ingress=all, no-allow-unauthenticated)
                             │  private IP :5432 over Direct VPC egress
                             ▼
                      Cloud SQL for PostgreSQL 17
   Secret Manager ──────────┘   (DB password, admin API key)
   Cloud Run Job ─────────────► alembic upgrade head  (controlled, pre-deploy)
```

## 0. Variables

```bash
export PROJECT_ID="<your-project-id>"
export REGION="europe-west1"
export REPO="eximion"
export SQL_INSTANCE="eximion-pg"
export DB_NAME="eximion"
export DB_USER="eximion_app"
export BACKEND_SA="eximion-backend"
export FRONTEND_SA="eximion-frontend"
export MIGRATOR_SA="eximion-migrator"
export EXTRACTION_SA="eximion-extraction"
export TAG="$(git rev-parse --short HEAD)"

gcloud config set project "${PROJECT_ID}"
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com aiplatform.googleapis.com \
  compute.googleapis.com servicenetworking.googleapis.com
```

## 1. Artifact Registry

```bash
gcloud artifacts repositories create "${REPO}" \
  --repository-format=docker --location="${REGION}" \
  --description="Eximion clinical case platform images"

gcloud auth configure-docker "${REGION}-docker.pkg.dev"
```

## 2. Build and push images

Images are tagged with the commit SHA — never `latest` — so every Cloud Run revision
is traceable to a commit and rollback is unambiguous.

```bash
BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:${TAG}"
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend:${TAG}"
EXTRACTION_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/extraction:${TAG}"

docker build --platform linux/amd64 -t "${BACKEND_IMAGE}" ./backend
docker build --platform linux/amd64 -t "${FRONTEND_IMAGE}" ./frontend
docker build --platform linux/amd64 -t "${EXTRACTION_IMAGE}" ./llm_pipeline

docker push "${BACKEND_IMAGE}"
docker push "${FRONTEND_IMAGE}"
docker push "${EXTRACTION_IMAGE}"
```

## 3. Networking and Cloud SQL

The instance has no public IP, so two things must exist before Cloud Run can
reach it: a Private Services Access range for Google to peer the instance into,
and a path out of Cloud Run into that VPC.

```bash
# Private Services Access: the range Google allocates the Cloud SQL instance in.
gcloud compute addresses create google-managed-services-default \
  --global --purpose=VPC_PEERING --prefix-length=16 --network=default

gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-default \
  --network=default
```

```bash
gcloud sql instances create "${SQL_INSTANCE}" \
  --database-version=POSTGRES_17 \
  --region="${REGION}" \
  --tier=db-custom-2-7680 \
  --storage-type=SSD --storage-size=20GB --storage-auto-increase \
  --availability-type=REGIONAL \
  --backup-start-time=02:00 \
  --enable-point-in-time-recovery \
  --no-assign-ip \
  --network="projects/${PROJECT_ID}/global/networks/default" \
  --ssl-mode=ENCRYPTED_ONLY \
  --database-flags=max_connections=200

gcloud sql databases create "${DB_NAME}" --instance="${SQL_INSTANCE}"

# The instance has exactly one address, the private one. The services connect to it.
DB_PRIVATE_IP="$(gcloud sql instances describe "${SQL_INSTANCE}" \
  --format='get(ipAddresses[0].ipAddress)')"

# Generated locally, stored only in Secret Manager. Never echoed, never in git.
DB_PASSWORD="$(openssl rand -base64 32)"
gcloud sql users create "${DB_USER}" --instance="${SQL_INSTANCE}" --password="${DB_PASSWORD}"
```

Point-in-time recovery and regional availability are on because submissions are
the audit record of a competition.

Each Cloud Run service below is deployed with **Direct VPC egress**
(`--network` / `--subnet`), which is the current recommended path and avoids
running a Serverless VPC Access connector. Through that path the application
connects to the instance's private IP on port 5432 — `DB_HOST` — as an ordinary
PostgreSQL client. `--ssl-mode=ENCRYPTED_ONLY` makes the instance refuse a
plaintext session, and psycopg negotiates TLS by default, so the traffic is
encrypted inside the VPC as well.

**One connection path, deliberately.** The managed `--set-cloudsql-instances`
Unix socket is the Auth Proxy path; by default it reaches the instance over its
public IP, which this instance does not have. Pairing it with a private-only
instance either requires the proxy in private-IP mode or does not connect at all.
The first runbook mixed the two. Now there is no proxy, no socket and no
`cloudsql.client` role: the database is reached by network path plus password,
and the network path is the VPC.

## 4. Secrets

```bash
printf '%s' "${DB_PASSWORD}" | gcloud secrets create eximion-db-password --data-file=-
printf '%s' "$(openssl rand -hex 32)" | gcloud secrets create eximion-admin-api-key --data-file=-
unset DB_PASSWORD
```

Secrets are mounted as environment variables at runtime. They are never baked
into an image layer and never passed as `docker build --build-arg`.

**Cloud Run does not expand variable references inside environment values.** A
`DATABASE_URL` containing `${DB_PASSWORD}` would arrive at the process with that
text as the password. So the service receives `DB_USER`, `DB_PASSWORD`,
`DB_NAME` and `DB_HOST` separately and assembles the URL at
runtime (`Settings.sqlalchemy_url`), which also escapes a generated password
containing `/`, `@` or `:` correctly. `tests/test_config.py` covers both.

## 5. Service accounts (least privilege)

One identity per workload, each holding only what that workload uses.

```bash
for sa in "${BACKEND_SA}" "${FRONTEND_SA}" "${MIGRATOR_SA}" "${EXTRACTION_SA}"; do
  gcloud iam service-accounts create "${sa}" --display-name="${sa}"
done

# Backend: its two secrets. No cloudsql.client — that role authorizes the Auth
# Proxy and the connectors, and over private IP the database is reached by
# network path plus password, not by IAM. It does not call Vertex AI —
# extraction does — so it gets no aiplatform role either.
for secret in eximion-db-password eximion-admin-api-key; do
  gcloud secrets add-iam-policy-binding "${secret}" \
    --member="serviceAccount:${BACKEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done

# Migrator: the database password only. It runs DDL, so it is kept separate from
# the serving identity and is attached to no long-running service.
gcloud secrets add-iam-policy-binding eximion-db-password \
  --member="serviceAccount:${MIGRATOR_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Extraction job: Vertex AI only. The CLI prints a case to stdout for a human to
# review; it does not write to the API, so it holds no admin key and no database
# access. Publishing extracted cases is a production next step with a review
# boundary, and the permission belongs with that work, not before it.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${EXTRACTION_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Frontend: no database, no secrets. It only invokes the backend (granted in §8).
```

## 6. Migrations as a controlled step

Migrations run as their own Cloud Run **Job**, executed deliberately before the
new revision is deployed. Not on container startup: with autoscaling, N
instances would race on the same DDL, and a failed migration would crash-loop
the service instead of failing one job.

```bash
gcloud run jobs deploy eximion-migrate \
  --image="${BACKEND_IMAGE}" \
  --region="${REGION}" \
  --service-account="${MIGRATOR_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --network=default --subnet=default --vpc-egress=private-ranges-only \
  --set-secrets="DB_PASSWORD=eximion-db-password:latest" \
  --set-env-vars="ENVIRONMENT=production,DB_USER=${DB_USER},DB_NAME=${DB_NAME},DB_HOST=${DB_PRIVATE_IP}" \
  --command="alembic" --args="upgrade,head" \
  --max-retries=0 --task-timeout=10m

gcloud run jobs execute eximion-migrate --region="${REGION}" --wait
```

This job carries no admin API key and does not need one. The production check
for that key lives in `create_app()` rather than in `Settings`, precisely
because Alembic loads the same settings without ever serving a request — putting
that check on `Settings` would fail this job before it ran a single statement.

Rollout order for a schema change: backwards-compatible DDL first, then the new
revision, then drop what is no longer used in a later release. That keeps the
previous revision runnable, which is what makes the rollback in §10 real.

## 7. Deploy the backend

```bash
gcloud run deploy eximion-backend \
  --image="${BACKEND_IMAGE}" \
  --region="${REGION}" \
  --service-account="${BACKEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --network=default --subnet=default --vpc-egress=private-ranges-only \
  --set-secrets="DB_PASSWORD=eximion-db-password:latest,ADMIN_API_KEY=eximion-admin-api-key:latest" \
  --set-env-vars="ENVIRONMENT=production,LOG_LEVEL=INFO,DB_USER=${DB_USER},DB_NAME=${DB_NAME},DB_HOST=${DB_PRIVATE_IP},DB_POOL_SIZE=5,DB_MAX_OVERFLOW=2" \
  --min-instances=1 --max-instances=10 --concurrency=80 \
  --cpu=1 --memory=512Mi --timeout=30s \
  --ingress=all \
  --no-allow-unauthenticated
```

**Why `--ingress=all` and not internal.** The backend is closed by IAM: without
`roles/run.invoker` and a valid ID token nobody gets past the front door, on any
network. Internal ingress would add a second lock, but it is a *network* control,
and the frontend is not on the VPC — one Cloud Run service calling another over
internal ingress has to egress through a VPC that counts as internal. Setting
internal ingress without putting the frontend on that VPC does not harden the
service, it breaks it, and it breaks the verification in §10 as well. Putting the
frontend on a VPC for this is more moving parts than this system needs, so IAM
alone is the trade — deliberately, not by oversight.

**Connection pool sizing.** Cloud Run multiplies connections by instance count:
`max-instances × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` = `10 × 7` = **70** against
`max_connections=200`, leaving headroom for the migration job, psql sessions and
a second service. Raising `max-instances` without lowering the pool is the usual
way to exhaust a Cloud SQL instance, so the two are reviewed together.

`ENVIRONMENT=production` also makes the app refuse to start without
`ADMIN_API_KEY` and disables `/docs` and `/openapi.json`.

## 8. Deploy the frontend

```bash
BACKEND_URL="$(gcloud run services describe eximion-backend \
  --region="${REGION}" --format='value(status.url)')"

gcloud run deploy eximion-frontend \
  --image="${FRONTEND_IMAGE}" \
  --region="${REGION}" \
  --service-account="${FRONTEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="NODE_ENV=production,API_BASE_URL=${BACKEND_URL}" \
  --min-instances=1 --max-instances=10 --concurrency=80 \
  --cpu=1 --memory=512Mi \
  --allow-unauthenticated

# The browser never calls the API, so only the frontend identity may invoke it.
gcloud run services add-iam-policy-binding eximion-backend \
  --region="${REGION}" \
  --member="serviceAccount:${FRONTEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**`run.invoker` permits a call; it does not authenticate one.** A private Cloud
Run service still requires a Google-signed ID token whose audience is the target
service URL. The frontend fetches one from the instance metadata server and
attaches it to every backend request — see `frontend/src/lib/api/auth.ts`, wired
into the client as a middleware. Outside Cloud Run (`K_SERVICE` unset) it adds
nothing, so local development is unchanged. Covered by `auth.test.ts`.

`API_BASE_URL` is read server-side only (it is not `NEXT_PUBLIC_*`), so the
backend URL never reaches the browser — and it doubles as the token audience.

## 9. Deploy the extraction pipeline (Cloud Run Job)

Extraction is batch work: an editor feeds in clinical text and gets a structured
case to review. It is not on a physician's request path, so it is a Job, not a
service — no idle cost, and it cannot take traffic.

```bash
gcloud run jobs deploy eximion-extraction \
  --image="${EXTRACTION_IMAGE}" \
  --region="${REGION}" \
  --service-account="${EXTRACTION_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GEMINI_MODEL=gemini-2.5-flash" \
  --cpu=1 --memory=1Gi --max-retries=1 --task-timeout=15m \
  --args="eval,--provider,gemini"
```

Run it to measure the accuracy of the current model and prompt:

```bash
gcloud run jobs execute eximion-extraction --region="${REGION}" --wait
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="eximion-extraction"' \
  --limit=20 --freshness=10m
```

Notes:

- Vertex AI is reached through the job's service account (ADC). There is no API key.
- Run this after a model or prompt change: if the metrics drop, the change does
  not ship.
- The CLI writes the extracted case to stdout for a human to review. It does not
  post to the API, which is why this identity holds no admin key — publishing
  extracted cases needs a review boundary first, and that is a production next step.
- Verification with Jev (`--verify typesafe`, see `docs/DECISION_MODEL_MIGRATION.md`)
  is off by default. Turning it on needs one more secret, mounted on this job only:

  ```bash
  printf '%s' "${TYPESAFE_API_KEY}" | gcloud secrets create eximion-typesafe-api-key --data-file=-
  gcloud secrets add-iam-policy-binding eximion-typesafe-api-key \
    --member="serviceAccount:${EXTRACTION_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
  gcloud run jobs update eximion-extraction --region="${REGION}" \
    --set-secrets="TYPESAFE_API_KEY=eximion-typesafe-api-key:latest"
  ```

  Synthetic data only, unless a privacy and security review confirms PHI use is
  permitted and the required contractual controls, including a BAA if applicable, are
  in place. The local models ship inside the image and need no secret.

## 10. Verify, then roll back if needed

```bash
WEB_URL="$(gcloud run services describe eximion-frontend \
  --region="${REGION}" --format='value(status.url)')"

# The backend is private, so direct calls need an identity token.
export ID_TOKEN="$(gcloud auth print-identity-token)"
curl -fsS -H "Authorization: Bearer ${ID_TOKEN}" "${BACKEND_URL}/health/ready"

# The same smoke test CI runs, pointed at the deployed stack.
API_BASE_URL="${BACKEND_URL}" WEB_BASE_URL="${WEB_URL}" \
  ADMIN_API_KEY="$(gcloud secrets versions access latest --secret=eximion-admin-api-key)" \
  bash scripts/smoke.sh

gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=WARNING' --limit=50 --freshness=10m
```

`smoke.sh` picks up `ID_TOKEN` from the environment and sends it on every
backend call, so it works against a private service unchanged.

Rollback is a traffic shift to the previous revision — no rebuild, no image pull:

```bash
gcloud run revisions list --service=eximion-backend --region="${REGION}"
gcloud run services update-traffic eximion-backend \
  --region="${REGION}" --to-revisions="<previous-revision>=100"
```

For a gradual rollout, split traffic instead:
`--to-revisions="<new>=10,<previous>=90"`, watch the error rate, then move to 100%.

## 11. Notes and limits

- **Cold starts**: `min-instances=1` keeps one warm instance per service. The
  extraction job is batch work and needs no warm capacity.
- **Not configured here**, and listed as production next steps in
  `docs/REPORT.md`: custom domain and Cloud Armor, end-user authentication,
  rate limiting, uptime checks and alerting policies, a dedicated audit-log
  sink, and a data retention policy.
- **Not executed.** No GCP project with billing was provisioned for this
  assignment, so none of the above was run against a live account. The commands
  are the path I would follow, not a transcript of one I ran.
