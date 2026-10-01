# Deployment: Cloud Run + Cloud SQL

> **Status:** the commands below are the reproducible deployment path for this service.
> A live GCP deployment was **not performed** for this assignment — no project or billing
> account was provisioned for it. Everything else in this repo (migrations, tests, the
> Docker images, the end-to-end smoke test) was executed locally; see `docs/REPORT.md`.

Architecture:

```
Artifact Registry ──► Cloud Run (frontend, public)
                             │  server-side fetch, internal ingress
                             ▼
                      Cloud Run (backend, internal + LB)
                             │  Cloud SQL connector (private IP)
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
export TAG="$(git rev-parse --short HEAD)"

gcloud config set project "${PROJECT_ID}"
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  artifactregistry.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com aiplatform.googleapis.com
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

docker build --platform linux/amd64 -t "${BACKEND_IMAGE}" ./backend
docker build --platform linux/amd64 -t "${FRONTEND_IMAGE}" ./frontend
docker push "${BACKEND_IMAGE}"
docker push "${FRONTEND_IMAGE}"
```

## 3. Cloud SQL for PostgreSQL

```bash
gcloud sql instances create "${SQL_INSTANCE}" \
  --database-version=POSTGRES_17 \
  --region="${REGION}" \
  --tier=db-custom-2-7680 \
  --storage-type=SSD --storage-size=20GB --storage-auto-increase \
  --availability-type=REGIONAL \
  --backup-start-time=02:00 \
  --enable-point-in-time-recovery \
  --no-assign-ip --network="projects/${PROJECT_ID}/global/networks/default" \
  --database-flags=max_connections=200

gcloud sql databases create "${DB_NAME}" --instance="${SQL_INSTANCE}"

# Generated locally, stored only in Secret Manager — never in git or in a shell history file.
DB_PASSWORD="$(openssl rand -base64 32)"
gcloud sql users create "${DB_USER}" --instance="${SQL_INSTANCE}" --password="${DB_PASSWORD}"
```

`--no-assign-ip` keeps the instance off the public internet; Cloud Run reaches it over
the Cloud SQL connector. Point-in-time recovery and regional availability are on because
submissions are an audit record of a competition.

## 4. Secrets

```bash
printf '%s' "${DB_PASSWORD}" | gcloud secrets create eximion-db-password --data-file=-
printf '%s' "$(openssl rand -hex 32)" | gcloud secrets create eximion-admin-api-key --data-file=-
unset DB_PASSWORD
```

Secrets are mounted as environment variables at runtime; they are never baked into an
image layer and never passed as `docker build --build-arg`.

## 5. Service accounts (least privilege)

One identity per workload, each with only the roles it needs.

```bash
for sa in "${BACKEND_SA}" "${FRONTEND_SA}" "${MIGRATOR_SA}"; do
  gcloud iam service-accounts create "${sa}" --display-name="${sa}"
done

# Backend: connect to Cloud SQL, read its two secrets, call Vertex AI.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BACKEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
for secret in eximion-db-password eximion-admin-api-key; do
  gcloud secrets add-iam-policy-binding "${secret}" \
    --member="serviceAccount:${BACKEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BACKEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

# Migrator: Cloud SQL + the DB password only. It runs DDL, so it is kept separate
# from the serving identity and is not attached to any long-running service.
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${MIGRATOR_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"
gcloud secrets add-iam-policy-binding eximion-db-password \
  --member="serviceAccount:${MIGRATOR_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Frontend: no database, no secrets. It only needs to invoke the backend.
```

## 6. Migrations as a controlled step

Migrations run as their own Cloud Run **Job**, executed deliberately before the new
revision is deployed. They are *not* run on container startup: with autoscaling, N
instances would race on the same DDL, and a failed migration would crash-loop the
service instead of failing one job.

```bash
INSTANCE_CONN="${PROJECT_ID}:${REGION}:${SQL_INSTANCE}"
SOCKET_URL="postgresql+psycopg://${DB_USER}:\${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${INSTANCE_CONN}"

gcloud run jobs deploy eximion-migrate \
  --image="${BACKEND_IMAGE}" \
  --region="${REGION}" \
  --service-account="${MIGRATOR_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances="${INSTANCE_CONN}" \
  --set-secrets="DB_PASSWORD=eximion-db-password:latest" \
  --set-env-vars="^|^DATABASE_URL=${SOCKET_URL}|ENVIRONMENT=production" \
  --command="alembic" --args="upgrade,head" \
  --max-retries=0 --task-timeout=10m

gcloud run jobs execute eximion-migrate --region="${REGION}" --wait
```

