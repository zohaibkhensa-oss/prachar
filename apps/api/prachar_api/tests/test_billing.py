"""Tests for the billing/payments module — plans, pricing, and endpoints.

Verifies:
  1. Plans are env-driven (no hardcoded values)
  2. Plan deliverables are complete
  3. /billing/plans endpoint returns all 3 plans
  4. /billing/subscription returns current status
  5. /billing/checkout validates provider + plan
  6. Webhook signature verification works

API tests use the same async pattern as test_s0_acceptance.py (real DB).
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

from prachar_shared import plans as plans_mod
from prachar_shared.plans import get_plan, get_plans, list_plans


@pytest.fixture
async def client():
    """Fresh DB engine + ASGI client per test (matches test_s0 pattern)."""
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


async def _register(c: AsyncClient, plan: str = "starter") -> dict:
    res = await c.post("/auth/register", json={
        "email": f"billing-{uuid.uuid4().hex[:8]}@test.com",
        "password": "testpass123",
        "tenant_name": f"Billing Test {uuid.uuid4().hex[:6]}",
        "plan": plan,
    })
    assert res.status_code == 201, res.text
    return res.json()


# ─── Plans module tests (pure, no DB) ───────────────────────────────────────

class TestPlansModule:
    def test_three_plans_exist(self):
        plans = get_plans()
        assert set(plans.keys()) == {"starter", "growth", "agency"}

    def test_starter_pricing(self):
        p = get_plan("starter")
        assert p is not None
        assert p.price_inr > 0
        assert p.price_usd > 0
        assert p.brands_limit == 1
        assert p.videos_per_month == 2
        assert p.video_quality_tier == "lite"

    def test_growth_pricing(self):
        p = get_plan("growth")
        assert p is not None
        assert p.price_inr > get_plan("starter").price_inr
        assert p.popular is True
        assert p.google_ads is True
        assert p.meta_ads is True
        assert p.video_quality_tier == "fast"

    def test_agency_pricing(self):
        p = get_plan("agency")
        assert p is not None
        assert p.price_inr > get_plan("growth").price_inr
        assert p.brands_limit == 5
        assert p.videos_per_month == -1  # unlimited
        assert p.white_label is True
        assert p.api_access is True
        assert p.video_quality_tier == "standard"

    def test_deliverables_non_empty(self):
        for p in list_plans():
            assert len(p.deliverables) >= 10, f"{p.key} has too few deliverables"

    def test_to_dict_serializable(self):
        for p in list_plans():
            d = p.to_dict()
            assert "key" in d
            assert "price_inr" in d
            assert "deliverables" in d
            assert isinstance(d["deliverables"], list)

    def test_quality_tier_ranking(self):
        assert get_plan("starter").video_quality_tier == "lite"
        assert get_plan("growth").video_quality_tier == "fast"
        assert get_plan("agency").video_quality_tier == "standard"

    def test_pricing_is_env_driven(self, monkeypatch):
        """Pricing should come from Settings (env), not hardcoded."""
        plans_mod.reset_plans_cache()
        from prachar_shared.config import Settings
        custom = Settings()
        monkeypatch.setattr(custom, "plan_starter_price_inr", 1499)
        monkeypatch.setattr(plans_mod, "get_settings", lambda: custom)
        plans_mod.reset_plans_cache()
        try:
            p = get_plan("starter")
            assert p.price_inr == 1499
        finally:
            plans_mod.reset_plans_cache()


# ─── Billing API tests (real DB) ────────────────────────────────────────────

class TestBillingAPI:
    @pytest.mark.asyncio
    async def test_plans_endpoint_returns_all_plans(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.get("/billing/plans", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["plans"]) == 3
        plan_keys = {p["key"] for p in data["plans"]}
        assert plan_keys == {"starter", "growth", "agency"}
        for p in data["plans"]:
            assert len(p["deliverables"]) >= 10
            assert p["price_inr"] > 0

    @pytest.mark.asyncio
    async def test_subscription_endpoint(self, client: AsyncClient):
        tok = await _register(client, plan="growth")
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.get("/billing/subscription", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "growth"

    @pytest.mark.asyncio
    async def test_checkout_rejects_unknown_provider(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post("/billing/checkout", headers=headers, json={
            "plan": "growth",
            "provider": "paypal",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_rejects_unknown_plan(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post("/billing/checkout", headers=headers, json={
            "plan": "enterprise",
            "provider": "stripe",
        })
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_stripe_without_key_returns_503(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post("/billing/checkout", headers=headers, json={
            "plan": "growth",
            "provider": "stripe",
        })
        assert resp.status_code in (503, 502)

    @pytest.mark.asyncio
    async def test_usage_endpoint(self, client: AsyncClient):
        tok = await _register(client, plan="agency")
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.get("/billing/usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "agency"
        assert data["brands_limit"] == 5
        assert data["videos_limit"] == -1  # unlimited


# ─── Webhook tests ──────────────────────────────────────────────────────────

class TestWebhooks:
    @pytest.mark.asyncio
    async def test_stripe_webhook_without_secret_returns_503(self, client: AsyncClient):
        resp = await client.post("/billing/webhook/stripe", json={"type": "test"})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_razorpay_webhook_without_secret_returns_503(self, client: AsyncClient):
        resp = await client.post("/billing/webhook/razorpay", json={"event": "test"})
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_stripe_webhook_invalid_signature_returns_400(self, client: AsyncClient, monkeypatch):
        from prachar_shared.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "stripe_webhook_secret", "whsec_test123")
        monkeypatch.setattr(s, "stripe_api_key", "sk_test_123")
        resp = await client.post(
            "/billing/webhook/stripe",
            json={"type": "test"},
            headers={"Stripe-Signature": "invalid_sig"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_razorpay_webhook_invalid_signature_returns_400(self, client: AsyncClient, monkeypatch):
        from prachar_shared.config import get_settings
        s = get_settings()
        monkeypatch.setattr(s, "razorpay_webhook_secret", "whsec_test123")
        resp = await client.post(
            "/billing/webhook/razorpay",
            json={"event": "test"},
            headers={"X-Razorpay-Signature": "invalid_sig"},
        )
        assert resp.status_code == 400


class TestBillingInvoices:
    """Tests for the /billing/invoices endpoint."""

    @pytest.mark.asyncio
    async def test_invoices_empty_when_no_subscription(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.get("/billing/invoices", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["invoices"] == []


class TestBillingCoupons:
    """Tests for the /billing/coupons/validate endpoint."""

    @pytest.mark.asyncio
    async def test_valid_coupon(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post(
            "/billing/coupons/validate",
            json={"code": "LAUNCH50", "plan": "starter"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["discount_pct"] == 50
        assert data["discount_amount"] > 0

    @pytest.mark.asyncio
    async def test_invalid_coupon(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post(
            "/billing/coupons/validate",
            json={"code": "INVALID", "plan": "starter"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False

    @pytest.mark.asyncio
    async def test_coupon_wrong_plan(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post(
            "/billing/coupons/validate",
            json={"code": "EARLYBIRD25", "plan": "agency"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert "not valid for agency" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_coupon_case_insensitive(self, client: AsyncClient):
        tok = await _register(client)
        headers = {"Authorization": f"Bearer {tok['access_token']}"}
        resp = await client.post(
            "/billing/coupons/validate",
            json={"code": "launch50", "plan": "starter"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
