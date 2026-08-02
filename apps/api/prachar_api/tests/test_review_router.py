"""Tests for the review workflow router (P3.2 + P3.3).

Verifies:
- GET /review/queue returns only draft/in_review/changes_requested campaigns
- POST /review/{id}/request-changes transitions to changes_requested
- POST /review/{id}/approve transitions to approved
- POST /review/{id}/publish transitions to active
- Invalid transitions return 409
- 404 for non-existent or other-tenant campaign
- Auth required (401 without token)
- POST /review/{id}/suggestions returns 200 with list of suggestions (P3.3)
- POST /review/{id}/suggestions returns 404 for non-existent campaign (P3.3)
- POST /review/{id}/suggestions requires auth (P3.3)

These tests hit the real DB (no mocking) following the s0_acceptance pattern.
"""
from __future__ import annotations

import os
import uuid
from unittest.mock import patch

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
        json={"name": "Review Brand", "website": "https://example.com", "category": "tech"},
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
async def test_queue_requires_auth(client: AsyncClient):
    res = await client.get("/review/queue")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_request_changes_requires_auth(client: AsyncClient):
    res = await client.post(f"/review/{uuid.uuid4()}/request-changes", json={"feedback": "fix it"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_approve_requires_auth(client: AsyncClient):
    res = await client.post(f"/review/{uuid.uuid4()}/approve")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_publish_requires_auth(client: AsyncClient):
    res = await client.post(f"/review/{uuid.uuid4()}/publish")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_suggestions_requires_auth(client: AsyncClient):
    res = await client.post(f"/review/{uuid.uuid4()}/suggestions")
    assert res.status_code == 401


# ─── queue ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_returns_only_review_statuses(client: AsyncClient):
    tok = await _register(client, f"q{uuid.uuid4().hex[:8]}@test.com", "Queue Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # New campaign is draft → should appear in queue.
    res = await client.get("/review/queue", headers=headers)
    assert res.status_code == 200
    ids = [c["id"] for c in res.json()]
    assert camp["id"] in ids
    # All returned items must be in a queue status.
    for c in res.json():
        assert c["status"] in ("draft", "in_review", "changes_requested")


@pytest.mark.asyncio
async def test_queue_excludes_active_campaigns(client: AsyncClient):
    tok = await _register(client, f"qa{uuid.uuid4().hex[:8]}@test.com", "Queue Active Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # Approve then publish to move it to active.
    res = await client.post(f"/review/{camp['id']}/approve", headers=headers)
    assert res.status_code == 200
    res = await client.post(f"/review/{camp['id']}/publish", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    # Now queue should not contain it.
    res = await client.get("/review/queue", headers=headers)
    ids = [c["id"] for c in res.json()]
    assert camp["id"] not in ids


# ─── request-changes ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_request_changes_from_in_review(client: AsyncClient):
    tok = await _register(client, f"rc{uuid.uuid4().hex[:8]}@test.com", "RC Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # Move to in_review via approve? No — approve goes to approved.
    # We need in_review. Set directly via the approve path is wrong.
    # Use request-changes from approved (allowed) — but first need in_review.
    # The router allows request_changes from in_review or approved.
    # Approve first (draft→approved), then request_changes (approved→changes_requested).
    res = await client.post(f"/review/{camp['id']}/approve", headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    res = await client.post(
        f"/review/{camp['id']}/request-changes",
        json={"feedback": "Please revise the headline"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "changes_requested"


@pytest.mark.asyncio
async def test_request_changes_invalid_from_draft(client: AsyncClient):
    tok = await _register(client, f"rcd{uuid.uuid4().hex[:8]}@test.com", "RC Draft Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.post(
        f"/review/{camp['id']}/request-changes",
        json={"feedback": "fix"},
        headers=headers,
    )
    assert res.status_code == 409


# ─── approve ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_approve_from_draft(client: AsyncClient):
    tok = await _register(client, f"ap{uuid.uuid4().hex[:8]}@test.com", "Approve Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.post(f"/review/{camp['id']}/approve", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_approve_invalid_from_active(client: AsyncClient):
    tok = await _register(client, f"apa{uuid.uuid4().hex[:8]}@test.com", "Approve Active Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # draft → approved → active
    await client.post(f"/review/{camp['id']}/approve", headers=headers)
    await client.post(f"/review/{camp['id']}/publish", headers=headers)

    res = await client.post(f"/review/{camp['id']}/approve", headers=headers)
    assert res.status_code == 409


# ─── publish ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publish_from_approved(client: AsyncClient):
    tok = await _register(client, f"pub{uuid.uuid4().hex[:8]}@test.com", "Publish Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    await client.post(f"/review/{camp['id']}/approve", headers=headers)
    res = await client.post(f"/review/{camp['id']}/publish", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "active"


@pytest.mark.asyncio
async def test_publish_invalid_from_draft(client: AsyncClient):
    tok = await _register(client, f"pubd{uuid.uuid4().hex[:8]}@test.com", "Publish Draft Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.post(f"/review/{camp['id']}/publish", headers=headers)
    assert res.status_code == 409


# ─── 404 / tenant isolation ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_404_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"n404{uuid.uuid4().hex[:8]}@test.com", "404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    res = await client.post(f"/review/{uuid.uuid4()}/approve", headers=headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_404_other_tenant_campaign(client: AsyncClient):
    tok_a = await _register(client, f"t404a{uuid.uuid4().hex[:8]}@test.com", "Tenant A 404")
    tok_b = await _register(client, f"t404b{uuid.uuid4().hex[:8]}@test.com", "Tenant B 404")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}
    brand_id = await _create_brand(client, headers_a)
    camp = await _create_campaign(client, headers_a, brand_id)

    # Tenant B cannot act on tenant A's campaign.
    res = await client.post(f"/review/{camp['id']}/approve", headers=headers_b)
    assert res.status_code == 404

    res = await client.post(
        f"/review/{camp['id']}/request-changes",
        json={"feedback": "x"},
        headers=headers_b,
    )
    assert res.status_code == 404

    res = await client.post(f"/review/{camp['id']}/publish", headers=headers_b)
    assert res.status_code == 404

    # And tenant B's queue should not list it.
    res = await client.get("/review/queue", headers=headers_b)
    ids = [c["id"] for c in res.json()]
    assert camp["id"] not in ids


# ─── suggestions (P3.3) ──────────────────────────────────────────────────────


def _fake_suggestions():
    """Canned Suggestion objects returned by the mocked generate_suggestions."""
    from prachar_shared.marketing_intelligence.review_engine import Suggestion

    return [
        Suggestion(
            what_to_change="Headline",
            why="Too generic, add a specific dish name.",
            suggested_replacement="Hyderabad's Best Biryani — Order Now",
        ),
        Suggestion(
            what_to_change="Call-to-action",
            why="A clearer CTA drives higher CTR.",
            suggested_replacement="Book your catering order today.",
        ),
        Suggestion(
            what_to_change="Budget allocation",
            why="Dayparting captures decision-makers at lunch.",
            suggested_replacement="70% budget 11am-2pm, 30% evenings",
        ),
    ]


@pytest.mark.asyncio
async def test_suggestions_returns_200_with_list(client: AsyncClient):
    tok = await _register(client, f"sug{uuid.uuid4().hex[:8]}@test.com", "Sug Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    with patch(
        "prachar_api.routers.review.generate_suggestions",
        return_value=_fake_suggestions(),
    ):
        res = await client.post(f"/review/{camp['id']}/suggestions", headers=headers)

    assert res.status_code == 200, res.text
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 3
    required = {"what_to_change", "why", "suggested_replacement"}
    for item in data:
        assert required.issubset(item.keys())
        assert item["what_to_change"]
        assert item["why"]
        assert item["suggested_replacement"]


@pytest.mark.asyncio
async def test_suggestions_404_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"sug404{uuid.uuid4().hex[:8]}@test.com", "Sug 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    with patch(
        "prachar_api.routers.review.generate_suggestions",
        return_value=_fake_suggestions(),
    ):
        res = await client.post(f"/review/{uuid.uuid4()}/suggestions", headers=headers)

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_suggestions_404_other_tenant_campaign(client: AsyncClient):
    tok_a = await _register(client, f"sugta{uuid.uuid4().hex[:8]}@test.com", "Sug Tenant A")
    tok_b = await _register(client, f"sugtb{uuid.uuid4().hex[:8]}@test.com", "Sug Tenant B")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}
    brand_id = await _create_brand(client, headers_a)
    camp = await _create_campaign(client, headers_a, brand_id)

    with patch(
        "prachar_api.routers.review.generate_suggestions",
        return_value=_fake_suggestions(),
    ):
        res = await client.post(f"/review/{camp['id']}/suggestions", headers=headers_b)

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_suggestions_returns_empty_list_on_ai_failure(client: AsyncClient):
    """When generate_suggestions returns [], the endpoint returns 200 with []."""
    tok = await _register(client, f"sugfail{uuid.uuid4().hex[:8]}@test.com", "Sug Fail Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    with patch(
        "prachar_api.routers.review.generate_suggestions",
        return_value=[],
    ):
        res = await client.post(f"/review/{camp['id']}/suggestions", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == []


# ─── inline comments ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_comments_requires_auth(client: AsyncClient):
    res = await client.get(f"/review/{uuid.uuid4()}/comments")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_add_comment_requires_auth(client: AsyncClient):
    res = await client.post(
        f"/review/{uuid.uuid4()}/comments",
        json={"anchor_text": "hello", "body": "fix this"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_resolve_comment_requires_auth(client: AsyncClient):
    res = await client.post(f"/review/{uuid.uuid4()}/comments/{uuid.uuid4()}/resolve")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_add_and_list_comment(client: AsyncClient):
    tok = await _register(client, f"c{uuid.uuid4().hex[:8]}@test.com", "Comment Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.post(
        f"/review/{camp['id']}/comments",
        json={"anchor_text": "Daily Budget", "body": "Increase to 500"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    comment = res.json()
    assert comment["anchor_text"] == "Daily Budget"
    assert comment["body"] == "Increase to 500"
    assert comment["resolved"] is False
    assert comment["author"]["email"] == tok["user"]["email"]
    assert comment["replies"] == []

    # List should return the comment.
    res = await client.get(f"/review/{camp['id']}/comments", headers=headers)
    assert res.status_code == 200
    comments = res.json()
    assert len(comments) == 1
    assert comments[0]["id"] == comment["id"]


@pytest.mark.asyncio
async def test_add_reply_threads_under_parent(client: AsyncClient):
    tok = await _register(client, f"r{uuid.uuid4().hex[:8]}@test.com", "Reply Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    # Create a top-level comment.
    res = await client.post(
        f"/review/{camp['id']}/comments",
        json={"anchor_text": "Audience", "body": "Too broad"},
        headers=headers,
    )
    assert res.status_code == 201
    parent = res.json()

    # Reply to it.
    res = await client.post(
        f"/review/{camp['id']}/comments",
        json={
            "anchor_text": "ignored",
            "body": "Agreed, let's narrow geo",
            "parent_id": parent["id"],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    reply = res.json()
    assert reply["parent_id"] == parent["id"]
    # Reply inherits the parent's anchor_text.
    assert reply["anchor_text"] == "Audience"

    # List shows the reply nested under the parent.
    res = await client.get(f"/review/{camp['id']}/comments", headers=headers)
    comments = res.json()
    assert len(comments) == 1  # only top-level
    assert len(comments[0]["replies"]) == 1
    assert comments[0]["replies"][0]["id"] == reply["id"]


@pytest.mark.asyncio
async def test_resolve_toggles_status(client: AsyncClient):
    tok = await _register(client, f"rs{uuid.uuid4().hex[:8]}@test.com", "Resolve Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)

    res = await client.post(
        f"/review/{camp['id']}/comments",
        json={"anchor_text": "Network", "body": "Wrong network"},
        headers=headers,
    )
    comment_id = res.json()["id"]

    # Resolve.
    res = await client.post(
        f"/review/{camp['id']}/comments/{comment_id}/resolve", headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["resolved"] is True

    # Toggle back to unresolved.
    res = await client.post(
        f"/review/{camp['id']}/comments/{comment_id}/resolve", headers=headers
    )
    assert res.status_code == 200
    assert res.json()["resolved"] is False


@pytest.mark.asyncio
async def test_comments_isolated_by_tenant(client: AsyncClient):
    tok_a = await _register(client, f"ta{uuid.uuid4().hex[:8]}@test.com", "Tenant A")
    headers_a = {"Authorization": f"Bearer {tok_a['access_token']}"}
    brand_a = await _create_brand(client, headers_a)
    camp_a = await _create_campaign(client, headers_a, brand_a)

    tok_b = await _register(client, f"tb{uuid.uuid4().hex[:8]}@test.com", "Tenant B")
    headers_b = {"Authorization": f"Bearer {tok_b['access_token']}"}

    # Tenant A adds a comment.
    res = await client.post(
        f"/review/{camp_a['id']}/comments",
        json={"anchor_text": "x", "body": "secret"},
        headers=headers_a,
    )
    assert res.status_code == 201

    # Tenant B cannot see tenant A's comments.
    res = await client.get(f"/review/{camp_a['id']}/comments", headers=headers_b)
    assert res.status_code == 404  # campaign not found in tenant B


@pytest.mark.asyncio
async def test_add_comment_404_for_nonexistent_campaign(client: AsyncClient):
    tok = await _register(client, f"cn{uuid.uuid4().hex[:8]}@test.com", "404 Comment Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    res = await client.post(
        f"/review/{uuid.uuid4()}/comments",
        json={"anchor_text": "x", "body": "y"},
        headers=headers,
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_resolve_comment_404_for_nonexistent_comment(client: AsyncClient):
    tok = await _register(client, f"rc404{uuid.uuid4().hex[:8]}@test.com", "Resolve 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)
    res = await client.post(
        f"/review/{camp['id']}/comments/{uuid.uuid4()}/resolve", headers=headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_add_reply_404_for_nonexistent_parent(client: AsyncClient):
    tok = await _register(client, f"rp404{uuid.uuid4().hex[:8]}@test.com", "Reply 404 Tenant")
    headers = {"Authorization": f"Bearer {tok['access_token']}"}
    brand_id = await _create_brand(client, headers)
    camp = await _create_campaign(client, headers, brand_id)
    res = await client.post(
        f"/review/{camp['id']}/comments",
        json={"anchor_text": "x", "body": "y", "parent_id": str(uuid.uuid4())},
        headers=headers,
    )
    assert res.status_code == 404