Rollout order for a schema change: deploy backwards-compatible DDL first, then the new
revision, then (in a later release) drop what is no longer used. That keeps the previous
revision runnable, which is what makes step 9 a real rollback.

## 7. Deploy the backend

```bash
gcloud run deploy eximion-backend \
  --image="${BACKEND_IMAGE}" \
  --region="${REGION}" \
  --service-account="${BACKEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-cloudsql-instances="${INSTANCE_CONN}" \
  --set-secrets="DB_PASSWORD=eximion-db-password:latest,ADMIN_API_KEY=eximion-admin-api-key:latest" \
  --set-env-vars="^|^DATABASE_URL=${SOCKET_URL}|ENVIRONMENT=production|LOG_LEVEL=INFO|DB_POOL_SIZE=5|DB_MAX_OVERFLOW=2|GOOGLE_CLOUD_PROJECT=${PROJECT_ID}|GOOGLE_CLOUD_LOCATION=${REGION}" \
  --min-instances=1 --max-instances=10 --concurrency=80 \
  --cpu=1 --memory=512Mi --timeout=30s \
  --ingress=internal-and-cloud-load-balancing \
  --no-allow-unauthenticated
```

**Connection pool sizing.** Cloud Run multiplies connections by instance count:
`max-instances × (DB_POOL_SIZE + DB_MAX_OVERFLOW)` = `10 × 7` = **70** connections
against `max_connections=200`, leaving headroom for the migration job, psql sessions
and a second service. Raising `max-instances` without lowering the pool is the standard
way to exhaust a Cloud SQL instance, so the two numbers are reviewed together.
`ENVIRONMENT=production` also makes the app refuse to start without `ADMIN_API_KEY`
and disables `/docs` and `/openapi.json`.

## 8. Deploy the frontend

```bash
gcloud run deploy eximion-frontend \
  --image="${FRONTEND_IMAGE}" \
  --region="${REGION}" \
  --service-account="${FRONTEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --set-env-vars="API_BASE_URL=$(gcloud run services describe eximion-backend --region="${REGION}" --format='value(status.url)'),NODE_ENV=production" \
  --min-instances=1 --max-instances=10 --concurrency=80 \
  --cpu=1 --memory=512Mi \
  --allow-unauthenticated

# The browser never calls the API, so let only the frontend identity invoke the backend.
gcloud run services add-iam-policy-binding eximion-backend \
  --region="${REGION}" \
  --member="serviceAccount:${FRONTEND_SA}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

`API_BASE_URL` is read server-side only (it is not `NEXT_PUBLIC_*`), so the backend URL
is never shipped to the browser.

## 9. Verify, then roll back if needed

```bash
BACKEND_URL="$(gcloud run services describe eximion-backend --region="${REGION}" --format='value(status.url)')"
WEB_URL="$(gcloud run services describe eximion-frontend --region="${REGION}" --format='value(status.url)')"

# Smoke test the deployed stack with the same script CI uses.
TOKEN="$(gcloud auth print-identity-token)"
curl -fsS -H "Authorization: Bearer ${TOKEN}" "${BACKEND_URL}/health/ready"
API_BASE_URL="${BACKEND_URL}" WEB_BASE_URL="${WEB_URL}" \
  ADMIN_API_KEY="$(gcloud secrets versions access latest --secret=eximion-admin-api-key)" \
  bash scripts/smoke.sh

gcloud logging read \
  'resource.type="cloud_run_revision" AND severity>=WARNING' --limit=50 --freshness=10m
```

Rollback is a traffic shift to the previous revision — no rebuild, no image pull:

```bash
gcloud run revisions list --service=eximion-backend --region="${REGION}"
gcloud run services update-traffic eximion-backend \
  --region="${REGION}" --to-revisions="<previous-revision>=100"
```

For a gradual rollout, split traffic instead: `--to-revisions="<new>=10,<previous>=90"`,
watch the error rate, then move to 100%.

## 10. Notes and limits

- **Vertex AI / Gemini** uses the backend service account via Application Default
  Credentials — no API key is stored anywhere. Extraction is an authoring-time
  operation; it is not on the request path of a physician solving a case.
- **Cold starts**: `min-instances=1` keeps one warm instance per service; the extraction
  pipeline is a batch/CLI workload and does not need warm capacity.
- **Not configured here** (out of scope for the assignment, listed in `docs/REPORT.md`):
  custom domain and Cloud Armor, end-user authentication, rate limiting, uptime checks
  and alerting policies, a dedicated audit-log sink, and a data retention policy.
