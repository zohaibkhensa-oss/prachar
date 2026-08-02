# PRACHAR AI — Developer Documentation

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Local Development Setup](#local-development-setup)
3. [Adding a New Tool](#adding-a-new-tool)
4. [Adding a New Context Provider](#adding-a-new-context-provider)
5. [Adding a New Integration Adapter](#adding-a-new-integration-adapter)
6. [Adding a New Domain Pack](#adding-a-new-domain-pack)
7. [Database Migrations](#database-migrations)
8. [Testing](#testing)
9. [Extension Checklist](#extension-checklist)

---

## Architecture Overview

PRACHAR AI is a monorepo with 4 packages:

```
apps/api/         FastAPI backend (routers, runtime, models, tests)
apps/web/         Next.js 15 frontend (App Router, TypeScript)
apps/workers/     Celery workers (ingest, organic, ads, measure, creative)
packages/shared/  Shared library (ai_gateway, adapters, contracts, policy)
infra/            Terraform (AWS infrastructure)
docs/             Documentation (ADR, dev guides)
```

### Core Systems (frozen — see ADR-0007)

| System | Location | ADR |
|--------|----------|-----|
| Runtime | `apps/api/prachar_api/runtime/` | ADR-0001 |
| Tool Registry | `apps/api/prachar_api/runtime/registry.py` | ADR-0002 |
| Context Builder | `apps/api/prachar_api/runtime/context_builder.py` | ADR-0003 |
| Knowledge Hub | `packages/shared/prachar_shared/knowledge_hub/` | ADR-0004 |
| Integration Framework | `packages/shared/prachar_shared/adapters/` | ADR-0005 |
| Workflow Engine | `apps/api/prachar_api/runtime/automation.py` | ADR-0006 |

### The Orb (AI Runtime)

The Orb is a 7-stage pipeline:

1. **Session creation** — `SessionManager`
2. **Context assembly** — `ContextBuilder` (16 providers)
3. **Intent classification** — LLM classifies the message
4. **Planning** — `Planner` produces an `ExecutionGraph`
5. **Decision contract** — `DecisionContract` captures goal + reasoning
6. **Timeline append** — Immutable record
7. **Execution** — `Executor` runs tools (30 tools) with retries

Entry point: `POST /runtime/invoke`

---

## Local Development Setup

### Prerequisites

- Python 3.12+ (3.14 ok locally)
- Node.js 20+ with pnpm 9
- PostgreSQL 16
- Redis 7

### Setup

```bash
# Clone the repo
git clone <repo-url> && cd prachar

# Create virtual environment and install deps
make setup

# Copy env file and fill in secrets
cp .env.example .env
# Edit .env with your DATABASE_URL, REDIS_URL, JWT_SECRET, etc.

# Run database migrations
make migrate

# Seed demo data
make seed

# Start the API
make api    # uvicorn on :8000

# Start the frontend (separate terminal)
make web    # next.js on :3000

# Start workers (separate terminal)
make worker # celery worker
make beat   # celery beat scheduler
```

### Verify

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs

# Run tests
make test
```

---

## Adding a New Tool

Tools are the Orb's actions. Every AI capability is a tool.

### 1. Define the tool

```python
# apps/api/prachar_api/runtime/tools.py
from .registry import Tool, ToolCategory

async def my_new_tool(session, tenant_id: str, brand_id: str, **kwargs):
    """Does something useful."""
    # Your logic here
    return {"result": "..."}

# Register it
registry.register(Tool(
    name="my_feature.action",
    category=ToolCategory.ANALYTICS,
    description="Does something useful for the user",
    input_schema={"param1": {"type": "str", "required": True}},
    output_schema={"result": {"type": "str"}},
    cost_estimate={"latency_ms": 500, "tokens": 0, "quality": 0.8},
    handler=my_new_tool,
))
```

### 2. Add tests

```python
# apps/api/prachar_api/tests/test_my_tool.py
import pytest

@pytest.mark.asyncio
async def test_my_tool_returns_result():
    result = await my_new_tool(session, tenant_id, brand_id, param1="test")
    assert "result" in result
```

### 3. The planner will automatically discover the tool

No changes to the planner or runtime needed.

---

## Adding a New Context Provider

Context providers feed relevant data to the Orb.

### 1. Define the provider

```python
# apps/api/prachar_api/runtime/context_builder.py
class MyContextProvider(ContextProvider):
    name = "my_feature"
    keywords = ["my_feature", "specific_term"]

    def is_relevant(self, message: str, intent: str) -> bool:
        return any(kw in message.lower() for kw in self.keywords)

    async def load(self, session, tenant_id, brand_id, message) -> dict:
        # Query your data
        return {"my_feature_data": [...]}
```

### 2. Register it

```python
# In the ContextBuilder constructor
self.providers.append(MyContextProvider())
```

### 3. Add tests

```python
def test_my_provider_is_relevant():
    p = MyContextProvider()
    assert p.is_relevant("show me my feature data", "query")
    assert not p.is_relevant("unrelated message", "query")
```

---

## Adding a New Integration Adapter

Adapters connect to external platforms.

### 1. Implement the adapter interface

```python
# packages/shared/prachar_shared/adapters/organic/my_platform.py
from .base import ChannelAdapter

class MyPlatformAdapter(ChannelAdapter):
    platform = "my_platform"

    async def publish(self, content: dict) -> dict:
        # POST to platform API
        ...

    async def get_insights(self, since: datetime) -> dict:
        # GET analytics
        ...
```

### 2. Register it

```python
# packages/shared/prachar_shared/adapters/organic/__init__.py
from .my_platform import MyPlatformAdapter
```

### 3. Add OAuth flow (if needed)

Add OAuth client credentials to `.env`:
```
MY_PLATFORM_CLIENT_ID=...
MY_PLATFORM_CLIENT_SECRET=...
```

### 4. Add tests

```python
# packages/shared/prachar_shared/tests/test_my_platform_adapter.py
@pytest.mark.asyncio
async def test_my_platform_publish():
    adapter = MyPlatformAdapter()
    result = await adapter.publish({"text": "hello"})
    assert "id" in result
```

---

## Adding a New Domain Pack

Domain packs configure the platform for specific industries.

### 1. Create the pack

```python
# packages/shared/prachar_shared/domain_packs/my_industry/
# ├── __init__.py
# └── pack.py

from ..base import DomainPack, SubtypePreset, KpiCardSpec, ...

class MyIndustryPack(DomainPack):
    name = "my_industry"
    display_name = "My Industry"

    def discovery_prompts(self) -> str:
        return "Tell me about your business..."

    def kpis(self) -> list[KpiCardSpec]:
        return [
            KpiCardSpec(label="Revenue", key="revenue", ...),
        ]

    # ... implement all required methods
```

### 2. Register it

```python
# packages/shared/prachar_shared/domain_packs/__init__.py
from .my_industry.pack import MyIndustryPack
register_pack(MyIndustryPack())
```

### 3. Add tests

```python
# packages/shared/prachar_shared/domain_packs/tests/test_my_industry.py
def test_my_industry_pack_has_required_attributes():
    pack = MyIndustryPack()
    assert pack.name
    assert pack.display_name
    assert pack.kpis()
```

---

## Database Migrations

Migrations are additive-only (ADR-0007). No destructive changes without approval.

### Create a migration

```bash
# Auto-generate from model changes
alembic -c apps/api/alembic.ini revision --autogenerate -m "add_my_table"

# Or create manually
alembic -c apps/api/alembic.ini revision -m "add_my_table"
```

### Apply migrations

```bash
alembic -c apps/api/alembic.ini upgrade head
```

### Rollback

```bash
alembic -c apps/api/alembic.ini downgrade -1
```

### Rules

- **Additive only**: new tables, new columns (nullable or with default)
- **No destructive changes**: no DROP TABLE, no DROP COLUMN without approval
- **Always test rollback**: `downgrade -1` must work
- **RLS on every tenant table**: add `tenant_id` column + RLS policy

---

## Testing

### Run all tests

```bash
make test    # pytest + pnpm typecheck + playwright smoke
```

### Run specific test suites

```bash
# Backend
pytest apps/api/prachar_api/tests/ -v

# Shared
pytest packages/shared/prachar_shared/tests/ -v

# Workers
pytest apps/workers/prachar_workers/tests/ -v

# Architecture freeze guards
pytest apps/api/prachar_api/tests/test_architecture_freeze.py -v

# Frontend
cd apps/web && pnpm typecheck
```

### Test count

- 774 backend tests
- 48 architecture invariant tests
- 7 architecture freeze guards
- 0 TypeScript errors

---

## Extension Checklist

Before starting any new feature, answer these questions. If every answer
points to an existing subsystem, the feature proceeds without architectural
review:

- [ ] Which existing subsystem does it extend?
- [ ] Which Tool Registry entry is added (if any)?
- [ ] Which Context Provider is added (if any)?
- [ ] Which Integration adapter is added (if any)?
- [ ] Which Workflow actions/events are added (if any)?
- [ ] Which database migration is additive?
- [ ] Which tests are added?

If a feature cannot fit into any existing subsystem, see ADR-0007 §v2 Admission Rule.
