.PHONY: setup venv migrate migrate-sync seed api web worker beat test lint typecheck fmt up down psql redis-cli clean

PY := .venv/bin/python
PIP := .venv/bin/pip
UVICORN := .venv/bin/uvicorn
CELERY := .venv/bin/celery
ALEMBIC := .venv/bin/alembic
PYTEST := .venv/bin/pytest

# ─── one-time setup ──────────────────────────────────────────────────────────
setup: venv
	$(PIP) install -U pip wheel
	$(PIP) install -e "packages/shared[dev]" -e "apps/api[dev]" -e "apps/workers[dev]"
	@command -v psql >/dev/null && psql -d postgres -c "CREATE DATABASE prachar;" 2>/dev/null || true
	@command -v psql >/dev/null && psql -d postgres -c "CREATE USER prachar WITH PASSWORD 'prachar' SUPERUSER;" 2>/dev/null || true
	@command -v psql >/dev/null && psql -d prachar -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" || true
	@command -v psql >/dev/null && psql -d prachar -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" || true
	cd apps/web && pnpm install
	cp -n .env.example .env || true
	@echo "✅ setup done — edit .env, then: make migrate && make seed"

venv:
	[ -d .venv ] || python3 -m venv .venv

# ─── db ──────────────────────────────────────────────────────────────────────
migrate:
	$(ALEMBIC) -c apps/api/alembic.ini upgrade head

migrate-sync:
	DATABASE_URL=$$(grep ^DATABASE_URL_SYNC .env | cut -d= -f2-) $(ALEMBIC) -c apps/api/alembic.ini upgrade head

migrate-new:
	@read -p "message: " msg; $(ALEMBIC) -c apps/api/alembic.ini revision --autogenerate -m "$$msg"

seed:
	$(PY) scripts/seed.py

# ─── run ─────────────────────────────────────────────────────────────────────
api:
	$(UVICORN) apps.api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd apps/web && pnpm dev

worker:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=4

beat:
	$(CELERY) -A apps.workers.celery_app beat -l info

# ─── quality ─────────────────────────────────────────────────────────────────
test:
	$(PYTEST) -q
	cd apps/web && pnpm typecheck && pnpm test

lint:
	$(PY) -m ruff check apps packages
	cd apps/web && pnpm lint

typecheck:
	$(PY) -m mypy apps packages
	cd apps/web && pnpm typecheck

fmt:
	$(PY) -m ruff format apps packages

# ─── docker ──────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

# ─── helpers ─────────────────────────────────────────────────────────────────
psql:
	psql -d prachar

redis-cli:
	redis-cli

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache apps/web/.next apps/web/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
