"""Tests for the Creative Studio API router (P2.3).

Verifies:
- POST /creative-studio/generate returns 200 with a package containing 10 formats
- POST /creative-studio/generate/{format_id} returns 200 with a single format
- GET /creative-studio/{package_id} returns 404 (persistence not yet implemented)
- Auth required for all endpoints
- Invalid format_id returns 404

The CreativeStudioEngine is mocked so no real AI / DB lookups happen for the
generate endpoints. Auth uses the real DB (register → token) following the
test_review_router pattern.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

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
from prachar_api.routers.creative_studio import CreativeStudioEngine  # noqa: E402


# ─── Fixtures ───────────────────────────────────────────────────────────────


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


def _fake_package_dict() -> dict:
    """A fake CreativePackage.to_dict() with all 10 formats."""
    format_ids = [
        "poster", "video_script", "carousel", "story", "whatsapp",
        "facebook", "linkedin", "email", "landing_page", "sms",
    ]
    return {
        "id": str(uuid.uuid4()),
        "campaign_id": str(uuid.uuid4()),
        "creative_direction_id": str(uuid.uuid4()),
        "formats": {fid: {"headline": f"Fake {fid}", "cta": "Learn more"} for fid in format_ids},
        "generated_at": "2025-01-01T00:00:00+00:00",
        "total_tokens": 1234,
    }


def _fake_format_dict() -> dict:
    return {"headline": "Fake poster", "cta": "Buy now", "subheadline": "Limited offer"}


# ─── Auth required ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_requires_auth(client: AsyncClient):
    res = await client.post(
        "/creative-studio/generate",
        json={"campaign_id": str(uuid.uuid4()), "creative_direction_id": str(uuid.uuid4()), "domain": "tech"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_generate_one_requires_auth(client: AsyncClient):
    res = await client.post(
        "/creative-studio/generate/poster",
        json={"campaign_id": str(uuid.uuid4()), "creative_direction_id": str(uuid.uuid4()), "domain": "tech"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_package_requires_auth(client: AsyncClient):
    res = await client.get(f"/creative-studio/{uuid.uuid4()}")
    assert res.status_code == 401


# ─── POST /generate — all 10 formats ────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_returns_package_with_10_formats(client: AsyncClient):
    tok = await _register(client, f"cs{uuid.uuid4().hex[:8]}@test.com", "CS Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    fake = _fake_package_dict()

    with patch.object(
        CreativeStudioEngine,
        "generate_package",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        res = await client.post(
            "/creative-studio/generate",
            json={
                "campaign_id": str(uuid.uuid4()),
                "creative_direction_id": str(uuid.uuid4()),
                "domain": "tech",
            },
            headers=headers,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == fake["id"]
    assert "formats" in body
    assert len(body["formats"]) == 10
    expected = {"poster", "video_script", "carousel", "story", "whatsapp",
                "facebook", "linkedin", "email", "landing_page", "sms"}
    assert set(body["formats"].keys()) == expected


# ─── POST /generate/{format_id} — single format ─────────────────────────────


@pytest.mark.asyncio
async def test_generate_one_returns_single_format(client: AsyncClient):
    tok = await _register(client, f"cs1{uuid.uuid4().hex[:8]}@test.com", "CS One Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    fake = _fake_format_dict()

    with patch.object(
        CreativeStudioEngine,
        "generate_one",
        new_callable=AsyncMock,
        return_value=fake,
    ):
        res = await client.post(
            "/creative-studio/generate/poster",
            json={
                "campaign_id": str(uuid.uuid4()),
                "creative_direction_id": str(uuid.uuid4()),
                "domain": "tech",
            },
            headers=headers,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["headline"] == "Fake poster"
    assert body["cta"] == "Buy now"


@pytest.mark.asyncio
async def test_generate_one_invalid_format_returns_404(client: AsyncClient):
    tok = await _register(client, f"csi{uuid.uuid4().hex[:8]}@test.com", "CS Invalid Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    def _raise_keyerror(self, *a, **kw):
        raise KeyError("unknown format")

    with patch.object(
        CreativeStudioEngine,
        "generate_one",
        _raise_keyerror,
    ):
        res = await client.post(
            "/creative-studio/generate/nonexistent_format",
            json={
                "campaign_id": str(uuid.uuid4()),
                "creative_direction_id": str(uuid.uuid4()),
                "domain": "tech",
            },
            headers=headers,
        )

    assert res.status_code == 404
    assert "unknown" in res.json()["detail"].lower()


# ─── GET /{package_id} — persistence stub ───────────────────────────────────


@pytest.mark.asyncio
async def test_get_package_returns_404_persistence_not_implemented(client: AsyncClient):
    tok = await _register(client, f"csp{uuid.uuid4().hex[:8]}@test.com", "CS Persist Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    res = await client.get(f"/creative-studio/{uuid.uuid4()}", headers=headers)
    assert res.status_code == 404
    assert "future" in res.json()["detail"].lower() or "persistence" in res.json()["detail"].lower()


# ─── POST /regenerate-field — granular field regeneration ───────────────────


@pytest.mark.asyncio
async def test_regenerate_field_requires_auth(client: AsyncClient):
    res = await client.post(
        "/creative-studio/regenerate-field",
        json={
            "campaign_id": str(uuid.uuid4()),
            "creative_direction_id": str(uuid.uuid4()),
            "domain": "tech",
            "format_id": "poster",
            "field_name": "headline",
            "current_content": {"headline": "Old headline"},
        },
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_regenerate_field_returns_new_value(client: AsyncClient):
    tok = await _register(client, f"csrf{uuid.uuid4().hex[:8]}@test.com", "CS RegenField Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    fake_result = {"field_name": "headline", "new_value": "Amazing new headline!"}

    with patch.object(
        CreativeStudioEngine,
        "regenerate_field",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        res = await client.post(
            "/creative-studio/regenerate-field",
            json={
                "campaign_id": str(uuid.uuid4()),
                "creative_direction_id": str(uuid.uuid4()),
                "domain": "tech",
                "format_id": "poster",
                "field_name": "headline",
                "current_content": {"headline": "Old headline", "cta": "Buy now"},
            },
            headers=headers,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["field_name"] == "headline"
    assert body["new_value"] == "Amazing new headline!"


@pytest.mark.asyncio
async def test_regenerate_field_invalid_format_returns_404(client: AsyncClient):
    tok = await _register(client, f"csrfi{uuid.uuid4().hex[:8]}@test.com", "CS RegenField Invalid Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    def _raise_keyerror(self, *a, **kw):
        raise KeyError("unknown format")

    with patch.object(
        CreativeStudioEngine,
        "regenerate_field",
        _raise_keyerror,
    ):
        res = await client.post(
            "/creative-studio/regenerate-field",
            json={
                "campaign_id": str(uuid.uuid4()),
                "creative_direction_id": str(uuid.uuid4()),
                "domain": "tech",
                "format_id": "nonexistent_format",
                "field_name": "headline",
                "current_content": {},
            },
            headers=headers,
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_regenerate_field_list_value(client: AsyncClient):
    """Regenerate a list field (e.g. color_palette) returns a list new_value."""
    tok = await _register(client, f"csrfl{uuid.uuid4().hex[:8]}@test.com", "CS RegenField List Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    fake_result = {"field_name": "color_palette", "new_value": ["#FF0000", "#00FF00", "#0000FF"]}

    with patch.object(
        CreativeStudioEngine,
        "regenerate_field",
        new_callable=AsyncMock,
        return_value=fake_result,
    ):
        res = await client.post(
            "/creative-studio/regenerate-field",
            json={
                "campaign_id": str(uuid.uuid4()),
                "creative_direction_id": str(uuid.uuid4()),
                "domain": "tech",
                "format_id": "poster",
                "field_name": "color_palette",
                "current_content": {"color_palette": ["#111111", "#222222"]},
            },
            headers=headers,
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["field_name"] == "color_palette"
    assert body["new_value"] == ["#FF0000", "#00FF00", "#0000FF"]


# ─── Router registration ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_creative_studio_router_registered(client: AsyncClient):
    """The OpenAPI schema should include creative-studio endpoints."""
    res = await client.get("/openapi.json")
    assert res.status_code == 200
    paths = res.json().get("paths", {})
    cs_paths = [p for p in paths if p.startswith("/creative-studio")]
    assert any(p == "/creative-studio/generate" for p in cs_paths)
    assert any(p.startswith("/creative-studio/generate/{format_id}") for p in cs_paths)
    assert any(p == "/creative-studio/regenerate-field" for p in cs_paths)
    assert any(p == "/creative-studio/{package_id}" for p in cs_paths)
