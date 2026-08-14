# Watari — developer workflow Makefile
#
# Usage: `make help` to list available targets.
#
# Most targets assume Docker Compose is available. `make test-quick` and
# `make lint-backend` run standalone against a local Python environment;
# `make test` needs the dev stack up (`make dev`) because the DB-backed
# suites talk to the real PostgreSQL, and the frontend linters run inside
# the container that actually has node_modules.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c

COMPOSE ?= docker compose
API_CONTAINER := api
WORKER_CONTAINER := worker
DB_CONTAINER := postgres
FRONTEND_CONTAINER := frontend

.PHONY: help setup dev stop reset rebuild logs \
        db-migrate db-seed db-reset shell-db \
        test test-quick test-db \
        lint lint-backend lint-frontend format build \
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

# The owner role runs the migrations; the unprivileged role is what the tests
# query with, so they are subject to the same RLS the API is.
TEST_DB_URL  := postgresql+asyncpg://watari:watari_dev_password@localhost:5432/watari_test
TEST_APP_URL := postgresql+asyncpg://watari_app:watari_app_dev_password@localhost:5432/watari_test
# The default S3 endpoint resolves inside the Compose network, not from the host.
TEST_ENV := TEST_DATABASE_URL=$(TEST_DB_URL) \
            TEST_APP_DATABASE_URL=$(TEST_APP_URL) \
            S3_ENDPOINT_URL=http://localhost:9000

test: test-db ## Run every test (needs the dev stack: make dev)
	cd backend && $(TEST_ENV) PYTHONPATH=. pytest tests/ -q

test-quick: ## Run only the tests that need no database (fast inner loop)
	cd backend && PYTHONPATH=. pytest tests/property -q

test-db: ## Create the dedicated test database if it is missing
	@$(COMPOSE) exec -T $(DB_CONTAINER) psql -U watari -d postgres -tAc \
		"SELECT 1 FROM pg_database WHERE datname='watari_test'" | grep -q 1 \
		|| $(COMPOSE) exec -T $(DB_CONTAINER) createdb -U watari watari_test

# --------------------------------------------------------------- #
# Lint + format
# --------------------------------------------------------------- #

lint: lint-backend lint-frontend ## Run every linter

lint-backend: ## Ruff (blocking) + mypy (advisory) against the backend
	cd backend && ruff check src tests
	@# mypy is not clean yet (108 findings); reported, not blocking.
	@cd backend && mypy src || true

lint-frontend: ## tsc + eslint, inside the container that has node_modules
	@$(COMPOSE) ps --status running --services 2>/dev/null | grep -qx $(FRONTEND_CONTAINER) || { \
		echo "  The frontend container is not running. Start it with: make dev"; exit 1; }
	$(COMPOSE) exec -T $(FRONTEND_CONTAINER) npx tsc --noEmit
	$(COMPOSE) exec -T $(FRONTEND_CONTAINER) npm run lint

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
