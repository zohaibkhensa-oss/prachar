"""Contract regression tests — frontend↔API endpoint alignment.

Guards against the dead-route regression found in the activation audit:
frontend pages called /brands/{id}/campaigns, /brands/{id}/content,
/brands/{id}/reports and /campaigns/{id}/budget — none of which existed.

Verifies the corrected contracts:
  GET  /campaigns?brand_id={id}
  POST /campaigns/{campaign_id}/budget
  GET  /brands/{brand_id}/content
  GET  /reports/brands/{brand_id}/reports
  POST /billing/webhook/razorpay  (valid signature activates plan)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

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


async def _register(c: AsyncClient) -> dict:
    res = await c.post("/auth/register", json={
        "email": f"contract-{uuid.uuid4().hex[:8]}@test.com",
        "password": "testpass123",
        "tenant_name": f"Contract Test {uuid.uuid4().hex[:6]}",
    })
    assert res.status_code == 201, res.text
    return res.json()


async def _brand(c: AsyncClient, headers: dict, name: str = "Contract Brand") -> str:
    res = await c.post("/brands", json={
        "name": name, "website": "https://example.com", "category": "tech",
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def _campaign(c: AsyncClient, headers: dict, brand_id: str, budget: float = 100.0) -> dict:
    res = await c.post("/campaigns", json={
        "brand_id": brand_id, "network": "google_ads", "objective": "traffic",
        "audience_spec": {"geo": ["IN"]}, "budget_daily": budget,
        "currency": "INR", "dry_run": True,
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


class TestCampaignContract:
    async def test_list_campaigns_filters_by_brand(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        b1 = await _brand(client, headers, "Brand One")
        b2 = await _brand(client, headers, "Brand Two")
        await _campaign(client, headers, b1)

        res = await client.get("/campaigns", params={"brand_id": b1}, headers=headers)
        assert res.status_code == 200, res.text
        assert all(c["brand_id"] == b1 for c in res.json())

        res = await client.get("/campaigns", params={"brand_id": b2}, headers=headers)
        assert res.status_code == 200
        assert res.json() == []

    async def test_set_budget_updates_campaign(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        brand_id = await _brand(client, headers)
        camp = await _campaign(client, headers, brand_id)

        res = await client.post(
            f"/campaigns/{camp['id']}/budget", json={"budget": 250.0}, headers=headers
        )
        assert res.status_code == 200, res.text
        assert res.json()["budget_daily"] == 250.0

    async def test_set_budget_rejects_invalid(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        brand_id = await _brand(client, headers)
        camp = await _campaign(client, headers, brand_id)
        res = await client.post(
            f"/campaigns/{camp['id']}/budget", json={"budget": -10}, headers=headers
        )
        assert res.status_code == 422

    async def test_set_budget_404_unknown_campaign(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        res = await client.post(
            f"/campaigns/{uuid.uuid4()}/budget", json={"budget": 10}, headers=headers
        )
        assert res.status_code == 404


class TestBrandContentContract:
    async def test_brand_content_empty_ok(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        brand_id = await _brand(client, headers)
        res = await client.get(f"/brands/{brand_id}/content", headers=headers)
        assert res.status_code == 200, res.text
        assert res.json() == []

    async def test_brand_content_404_unknown_brand(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        res = await client.get(f"/brands/{uuid.uuid4()}/content", headers=headers)
        assert res.status_code == 404


class TestReportsContract:
    async def test_list_reports_shape(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        brand_id = await _brand(client, headers)
        res = await client.get(f"/reports/brands/{brand_id}/reports", headers=headers)
        assert res.status_code == 200, res.text
        assert res.json() == []

    async def test_report_download_404_without_pdf(self, client: AsyncClient):
        reg = await _register(client)
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        brand_id = await _brand(client, headers)
        res = await client.get(
            f"/reports/brands/{brand_id}/reports/{uuid.uuid4()}/download", headers=headers
        )
        assert res.status_code == 404


class TestRazorpayWebhookActivation:
    async def test_valid_signature_activates_plan(self, client: AsyncClient, monkeypatch):
        """A correctly-signed subscription.activated flips tenant.plan → growth."""
        s = get_settings()
        monkeypatch.setattr(s, "razorpay_webhook_secret", "whsec_contract_test")

        reg = await _register(client)
        tenant_id = reg["user"]["tenant_id"]

        body = json.dumps({
            "event": "subscription.activated",
            "payload": {"subscription": {"entity": {
                "id": f"sub_{uuid.uuid4().hex[:10]}",
                "notes": {"tenant_id": tenant_id, "plan": "growth"},
            }}},
        }).encode()
        sig = hmac.new(b"whsec_contract_test", body, hashlib.sha256).hexdigest()

        res = await client.post(
            "/billing/webhook/razorpay",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": sig,
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["action"] == "subscription_activated"

        # Entitlement actually flipped — plan resolves to growth now.
        headers = {"Authorization": f"Bearer {reg['access_token']}"}
        sub = await client.get("/billing/subscription", headers=headers)
        assert sub.status_code == 200
        assert sub.json()["plan"] in ("growth", "agency")

    async def test_tampered_signature_rejected(self, client: AsyncClient, monkeypatch):
        s = get_settings()
        monkeypatch.setattr(s, "razorpay_webhook_secret", "whsec_contract_test")
        res = await client.post(
            "/billing/webhook/razorpay",
            content=b'{"event":"subscription.activated"}',
            headers={
                "Content-Type": "application/json",
                "X-Razorpay-Signature": "forged" * 10,
            },
        )
        assert res.status_code == 400
