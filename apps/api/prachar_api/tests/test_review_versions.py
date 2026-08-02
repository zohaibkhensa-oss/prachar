"""Tests for version history on campaigns (A.4.2).

Verifies:
- PATCH /review/{id}/field creates a ReviewVersion snapshot
- GET /review/{id}/versions lists versions newest-first with author email
- GET /review/{id}/versions/{n} returns a specific version snapshot
- POST /review/{id}/versions/{n}/restore restores editable fields + creates a new version
- 404 for non-existent campaign / version / other-tenant campaign
- Auth required (401 without token)

These tests hit the real DB (no mocking) following the s0_acceptance pattern.
"""
from __future__ import annotations

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
        json={"name": "Version Brand", "website": "https://example.com", "category": "tech"},
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
async def test_list_versions_requires_auth(client: AsyncClient):
    res = await client.get(f"/review/{uuid.uuid4()}/versions")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_version_requires_auth(client: AsyncClient):
    res = await client.get(f"/review/{uuid.uuid4()}/versions/1")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_restore_version_requires_auth(client: AsyncClient):
    res = await client.post(f"/review/{uuid.uuid4()}/versions/1/restore")
    assert res.status_code == 401


# ─── edit creates a version ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_creates_version_snapshot(client: AsyncClient):
    tok = await _register(client, f"v{uuid.uuid4().hex[:8]}@test.com", "Version Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # First edit → version 1
    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "200"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # Second edit → version 2
    res = await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "objective", "value": "conversions"},
        headers=headers,
    )
    assert res.status_code == 200, res.text

    # List versions — newest first.
    res = await client.get(f"/review/{camp['id']}/versions", headers=headers)
    assert res.status_code == 200, res.text
    versions = res.json()
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1
    # Author email is embedded.
    assert versions[0]["author"] is not None
    assert versions[0]["author"]["email"] == tok["user"]["email"]
    # change_summary records the field.
    assert versions[0]["change_summary"] == "Edited objective"
    assert versions[1]["change_summary"] == "Edited budget_daily"
    # Snapshot captures the campaign state at that version.
    assert versions[1]["snapshot"]["budget_daily"] == 200.0
    assert versions[1]["snapshot"]["objective"] == "traffic"
    assert versions[0]["snapshot"]["budget_daily"] == 200.0
    assert versions[0]["snapshot"]["objective"] == "conversions"


# ─── get specific version ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_specific_version(client: AsyncClient):
    tok = await _register(client, f"gv{uuid.uuid4().hex[:8]}@test.com", "Get Version Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "150"},
        headers=headers,
    )
    await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "300"},
        headers=headers,
    )

    res = await client.get(
        f"/review/{camp['id']}/versions/1", headers=headers
    )
    assert res.status_code == 200, res.text
    v1 = res.json()
    assert v1["version_number"] == 1
    assert v1["snapshot"]["budget_daily"] == 150.0
    assert v1["author"]["email"] == tok["user"]["email"]


@pytest.mark.asyncio
async def test_get_version_404_nonexistent(client: AsyncClient):
    tok = await _register(client, f"gv404{uuid.uuid4().hex[:8]}@test.com", "GV404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.get(
        f"/review/{camp['id']}/versions/999", headers=headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_versions_404_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"lv404{uuid.uuid4().hex[:8]}@test.com", "LV404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    res = await client.get(f"/review/{uuid.uuid4()}/versions", headers=headers)
    assert res.status_code == 404


# ─── restore ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_restore_version_restores_fields(client: AsyncClient):
    tok = await _register(client, f"rv{uuid.uuid4().hex[:8]}@test.com", "Restore Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # v1: budget 150
    await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "150"},
        headers=headers,
    )
    # v2: budget 300
    await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "300"},
        headers=headers,
    )
    assert (await _get_campaign(client, headers, camp["id"]))["budget_daily"] == 300.0

    # Restore v1 → budget back to 150, and a new version (v3) is created.
    res = await client.post(
        f"/review/{camp['id']}/versions/1/restore", headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["budget_daily"] == 150.0

    # Three versions now exist; v3 is the restore.
    res = await client.get(f"/review/{camp['id']}/versions", headers=headers)
    versions = res.json()
    assert len(versions) == 3
    assert versions[0]["version_number"] == 3
    assert versions[0]["change_summary"] == "Restored version 1"
    assert versions[0]["snapshot"]["budget_daily"] == 150.0


@pytest.mark.asyncio
async def test_restore_version_404_nonexistent_version(client: AsyncClient):
    tok = await _register(client, f"rv404{uuid.uuid4().hex[:8]}@test.com", "RV404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.post(
        f"/review/{camp['id']}/versions/999/restore", headers=headers
    )
    assert res.status_code == 404


# ─── tenant isolation ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_versions_tenant_isolation(client: AsyncClient):
    tok_a = await _register(client, f"vta{uuid.uuid4().hex[:8]}@test.com", "Version Tenant A")
    tok_b = await _register(client, f"vtb{uuid.uuid4().hex[:8]}@test.com", "Version Tenant B")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}
    brand_id = await _create_brand(client, headers_a)
    camp = await _create_campaign(client, headers_a, brand_id)

    await client.patch(
        f"/review/{camp['id']}/field",
        json={"field": "budget_daily", "value": "200"},
        headers=headers_a,
    )

    # Tenant B cannot list versions for tenant A's campaign (404).
    res = await client.get(f"/review/{camp['id']}/versions", headers=headers_b)
    assert res.status_code == 404

    # Tenant B cannot restore either.
    res = await client.post(
        f"/review/{camp['id']}/versions/1/restore", headers=headers_b
    )
    assert res.status_code == 404


# ─── helper ──────────────────────────────────────────────────────────────────


async def _get_campaign(c: AsyncClient, headers: dict, camp_id: str) -> dict:
    """Fetch a campaign from the review queue to read its current fields."""
    res = await c.get("/review/queue", headers=headers)
    assert res.status_code == 200
    for row in res.json():
        if row["id"] == camp_id:
            return row
    raise AssertionError(f"campaign {camp_id} not in queue")
