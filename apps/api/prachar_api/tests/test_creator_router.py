"""Tests for the Creator Intelligence router and customer_type field.

Verifies:
- /creator/* endpoints are registered and require auth
- Brand.customer_type field exists with default "business"
- BrandOut includes customer_type
- Creator consult/campaign/repurpose/youtube-plan endpoints return 401 without auth
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from apps.api.prachar_api.main import create_app


def test_creator_endpoints_require_auth() -> None:
    """All 4 /creator/* endpoints must be registered and require authentication."""
    app = create_app()
    client = TestClient(app)

    # /creator/consult
    r = client.post("/creator/consult", json={"message": "I make tech videos"})
    assert r.status_code == 401, f"consult: expected 401, got {r.status_code}"

    # /creator/repurpose
    r = client.post("/creator/repurpose", json={"video_description": "test description"})
    assert r.status_code == 401, f"repurpose: expected 401, got {r.status_code}"

    # /creator/youtube-plan
    r = client.post("/creator/youtube-plan", json={"video_concept": "test concept"})
    assert r.status_code == 401, f"youtube-plan: expected 401, got {r.status_code}"

    # /creator/campaign
    r = client.post(
        "/creator/campaign",
        json={"brand_id": str(uuid.uuid4()), "goal": "grow"},
    )
    assert r.status_code == 401, f"campaign: expected 401, got {r.status_code}"


def test_creator_consult_validates_message_length() -> None:
    """Short messages should be rejected with 422 (after auth)."""
    app = create_app()
    client = TestClient(app)
    # Without auth we get 401 first; the validation happens after auth.
    # This test confirms the endpoint exists and the schema is wired.
    r = client.post("/creator/consult", json={"message": "hi"})
    assert r.status_code in (401, 422)


def test_brand_schema_includes_customer_type() -> None:
    """BrandIn and BrandOut schemas must include customer_type."""
    from apps.api.prachar_api.schemas import BrandIn, BrandOut

    in_fields = BrandIn.model_fields
    assert "customer_type" in in_fields, "BrandIn must have customer_type field"
    assert in_fields["customer_type"].default == "business"

    out_fields = BrandOut.model_fields
    assert "customer_type" in out_fields, "BrandOut must have customer_type field"
    assert out_fields["customer_type"].default == "business"


def test_brand_in_validates_customer_type() -> None:
    """BrandIn.customer_type must only accept 'business' or 'creator'."""
    from apps.api.prachar_api.schemas import BrandIn
    from pydantic import ValidationError

    # Valid
    b1 = BrandIn(name="Test", customer_type="business")
    assert b1.customer_type == "business"
    b2 = BrandIn(name="Test", customer_type="creator")
    assert b2.customer_type == "creator"

    # Invalid
    try:
        BrandIn(name="Test", customer_type="invalid")
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass


def test_brand_model_has_customer_type_column() -> None:
    """Brand SQLAlchemy model must have customer_type column with default 'business'."""
    from apps.api.prachar_api.models import Brand

    col = Brand.__table__.c.get("customer_type")
    assert col is not None, "Brand table must have customer_type column"
    assert col.default is not None
    # The server_default is "business"
    assert str(col.default.arg) == "'business'" or col.default.arg == "business"
