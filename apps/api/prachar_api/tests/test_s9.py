from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from prachar_api.main import create_app
from prachar_api.routers import admin


@pytest.fixture
def client():
    return TestClient(create_app())


def test_admin_router_registered():
    """Admin router is registered on the app."""
    app = create_app()
    schema = app.openapi()
    paths = list(schema.get("paths", {}).keys())
    assert any("/admin" in p for p in paths)


def test_white_label_config_model():
    """WhiteLabelConfig accepts valid input."""
    cfg = admin.WhiteLabelConfig(
        agency_name="Acme Agency",
        logo_url="https://example.com/logo.png",
        primary_color="#FFD400",
        accent_color="#141414",
        footer_text="Powered by Acme",
    )
    assert cfg.agency_name == "Acme Agency"
    assert cfg.primary_color == "#FFD400"


def test_white_label_config_defaults():
    """WhiteLabelConfig has correct defaults."""
    cfg = admin.WhiteLabelConfig(agency_name="Test")
    assert cfg.primary_color == "#FFD400"
    assert cfg.accent_color == "#141414"
    assert cfg.logo_url is None
    assert cfg.footer_text is None


def test_api_token_create_model():
    """APITokenCreate accepts valid input."""
    tok = admin.APITokenCreate(name="CI token", scopes=["read", "write"])
    assert tok.name == "CI token"
    assert "read" in tok.scopes


def test_api_token_create_defaults():
    """APITokenCreate defaults to read-only scope."""
    tok = admin.APITokenCreate(name="Default")
    assert tok.scopes == ["read"]


def test_cost_dashboard_model():
    """CostDashboard model is constructible."""
    dash = admin.CostDashboard(
        tenants=[],
        total_ai_tokens=0,
        total_ai_budget=100000,
        total_brands=0,
        total_campaigns=0,
        avg_utilization=0.0,
    )
    assert dash.total_ai_budget == 100000
    assert dash.tenants == []


def test_brand_summary_model():
    """BrandSummary model is constructible."""
    bs = admin.BrandSummary(
        brand_id=uuid.uuid4(),
        name="Test Brand",
        visibility_score=42.5,
        campaign_count=3,
        active_channels=5,
        weekly_spend=1500.0,
    )
    assert bs.name == "Test Brand"
    assert bs.visibility_score == 42.5


def test_conversion_out_model():
    """ConversionOut from attribution router is constructible."""
    from prachar_api.routers.attribution import ConversionOut

    out = ConversionOut(
        id=uuid.uuid4(),
        attributed_network="google_ads",
        position_based_credit={"google_ads": 0.4, "meta_ads": 0.6},
    )
    assert out.attributed_network == "google_ads"
    assert out.position_based_credit["meta_ads"] == 0.6
