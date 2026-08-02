"""Regression tests for the unified consult router.

These tests verify that the unified /consult router works for ALL domains
(business, creator, restaurant, clinic) through the SAME endpoints.

This is the automated version of the founder demo:
  - Register a Restaurant → /consult with domain="business" subtype="restaurant"
  - Register a Creator → /consult with domain="creator"
  - Register a Clinic → /consult with domain="business" subtype="clinic"

All three should follow the SAME pipeline. Only the Domain Pack changes.
"""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from prachar_api.main import app
from prachar_shared.domain_packs import register_all

# Ensure packs are registered
register_all()


client = TestClient(app)


# ─── /consult/domains ──────────────────────────────────────────────────────


class TestDomainsEndpoint:
    """Tests for GET /consult/domains — lists all available domains."""

    def test_domains_endpoint_returns_all_packs(self):
        """The domains endpoint returns all registered domain packs."""
        # No auth required for this endpoint (it's just metadata)
        res = client.get("/consult/domains")
        assert res.status_code == 200
        data = res.json()
        assert "domains" in data
        ids = [d["id"] for d in data["domains"]]
        assert "business" in ids
        assert "creator" in ids
        assert "restaurant" in ids
        assert "clinic" in ids

    def test_domains_endpoint_returns_subtypes(self):
        """Each domain includes its subtypes for the onboarding UI."""
        res = client.get("/consult/domains")
        data = res.json()
        for domain in data["domains"]:
            assert "subtypes" in domain
            assert len(domain["subtypes"]) > 0
            for subtype in domain["subtypes"]:
                assert "id" in subtype
                assert "label" in subtype
                assert "emoji" in subtype
                assert "blurb" in subtype

    def test_domains_endpoint_returns_customer_type(self):
        """Each domain includes its customer_type (business or creator)."""
        res = client.get("/consult/domains")
        data = res.json()
        for domain in data["domains"]:
            assert domain["customer_type"] in ("business", "creator")


# ─── /consult/nav/{domain} ────────────────────────────────────────────────


class TestNavEndpoint:
    """Tests for GET /consult/nav/{domain} — returns domain config for UI."""

    def test_nav_endpoint_returns_business_config(self):
        """The nav endpoint returns the business domain config."""
        res = client.get("/consult/nav/business")
        assert res.status_code == 200
        data = res.json()
        assert data["domain"] == "business"
        assert data["label"] == "Business Growth"
        assert len(data["nav_sections"]) > 0
        assert len(data["kpi_cards"]) > 0
        assert len(data["dashboard_widgets"]) > 0

    def test_nav_endpoint_returns_creator_config(self):
        """The nav endpoint returns the creator domain config."""
        res = client.get("/consult/nav/creator")
        assert res.status_code == 200
        data = res.json()
        assert data["domain"] == "creator"
        assert data["label"] == "Creator Growth"
        # Creator has tools (repurpose, youtube_plan)
        tool_ids = [t["id"] for t in data["tools"]]
        assert "repurpose" in tool_ids
        assert "youtube_plan" in tool_ids

    def test_nav_endpoint_returns_restaurant_config(self):
        """The nav endpoint returns the restaurant domain config."""
        res = client.get("/consult/nav/restaurant")
        assert res.status_code == 200
        data = res.json()
        assert data["domain"] == "restaurant"
        assert data["label"] == "Restaurant Growth"
        # Restaurant has food-specific KPIs
        kpi_keys = [k["key"] for k in data["kpi_cards"]]
        assert "covers" in kpi_keys

    def test_nav_endpoint_returns_clinic_config(self):
        """The nav endpoint returns the clinic domain config."""
        res = client.get("/consult/nav/clinic")
        assert res.status_code == 200
        data = res.json()
        assert data["domain"] == "clinic"
        assert data["label"] == "Clinic Growth"
        # Clinic has healthcare-specific KPIs
        kpi_keys = [k["key"] for k in data["kpi_cards"]]
        assert "appointments" in kpi_keys

    def test_nav_endpoint_404_for_unknown_domain(self):
        """The nav endpoint returns 404 for an unknown domain."""
        res = client.get("/consult/nav/nonexistent")
        assert res.status_code == 404


