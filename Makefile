.PHONY: setup venv migrate migrate-sync seed api web web-v2 worker beat test lint typecheck fmt up down psql redis-cli clean \
        worker-dispatch worker-loop-0 worker-loop-1 worker-loop-2 worker-loop-3 worker-loop-4 worker-loop-5 worker-loop-6 worker-loop-7 \
        worker-ingest worker-organic worker-ads worker-measure worker-creative

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
	$(UVICORN) apps.api.prachar_api.main:app --reload --host 0.0.0.0 --port 8000

web:
	cd apps/web && pnpm dev

# v2 frontend (AI-first layout, port 3002)
web-v2:
	cd apps/web-v2 && pnpm dev

# Single worker consuming all queues (local dev)
worker:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=4 \
		-Q prachar,dispatch,ingest,organic,ads,measure,creative,loop-0,loop-1,loop-2,loop-3,loop-4,loop-5,loop-6,loop-7

beat:
	$(CELERY) -A apps.workers.celery_app beat -l info

# ─── Scaled workers (production — run each in a separate terminal/process) ───
# At 10K users, run 8 loop shards + 1 each of ingest/organic/ads/measure/creative.
# Each can be horizontally scaled by running multiple instances.
worker-dispatch:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=1 -Q dispatch

worker-loop-0:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-0
worker-loop-1:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-1
worker-loop-2:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-2
worker-loop-3:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-3
worker-loop-4:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-4
worker-loop-5:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-5
worker-loop-6:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-6
worker-loop-7:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_LOOP:-4} -Q loop-7

worker-ingest:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_INGEST:-2} -Q ingest
worker-organic:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_ORGANIC:-4} -Q organic
worker-ads:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_ADS:-2} -Q ads
worker-measure:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_MEASURE:-2} -Q measure
worker-creative:
	$(CELERY) -A apps.workers.celery_app worker -l info --concurrency=${CELERY_CONCURRENCY_CREATIVE:-2} -Q creative

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
