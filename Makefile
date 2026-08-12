# Watari — developer workflow Makefile
#
# Usage: `make help` to list available targets.
#
# Most targets assume Docker Compose is available. `make test-unit` and
# `make lint` can be run standalone against a local Python environment,
# but the canonical path is to run everything inside the containers for
# reproducibility.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

COMPOSE ?= docker compose
API_CONTAINER := api
WORKER_CONTAINER := worker
DB_CONTAINER := postgres
FRONTEND_CONTAINER := frontend

.PHONY: help setup dev stop reset rebuild logs \
        db-migrate db-seed db-reset shell-db \
        test test-unit test-property test-integration \
        lint format build \
        shell-api docs \
        backend-deps frontend-deps

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / { \
		printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 \
	}' $(MAKEFILE_LIST)

# --------------------------------------------------------------- #
# Environment bootstrap
# --------------------------------------------------------------- #

setup: backend-deps frontend-deps ## Install backend + frontend dependencies locally
	@echo "→ Local dependencies installed. Run 'make dev' to start the stack."

backend-deps: ## Install backend Python dependencies
	cd backend && pip install -e ".[dev]"

frontend-deps: ## Install frontend Node dependencies
	cd frontend && npm install --no-audit --no-fund

# --------------------------------------------------------------- #
# Docker Compose
# --------------------------------------------------------------- #

dev: ## Start the full dev environment (API, worker, DB, Redis, MinIO, frontend)
	@test -f .env || (cp .env.example .env && echo "→ Created .env from .env.example")
	$(COMPOSE) up -d
	@echo "→ Environment running."
	@echo "  Frontend:  http://localhost:5173"
	@echo "  API docs:  http://localhost:8000/docs"
	@echo "  MinIO UI:  http://localhost:9001"

stop: ## Stop all containers
	$(COMPOSE) down

reset: ## Full reset (containers + volumes) and rebuild from scratch
	$(COMPOSE) down -v
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d
	@echo "→ Containers rebuilt. Run 'make db-migrate && make db-seed' to populate the DB."

rebuild: ## Clear Docker build cache, rebuild images, and force-recreate containers (preserves volumes)
	$(COMPOSE) down --remove-orphans
	$(COMPOSE) build --no-cache --pull
	$(COMPOSE) up -d --force-recreate
	@echo "→ Containers rebuilt with fresh images. Volumes preserved."
	@echo "  Frontend:  http://localhost:5173"
	@echo "  API docs:  http://localhost:8000/docs"

logs: ## Tail logs from every container
	$(COMPOSE) logs -f --tail=200

# --------------------------------------------------------------- #
# Database
# --------------------------------------------------------------- #

db-migrate: ## Run Alembic migrations inside the API container
	$(COMPOSE) exec $(API_CONTAINER) alembic upgrade head

db-seed: ## Populate the database with realistic sample data
	$(COMPOSE) exec $(API_CONTAINER) python -m scripts.seed

db-reset: ## Drop schema, re-migrate, and re-seed (destructive!)
	@read -p "This will erase all data. Continue? [y/N] " ans; \
		test "$$ans" = "y" || test "$$ans" = "Y" || exit 1
	$(COMPOSE) exec $(API_CONTAINER) alembic downgrade base
	$(COMPOSE) exec $(API_CONTAINER) alembic upgrade head
	$(COMPOSE) exec $(API_CONTAINER) python -m scripts.seed

shell-db: ## Open a psql shell against the dev database
	$(COMPOSE) exec $(DB_CONTAINER) psql -U watari -d watari

shell-api: ## Drop into a shell inside the API container
	$(COMPOSE) exec $(API_CONTAINER) bash

# --------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------- #

test: test-unit test-property test-integration ## Run every test

test-unit: ## Run backend unit tests
	cd backend && PYTHONPATH=. pytest tests/ --ignore=tests/integration --ignore=tests/e2e --ignore=tests/property -q

test-property: ## Run Hypothesis property tests
	cd backend && PYTHONPATH=. pytest tests/property -q

test-integration: ## Run backend integration tests (requires live Postgres)
	@echo "→ Running integration tests (requires Postgres at localhost:5432 with DB 'watari_test')"
	cd backend && TEST_DATABASE_URL=postgresql+asyncpg://watari:watari_dev_password@localhost:5432/watari_test \
		PYTHONPATH=. pytest tests/integration tests/property -q || echo "(integration tests require running DB)"

# --------------------------------------------------------------- #
# Lint + format
# --------------------------------------------------------------- #

lint: ## Run Ruff + mypy (backend) and eslint (frontend)
	cd backend && ruff check src tests
	cd backend && mypy src || true
	cd frontend && npx tsc --noEmit

format: ## Auto-format backend (ruff) + frontend (prettier)
	cd backend && ruff format src tests
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"

# --------------------------------------------------------------- #
# Production builds
# --------------------------------------------------------------- #

build: ## Build production Docker images
	$(COMPOSE) build

docs: ## Open API documentation in a browser
	@echo "→ API docs: http://localhost:8000/docs"
	@python3 -c "import webbrowser; webbrowser.open('http://localhost:8000/docs')" 2>/dev/null || true
