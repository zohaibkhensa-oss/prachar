"""Integration tests for cross-tenant dispatch discovery.

``due_brands_for_dispatch`` is a SECURITY DEFINER function that returns only
due (tenant_id, brand_id) identifiers. These tests prove:

1. The dispatcher discovers due brands across MULTIPLE tenants.
2. Not-due brands are excluded.
3. The same query as a direct table read stays RLS-blocked — the function
   does not widen the worker role's privileges.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_api import db as dbmod  # noqa: E402
from prachar_api.main import app  # noqa: E402


@pytest.fixture
async def client():
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


async def _create_brand(c: AsyncClient, headers: dict) -> str:
    res = await c.post("/brands", json={
        "name": f"B{uuid.uuid4().hex[:6]}", "website": "https://example.com", "category": "tech",
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _defer_brand(brand_id: str, tenant_id: str) -> None:
    """Push next_loop_at into the future (under the owning tenant context)."""
    engine = dbmod.get_engine()
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id}
        )
        res = await conn.execute(
            text("UPDATE brands SET next_loop_at = now() + interval '7 days' WHERE id = :bid"),
            {"bid": brand_id},
        )
        assert res.rowcount == 1
        await conn.commit()


@pytest.mark.asyncio
async def test_dispatch_due_finds_due_brands_across_tenants(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    # Two tenants, each with a brand. New brands have next_loop_at NULL → due.
    t1 = await _register(client, f"t1{uuid.uuid4().hex[:8]}@test.com", "Tenant A")
    h1 = {"Authorization": f"Bearer {t1['access_token']}"}
    brand_a = await _create_brand(client, h1)

    t2 = await _register(client, f"t2{uuid.uuid4().hex[:8]}@test.com", "Tenant B")
    h2 = {"Authorization": f"Bearer {t2['access_token']}"}
    brand_b = await _create_brand(client, h2)

    # A third brand, not due (next_loop_at pushed out a week)
    brand_c = await _create_brand(client, h2)
    await _defer_brand(brand_c, t2["user"]["tenant_id"])

    from prachar_workers import loop as worker_loop

    sent: list[str] = []
    monkeypatch.setattr(
        worker_loop.enqueue_weekly_loop,
        "apply_async",
        MagicMock(side_effect=lambda *a, **kw: sent.append(kw["args"][0] if "args" in kw else a[0][0])),
    )

    result = worker_loop.dispatch_due()

    assert brand_a in result["enqueued"], f"tenant A due brand missing: {result}"
    assert brand_b in result["enqueued"], f"tenant B due brand missing: {result}"
    assert brand_c not in result["enqueued"], "not-due brand was dispatched"
    assert len(sent) == result["count"]


@pytest.mark.asyncio
async def test_dispatch_rls_boundary_holds(client: AsyncClient):
    """Direct brand reads stay RLS-blocked; only the function crosses tenants."""
    t = await _register(client, f"r{uuid.uuid4().hex[:8]}@test.com", "Tenant RLS")
    brand_id = await _create_brand(client, {"Authorization": f"Bearer {t['access_token']}"})
    tenant_id = t["user"]["tenant_id"]

    engine = dbmod.get_engine()

    # No tenant context → brands invisible (RLS deny-all by default)
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM brands"))).all()
        assert rows == [], "RLS leak: brands visible without tenant context"
        await conn.rollback()

    # With tenant A set → only A's brand visible
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id}
        )
        rows = (await conn.execute(text("SELECT id FROM brands"))).all()
        assert [str(r[0]) for r in rows] == [brand_id]
        await conn.rollback()

    # The privileged function still returns the due pair for dispatch
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT tenant_id, brand_id FROM due_brands_for_dispatch(now())")
            )
        ).all()
        pairs = {(str(r[0]), str(r[1])) for r in rows}
        assert (tenant_id, brand_id) in pairs
        await conn.rollback()
