"""Tests for inline field editing on campaigns (P3.4).

Verifies:
- PATCH /review/{id}/field updates the field correctly
- 400 for non-whitelisted field
- 404 for non-existent campaign
- Auth required (401 without token)
- Audit event is written for each edit

These tests hit the real DB (no mocking) following the s0_acceptance pattern.
"""
from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

# Ensure env is loaded before settings is cached.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-secret-refresh-xxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.config import get_settings  # noqa: E402

get_settings.cache_clear()

from prachar_api.db import get_sessionmaker  # noqa: E402
from prachar_api.main import app  # noqa: E402


@pytest.fixture
async def client():
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
    res = await c.post(
        "/auth/register",
        json={"email": email, "password": "testpass123", "tenant_name": tenant_name},
    )
    assert res.status_code == 201, res.text
    return res.json()


async def _create_brand(c: AsyncClient, headers: dict) -> str:
    res = await c.post(
        "/brands",
        json={"name": "Edit Brand", "website": "https://example.com", "category": "tech"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _create_campaign(c: AsyncClient, headers: dict, brand_id: str) -> dict:
    res = await c.post(
        "/campaigns",
        json={
            "brand_id": brand_id,
            "network": "google_ads",
            "objective": "traffic",
            "audience_spec": {"geo": ["IN"]},
            "budget_daily": 100.0,
            "currency": "INR",
            "dry_run": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


# ─── auth required ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_field_requires_auth(client: AsyncClient):
    res = await client.patch(
        f"/review/{uuid.uuid4()}/field",
        json={"field": "budget_daily", "value": "200"},
    )
    assert res.status_code == 401


# ─── successful edits ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_field_updates_budget(client: AsyncClient):
    tok = await _register(client, f"ed{uuid.uuid4().hex[:8]}@test.com", "Edit Budget Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "250.5"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["budget_daily"] == 250.5


@pytest.mark.asyncio
async def test_edit_field_updates_objective(client: AsyncClient):
    tok = await _register(client, f"eo{uuid.uuid4().hex[:8]}@test.com", "Edit Obj Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "objective", "value": "conversions"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["objective"] == "conversions"


@pytest.mark.asyncio
async def test_edit_field_updates_currency(client: AsyncClient):
    tok = await _register(client, f"ec{uuid.uuid4().hex[:8]}@test.com", "Edit Currency Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "currency", "value": "USD"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["currency"] == "USD"


@pytest.mark.asyncio
async def test_edit_field_updates_guardrails_json(client: AsyncClient):
    tok = await _register(client, f"eg{uuid.uuid4().hex[:8]}@test.com", "Edit Guard Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "guardrails", "value": '{"max_cpa": 50, "no_clickbait": true}'},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["guardrails"] == {"max_cpa": 50, "no_clickbait": True}


# ─── 400 for non-whitelisted field ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_field_400_for_non_whitelisted(client: AsyncClient):
    tok = await _register(client, f"nw{uuid.uuid4().hex[:8]}@test.com", "NonWL Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "id", "value": str(uuid.uuid4())},
        headers=headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_edit_field_400_for_tenant_id(client: AsyncClient):
    tok = await _register(client, f"tid{uuid.uuid4().hex[:8]}@test.com", "TID Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "tenant_id", "value": str(uuid.uuid4())},
        headers=headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_edit_field_400_for_invalid_json(client: AsyncClient):
    tok = await _register(client, f"ij{uuid.uuid4().hex[:8]}@test.com", "Invalid JSON Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "guardrails", "value": "not-valid-json{"},
        headers=headers,
    )
    assert res.status_code == 400


# ─── 404 for non-existent campaign ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_field_404_nonexistent(client: AsyncClient):
    tok = await _register(client, f"e404{uuid.uuid4().hex[:8]}@test.com", "Edit 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    res = await client.patch(
        f"/review/{uuid.uuid4()}/field",
        json={"field": "budget_daily", "value": "200"},
        headers=headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_edit_field_404_other_tenant(client: AsyncClient):
    tok_a = await _register(client, f"eta{uuid.uuid4().hex[:8]}@test.com", "Edit Tenant A")
    tok_b = await _register(client, f"etb{uuid.uuid4().hex[:8]}@test.com", "Edit Tenant B")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}
    brand_id = await _create_brand(client, headers_a)
    camp = await _create_campaign(client, headers_a, brand_id)

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "200"},
        headers=headers_b,
    )
    assert res.status_code == 404


# ─── audit event written ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_field_writes_audit_event(client: AsyncClient):
    tok = await _register(client, f"aud{uuid.uuid4().hex[:8]}@test.com", "Audit Edit Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)
    tenant_id = tok["user"]["tenant_id"]

    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "300"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # Query audit_events directly with RLS context set.
    sm = get_sessionmaker()
    async with sm() as session:
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id}
        )
        res2 = await session.execute(
            text(
                "SELECT action, payload FROM audit_events "
                "WHERE action = 'campaign.edit_field' AND entity_id = :eid "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"eid": camp["id"]},
        )
        row = res2.fetchone()
        assert row is not None, "audit_events row for campaign.edit_field missing"
        assert row[0] == "campaign.edit_field"
        payload = row[1]
        assert payload["field"] == "budget_daily"
        assert payload["old_value"] == 100.0
        assert payload["new_value"] == 300.0