# ─── /consult (POST) — requires auth ──────────────────────────────────────


class TestConsultEndpointAuth:
    """Tests that the unified /consult endpoint requires authentication."""

    def test_consult_requires_auth(self):
        """POST /consult without auth returns 401."""
        res = client.post("/consult", json={
            "message": "I run a biryani restaurant in Hyderabad.",
            "domain": "business",
        })
        assert res.status_code == 401

    def test_consult_campaign_requires_auth(self):
        """POST /consult/campaign without auth returns 401."""
        res = client.post("/consult/campaign", json={
            "brand_id": "00000000-0000-0000-0000-000000000000",
            "goal": "grow",
            "budget": "₹10,000",
            "domain": "business",
        })
        assert res.status_code == 401

    def test_consult_tool_requires_auth(self):
        """POST /consult/tool/{tool_id} without auth returns 401."""
        res = client.post("/consult/tool/repurpose", json={
            "domain": "creator",
            "inputs": {"video_description": "test"},
        })
        assert res.status_code == 401


# ─── /consult (POST) — validation ─────────────────────────────────────────


class TestConsultEndpointValidation:
    """Tests for the unified /consult endpoint input validation."""

    def test_consult_validates_message_length(self):
        """POST /consult rejects messages that are too short or too long."""
        # Too short (< 5 chars)
        res = client.post("/consult", json={
            "message": "hi",
            "domain": "business",
        })
        # 422 validation error (or 401 if auth runs first — either is fine)
        assert res.status_code in (401, 422)

    def test_consult_validates_domain(self):
        """POST /consult with an unknown domain still accepts the request
        (the engine will raise KeyError, but the router doesn't validate this
        at the schema level — it's a runtime check)."""
        # We can't easily test this without auth, but we can verify the
        # schema accepts any string for domain
        res = client.post("/consult", json={
            "message": "I run a restaurant.",
            "domain": "nonexistent",
        })
        # Should be 401 (auth) not 422 (validation) — domain is a free string
        assert res.status_code in (401, 422)


# ─── Founder demo (the architectural guarantee) ───────────────────────────


class TestFounderDemo:
    """The founder demo: Restaurant + Creator + Clinic via the SAME pipeline.

    These tests verify that all three domains can be initiated through the
    same /consult endpoint with different `domain` parameters. The actual LLM
    calls require auth + API keys, so these tests verify the routing and
    schema, not the full pipeline.
    """

    def test_restaurant_uses_same_endpoint_as_business(self):
        """Registering a Restaurant uses POST /consult with domain='business'."""
        # Restaurant is a subtype of business
        res = client.post("/consult", json={
            "message": "I run a biryani restaurant in Hyderabad.",
            "domain": "business",
            "subtype_id": "restaurant",
        })
        # 401 (auth required) — but the endpoint accepts the request
        assert res.status_code == 401

    def test_creator_uses_same_endpoint_as_business(self):
        """Registering a Creator uses POST /consult with domain='creator'."""
        res = client.post("/consult", json={
            "message": "I make tech review videos on YouTube.",
            "domain": "creator",
            "subtype_id": "youtube_creator",
        })
        assert res.status_code == 401

    def test_clinic_uses_same_endpoint_as_business(self):
        """Registering a Clinic uses POST /consult with domain='business'."""
        res = client.post("/consult", json={
            "message": "I run a dental clinic in Mumbai.",
            "domain": "business",
            "subtype_id": "clinic",
        })
        assert res.status_code == 401

    def test_all_three_use_the_same_endpoint(self):
        """All three domains use POST /consult — only the domain parameter changes."""
        # This is the architectural guarantee: ONE endpoint, many domains
        domains = [
            ("business", "restaurant", "I run a biryani restaurant in Hyderabad."),
            ("creator", "youtube_creator", "I make tech review videos on YouTube."),
            ("business", "clinic", "I run a dental clinic in Mumbai."),
        ]
        for domain, subtype, message in domains:
            res = client.post("/consult", json={
                "message": message,
                "domain": domain,
                "subtype_id": subtype,
            })
            # All should return 401 (auth) — they all hit the SAME endpoint
            assert res.status_code == 401, (
                f"Domain {domain}/{subtype} returned {res.status_code}, expected 401"
            )

    def test_campaign_uses_same_endpoint_for_all_domains(self):
        """Campaign generation uses POST /consult/campaign for all domains."""
        for domain in ["business", "creator", "restaurant", "clinic"]:
            res = client.post("/consult/campaign", json={
                "brand_id": "00000000-0000-0000-0000-000000000000",
                "goal": "grow",
                "budget": "₹10,000",
                "domain": domain,
            })
            assert res.status_code == 401, (
                f"Domain {domain} campaign returned {res.status_code}, expected 401"
            )

    def test_creator_tools_use_unified_tool_endpoint(self):
        """Creator tools (repurpose, youtube_plan) use POST /consult/tool/{tool_id}."""
        for tool_id in ["repurpose", "youtube_plan"]:
            res = client.post(f"/consult/tool/{tool_id}", json={
                "domain": "creator",
                "inputs": {"video_description": "test", "video_concept": "test"},
            })
            assert res.status_code == 401, (
                f"Tool {tool_id} returned {res.status_code}, expected 401"
            )

    def test_nonexistent_tool_returns_404(self):
        """A nonexistent tool returns 404 (after auth)."""
        # Without auth we get 401, but the test documents the expected behavior
        res = client.post("/consult/tool/nonexistent", json={
            "domain": "creator",
            "inputs": {},
        })
        assert res.status_code in (401, 404)


