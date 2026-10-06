#  Entry points for local development and CI. Run `make help` for the list.
.DEFAULT_GOAL := help
.PHONY: help up down db migrate seed openapi types test lint typecheck check smoke eval eval-gemini \
	eval-decisions eval-jev train-local clean

BACKEND := backend
FRONTEND := frontend
PIPELINE := llm_pipeline

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack (PostgreSQL, migrations, API, frontend)
	docker compose up -d --build --wait

down: ## Stop the stack and remove volumes
	docker compose down -v

db: ## Start PostgreSQL only (for running the apps from source)
	docker compose up -d --wait postgres

migrate: ## Apply Alembic migrations
	cd $(BACKEND) && uv run alembic upgrade head

seed: ## Load synthetic demo cases
	cd $(BACKEND) && uv run python -m scripts.seed

openapi: ## Re-export contracts/openapi.json from the FastAPI app
	cd $(BACKEND) && uv run python -m scripts.export_openapi

types: openapi ## Regenerate the frontend types from the OpenAPI contract
	cd $(FRONTEND) && npm run generate:types

lint: ## Lint every package
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(PIPELINE) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npm run lint

typecheck: ## Type check every package
	cd $(BACKEND) && uv run mypy app scripts tests alembic/env.py
	cd $(PIPELINE) && uv run mypy src tests
	cd $(FRONTEND) && npm run typecheck

test: ## Run all test suites (backend needs PostgreSQL)
	cd $(BACKEND) && uv run pytest --cov
	cd $(PIPELINE) && uv run pytest --cov
	cd $(FRONTEND) && npm run test

eval: ## Run the extraction eval offline (fake provider, no credentials)
	cd $(PIPELINE) && uv run clinical-extraction eval --provider fake

eval-gemini: ## Run the extraction eval against Vertex AI / Gemini (needs credentials)
	cd $(PIPELINE) && uv run clinical-extraction eval --provider gemini \
		--output evals/results/gemini-eval.json

eval-decisions: ## Run the verifier eval offline (reference verifier, local model in shadow)
	cd $(PIPELINE) && uv run clinical-extraction eval-decisions

eval-jev: ## Run the verifier eval against Jev (needs TYPESAFE_API_KEY)
	cd $(PIPELINE) && uv run clinical-extraction eval-decisions --provider typesafe \
		--output evals/results/jev-decisions.json

train-local: ## Retrain the local finding-category model (needs the ml dependency group)
	cd $(PIPELINE) && uv sync --group ml && uv run clinical-extraction train-local --task finding_category

smoke: ## End-to-end smoke test against a running stack
	bash scripts/smoke.sh

check: lint typecheck test eval eval-decisions ## Everything CI runs, except Docker

clean: ## Remove local build and cache artifacts
	cd $(FRONTEND) && rm -rf .next node_modules/.cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.pytest_cache $(PIPELINE)/.pytest_cache $(BACKEND)/.ruff_cache
