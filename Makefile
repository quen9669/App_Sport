# Single entry point for every common task. Run `make` or `make help` to list them.
# Works on Linux and on Windows through WSL2 (run it from the Ubuntu terminal).

# Each recipe runs in one shell, and stops at the first failing command.
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

BACKEND := backend
FRONTEND := frontend

.PHONY: help install dev dev-backend dev-frontend test test-backend test-frontend \
	test-e2e e2e-install lint format typecheck check clean db-upgrade db-revision seed seed-clear

help: ## Show this list of commands
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install backend and frontend dependencies
	cd $(BACKEND) && uv sync
	cd $(FRONTEND) && npm ci
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")
	@# Fill in a random encryption key for stored tokens if none is set yet.
	@if grep -q '^TOKEN_ENCRYPTION_KEY=$$' .env; then \
		key=$$(cd $(BACKEND) && uv run --quiet python -c "from app.services.crypto import generate_key; print(generate_key())"); \
		sed -i "s|^TOKEN_ENCRYPTION_KEY=$$|TOKEN_ENCRYPTION_KEY=$$key|" .env; \
		echo "Generated TOKEN_ENCRYPTION_KEY in .env"; \
	fi

dev: ## Start backend (port 8000) and frontend (port 5173) together; Ctrl+C stops both
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend: db-upgrade ## Start only the backend, with auto-reload on code changes
	cd $(BACKEND) && uv run uvicorn app.main:app --reload --port 8000

db-upgrade: ## Apply database migrations (creates the SQLite file if needed)
	cd $(BACKEND) && uv run alembic upgrade head

seed: db-upgrade ## Fill the database with a year of realistic synthetic data
	cd $(BACKEND) && uv run python -m scripts.seed

seed-clear: ## Remove the synthetic data (real data is never touched)
	cd $(BACKEND) && uv run python -m scripts.seed --clear

db-revision: ## Create a migration from model changes: make db-revision m="add goal table"
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

dev-frontend: ## Start only the frontend dev server
	cd $(FRONTEND) && npm run dev -- --port 5173

test: test-backend test-frontend ## Run all unit tests

test-backend: ## Run backend tests (pytest)
	cd $(BACKEND) && uv run pytest

test-frontend: ## Run frontend unit tests (Vitest)
	cd $(FRONTEND) && npm test

e2e-install: ## Download the Chromium browser used by end-to-end tests (once)
	cd $(FRONTEND) && npx playwright install --with-deps chromium

test-e2e: ## Run the Playwright end-to-end test (starts backend and frontend itself)
	cd $(FRONTEND) && npm run test:e2e

lint: ## Check code style and common mistakes
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(FRONTEND) && npm run lint && npm run format:check

format: ## Automatically format all code
	cd $(BACKEND) && uv run ruff check --fix . && uv run ruff format .
	cd $(FRONTEND) && npm run format

typecheck: ## Check types (mypy for Python, tsc for TypeScript)
	cd $(BACKEND) && uv run mypy app tests scripts
	cd $(FRONTEND) && npm run typecheck

check: lint typecheck test ## Everything CI checks: lint, types and tests

clean: ## Remove caches and build outputs
	rm -rf $(BACKEND)/.pytest_cache $(BACKEND)/.mypy_cache $(BACKEND)/.ruff_cache
	rm -rf $(FRONTEND)/dist $(FRONTEND)/dev-dist $(FRONTEND)/playwright-report $(FRONTEND)/test-results
