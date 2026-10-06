# syntax=docker/dockerfile:1.7
# Batch container for the extraction pipeline.
#   extract -> raw clinical text to a case JSON
#   eval    -> accuracy of the extraction
# Runs as a Cloud Run Job, not a service: this is authoring work, not request-path work.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Deps first, so this layer is cached.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv ./.venv
COPY --chown=app:app src ./src
COPY --chown=app:app evals ./evals
# Trained local models: plain JSON, served without numpy or scikit-learn.
COPY --chown=app:app models ./models

USER app

# Credentials come from the service account at runtime, never from the image.
ENTRYPOINT ["clinical-extraction"]
CMD ["eval", "--provider", "fake"]