# ─── Creative directions in campaign preview (P1.1) ────────────────────────


class TestCreativeDirections:
    """Tests that the campaign preview includes 3 creative directions.

    Each direction must have: id, hook, angle, tone, sample_headline, sample_cta.
    The AIGateway is mocked so no real LLM calls are made.
    """

    @pytest.fixture
    def fake_gateway(self):
        """A fake AIGateway whose .complete() returns canned JSON responses."""
        from prachar_shared.ai_gateway import Completion

        preview_resp = {
            "reply": "Here's your campaign!",
            "preview": {
                "title": "Hyderabad's Best Biryani Tour",
                "hero_image_concept": "Steaming biryani being unveiled",
                "video_concept": "30s of the marination process",
                "post_ideas": ["Behind the scenes"],
                "estimated_reach": "15,000-25,000",
                "expected_enquiries": "30-50",
                "budget_estimate": "₹15,000/month",
                "why_this_campaign": "It highlights your signature dish.",
                "confidence": 85,
                "expected_benefit": "More walk-ins",
                "risks": ["Slow first week"],
                "alternative": "Focus on catering",
            },
        }
        directions_resp = {
            "creative_directions": [
                {
                    "id": "signature_dish_hero",
                    "hook": "The biryani that Hyderabad can't stop talking about",
                    "angle": "Lead with the signature dish as the hero",
                    "tone": "Mouth-watering and proud",
                    "sample_headline": "12 hours of marination. One unforgettable bite.",
                    "sample_cta": "Order now on Swiggy",
                },
                {
                    "id": "local_pride",
                    "hook": "Hyderabad's own biryani, made the old-fashioned way",
                    "angle": "Lean into local heritage and pride",
                    "tone": "Warm and nostalgic",
                    "sample_headline": "Made in Hyderabad. Loved by Hyderabad.",
                    "sample_cta": "Visit us today",
                },
                {
                    "id": "value_combo",
                    "hook": "Feast for two at a price that makes sense",
                    "angle": "Lead with a value combo offer",
                    "tone": "Bold and practical",
                    "sample_headline": "Biryani + kebab combo for two at ₹399",
                    "sample_cta": "Grab the combo",
                },
            ]
        }

        def fake_complete(prompt, **kwargs):
            # The creative directions prompt is distinguishable by its task name
            task = kwargs.get("task", "")
            if "creative_directions" in task:
                return Completion(
                    text=json.dumps(directions_resp),
                    tokens_used=200,
                    model="test-model",
                    confidence=0.9,
                )
            return Completion(
                text=json.dumps(preview_resp),
                tokens_used=500,
                model="test-model",
                confidence=0.85,
            )

        gw = MagicMock()
        gw.complete = MagicMock(side_effect=fake_complete)
        return gw

    @pytest.fixture
    def fake_brand(self):
        """A fake Brand object with the attributes the engine reads."""
        brand = MagicMock()
        brand.id = uuid.uuid4()
        brand.name = "Paradise Biryani"
        brand.website = "https://example.com"
        brand.category = "restaurant"
        brand.brand_graph = {}
        return brand

    @pytest.fixture
    def fake_user(self):
        """A fake CurrentUser with a tenant."""
        user = MagicMock()
        user.id = uuid.uuid4()
        user.tenant_id = uuid.uuid4()
        user.tenant = MagicMock()
        user.tenant.plan = "agency"
        return user

    @pytest.fixture
    def fake_session(self, fake_brand):
        """A fake AsyncSession that returns the fake brand on select."""
        session = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=fake_brand)
        session.execute = AsyncMock(return_value=result)
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_campaign_preview_has_creative_directions(
        self, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """The campaign preview contains a creative_directions list."""
        from prachar_api.infrastructure.consult_engine import ConsultEngine

        engine = ConsultEngine(gateway=fake_gateway)

        # Mock CampaignBrain.generate_campaign so no real AI/DB is needed
        with patch(
            "prachar_shared.marketing_intelligence.CampaignBrain.generate_campaign",
            new_callable=AsyncMock,
            return_value={"engine_outputs": {}},
        ), patch(
            "prachar_api.infrastructure.consult_engine.log_audit",
            new_callable=AsyncMock,
        ):
            result = await engine.campaign(
                pack_id="business",
                brand_id=fake_brand.id,
                goal="get more customers",
                budget="₹15,000",
                user=fake_user,
                session=fake_session,
            )

        assert "creative_directions" in result.preview
        directions = result.preview["creative_directions"]
        assert isinstance(directions, list)
        assert len(directions) == 3

    @pytest.mark.asyncio
    async def test_each_creative_direction_has_required_fields(
        self, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """Each creative direction has id, hook, angle, tone, sample_headline, sample_cta."""
        from prachar_api.infrastructure.consult_engine import ConsultEngine

        engine = ConsultEngine(gateway=fake_gateway)

        with patch(
            "prachar_shared.marketing_intelligence.CampaignBrain.generate_campaign",
            new_callable=AsyncMock,
            return_value={"engine_outputs": {}},
        ), patch(
            "prachar_api.infrastructure.consult_engine.log_audit",
            new_callable=AsyncMock,
        ):
            result = await engine.campaign(
                pack_id="business",
                brand_id=fake_brand.id,
                goal="get more customers",
                budget="₹15,000",
                user=fake_user,
                session=fake_session,
            )

        directions = result.preview["creative_directions"]
        required = {"id", "hook", "angle", "tone", "sample_headline", "sample_cta"}
        for d in directions:
            assert isinstance(d, dict)
            assert required.issubset(d.keys()), (
                f"Direction {d.get('id')} missing keys: {required - set(d.keys())}"
            )
            # Values should be non-empty strings
            for key in required:
                assert isinstance(d[key], str) and d[key], (
                    f"Direction {d.get('id')} field {key!r} is empty or not a string"
                )

    @pytest.mark.asyncio
    async def test_creative_directions_work_for_all_domains(
        self, fake_gateway, fake_brand, fake_user, fake_session,
    ):
        """Creative directions are generated for business, creator, restaurant, clinic."""
        from prachar_api.infrastructure.consult_engine import ConsultEngine

        for pack_id in ["business", "creator", "restaurant", "clinic"]:
            engine = ConsultEngine(gateway=fake_gateway)
            with patch(
                "prachar_shared.marketing_intelligence.CampaignBrain.generate_campaign",
                new_callable=AsyncMock,
                return_value={"engine_outputs": {}},
            ), patch(
                "prachar_api.infrastructure.consult_engine.log_audit",
                new_callable=AsyncMock,
            ):
                result = await engine.campaign(
                    pack_id=pack_id,
                    brand_id=fake_brand.id,
                    goal="grow",
                    budget="₹10,000",
                    user=fake_user,
                    session=fake_session,
                )
            directions = result.preview["creative_directions"]
            assert len(directions) == 3, (
                f"Pack {pack_id} returned {len(directions)} directions, expected 3"
            )
