from __future__ import annotations

"""S0 acceptance tests: register→login→create brand; cross-tenant RLS isolation.

Run with: .venv/bin/pytest apps/api/prachar_api/tests/test_s0_acceptance.py -q

Requires: Postgres with migrated schema + Redis (or no redis for these tests).
These tests hit the real DB (no mocking) to verify RLS end-to-end.
"""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure env is loaded before settings is cached.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.config import get_settings  # noqa: E402

get_settings.cache_clear()

from prachar_api.db import get_engine, get_sessionmaker  # noqa: E402
from prachar_api.main import app  # noqa: E402
from prachar_api.models import Tenant, User  # noqa: E402
from prachar_api.security import hash_password  # noqa: E402

from sqlalchemy import select, text  # noqa: E402


@pytest.fixture
async def client():
    # Reset the global engine so each test gets a fresh connection pool
    # on the current event loop.
    import prachar_api.db as dbmod
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    if dbmod._engine is not None:
        await dbmod._engine.dispose()
        dbmod._engine = None
        dbmod._sessionmaker = None


async def _register(c: AsyncClient, email: str, tenant_name: str):
    res = await c.post("/auth/register", json={
        "email": email,
        "password": "testpass123",
        "tenant_name": tenant_name,
    })
    assert res.status_code == 201, res.text
    return res.json()


@pytest.mark.asyncio
async def test_register_login_create_brand(client: AsyncClient):
    # Register
    tok = await _register(client, f"u{uuid.uuid4().hex[:8]}@test.com", "Test Tenant")
    assert "access_token" in tok
    assert tok["user"]["email"].endswith("@test.com")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    # Login
    res = await client.post("/auth/login", json={
        "email": tok["user"]["email"], "password": "testpass123",
    })
    assert res.status_code == 200, res.text
    assert res.json()["access_token"]

    # Create brand
    res = await client.post("/brands", json={
        "name": "Test Brand", "website": "https://example.com", "category": "tech",
    }, headers=headers)
    assert res.status_code == 201, res.text
    brand = res.json()
    assert brand["name"] == "Test Brand"

    # List brands
    res = await client.get("/brands", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1

    # Get brand score
    res = await client.get(f"/brands/{brand['id']}/score", headers=headers)
    assert res.status_code == 200
    assert "overall" in res.json()


@pytest.mark.asyncio
async def test_cross_tenant_rls_isolation(client: AsyncClient):
    """Tenant A cannot read tenant B's brands — RLS must block it."""
    tok_a = await _register(client, f"a{uuid.uuid4().hex[:8]}@test.com", "Tenant A")
    tok_b = await _register(client, f"b{uuid.uuid4().hex[:8]}@test.com", "Tenant B")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}

    # Tenant A creates a brand
    res = await client.post("/brands", json={"name": "A's Brand"}, headers=headers_a)
    assert res.status_code == 201
    brand_a_id = res.json()["id"]

    # Tenant B lists brands — must NOT see A's brand
    res = await client.get("/brands", headers=headers_b)
    assert res.status_code == 200
    brand_ids = [b["id"] for b in res.json()]
    assert brand_a_id not in brand_ids, "RLS leak: tenant B sees tenant A's brand"

    # Tenant B tries to GET A's brand directly — must 404 (RLS hides it)
    res = await client.get(f"/brands/{brand_a_id}", headers=headers_b)
    assert res.status_code == 404, f"RLS leak: tenant B read tenant A's brand ({res.status_code})"


@pytest.mark.asyncio
async def test_audit_trail_on_brand_create(client: AsyncClient):
    """Every mutation writes an AuditEvent row."""
    tok = await _register(client, f"audit{uuid.uuid4().hex[:8]}@test.com", "Audit Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    res = await client.post("/brands", json={"name": "Audited Brand"}, headers=headers)
    assert res.status_code == 201
    tenant_id = tok["user"]["tenant_id"]

    # Query audit_events directly with RLS context set.
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id})
        res2 = await session.execute(
            text("SELECT action FROM audit_events WHERE action='brand.create' LIMIT 1")
        )
        row = res2.fetchone()
        assert row is not None, "audit_events row for brand.create missing"
        assert row[0] == "brand.create"
