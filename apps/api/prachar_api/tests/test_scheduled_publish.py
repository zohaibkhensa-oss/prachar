"""Scheduled-publish regression tests — payload builder moved to shared,
API validation rules, and worker publish-flow contract."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://prachar:prachar@localhost:5432/prachar")
os.environ.setdefault("JWT_SECRET", "test-secret-jwt-xxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("TOKEN_ENC_KEY", "a" * 64)

from prachar_shared.publishing import (  # noqa: E402
    build_channel_payload,
    refresh_if_expiring,
    tokens_from_bundle,
)


class TestChannelPayloadBuilder:
    """The worker and API must produce identical adapter payloads."""

    def test_youtube_requires_video(self):
        with pytest.raises(ValueError, match="video"):
            build_channel_payload("youtube", "cap", None, "image", None, {})
        with pytest.raises(ValueError, match="video"):
            build_channel_payload("youtube", "cap", "https://v", "image", None, {})

    def test_youtube_video_payload(self):
        p = build_channel_payload("youtube", "My caption", "https://v.mp4", "video", None, {})
        assert p["video_url"] == "https://v.mp4"
        assert p["title"] == "My caption"[:100]
        assert p["privacy"] == "public"

    def test_instagram_requires_media(self):
        with pytest.raises(ValueError):
            build_channel_payload("instagram", "cap", None, "image", None, {})

    def test_instagram_reel_vs_feed(self):
        p = build_channel_payload("instagram", "cap", "https://i", "video", None, {})
        assert p["post_type"] == "reels"
        p = build_channel_payload("instagram", "cap", "https://i", "image", None, {})
        assert p["post_type"] == "feed"

    def test_linkedin_uses_member_urn(self):
        p = build_channel_payload("linkedin", "t", None, "image", None, {"member_id": "abc"})
        assert p["_author_urn"] == "urn:li:person:abc"

    def test_telegram_requires_chat_id(self):
        with pytest.raises(ValueError):
            build_channel_payload("telegram", "t", None, "image", None, {})

    def test_facebook_page_token_metadata(self):
        p = build_channel_payload(
            "facebook", "hi", "https://i", "image", None,
            {"page_access_token": "pt", "page_id": "pg"},
        )
        assert p["_page_access_token"] == "pt" and p["picture"] == "https://i"

    def test_unsupported_channel(self):
        with pytest.raises(ValueError, match="not supported"):
            build_channel_payload("snapchat", "t", None, "image", None, {})


class TestRefreshContract:
    def test_fresh_token_unchanged(self):
        bundle = {
            "access_token": "a",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
        out, changed = refresh_if_expiring(MagicMock(), bundle)
        assert not changed and out["access_token"] == "a"

    def test_expired_with_refresh(self):
        new_tokens = MagicMock(
            access_token="new", refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(hours=1), scopes=["s"],
        )
        adapter = MagicMock()
        adapter.refresh_access_token.return_value = new_tokens
        bundle = {
            "access_token": "old", "refresh_token": "rt",
            "expires_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        }
        out, changed = refresh_if_expiring(adapter, bundle)
        assert changed and out["access_token"] == "new"

    def test_expired_no_refresh_raises_reauth(self):
        bundle = {
            "access_token": "old",
            "expires_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        }
        with pytest.raises(PermissionError, match="REAUTH_REQUIRED"):
            refresh_if_expiring(MagicMock(spec=[]), bundle)

    def test_failed_refresh_raises_reauth(self):
        adapter = MagicMock()
        adapter.refresh_access_token.side_effect = RuntimeError("401")
        bundle = {
            "access_token": "old", "refresh_token": "rt",
            "expires_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        }
        with pytest.raises(PermissionError, match="REAUTH_REQUIRED"):
            refresh_if_expiring(adapter, bundle)


class TestTokensFromBundle:
    def test_builds_tokenset(self):
        bundle = {
            "access_token": "a", "refresh_token": "r",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "scopes": ["s"], "metadata": {"m": 1},
        }
        t = tokens_from_bundle(bundle)
        assert t.access_token == "a" and t.metadata == {"m": 1}


class TestAutopilotHelpers:
    def test_autopilot_state_defaults(self):
        from prachar_api.routers.brands import _autopilot_state

        brand = MagicMock(brand_graph={}, next_loop_at=None)
        st = _autopilot_state(brand, ["facebook", "linkedin"], 3)
        assert st["enabled"] is False
        assert st["mode"] == "approve_first"
        assert st["posts_per_week"] == 5
        assert st["channels"] == ["facebook", "linkedin"]
        assert st["queued_count"] == 3

    def test_autopilot_state_respects_custom_config(self):
        from prachar_api.routers.brands import _autopilot_state

        now = datetime.now(UTC) + timedelta(days=7)
        brand = MagicMock(
            brand_graph={
                "autopilot": {
                    "enabled": True,
                    "mode": "full_auto",
                    "posts_per_week": 7,
                    "channels": ["x"],
                    "pillars": ["Wins"],
                }
            },
            next_loop_at=now,
        )
        st = _autopilot_state(brand, ["x", "linkedin"], 5)
        assert st["enabled"] is True
        assert st["mode"] == "full_auto"
        assert st["posts_per_week"] == 7
        assert st["channels"] == ["x"]
        assert st["pillars"] == ["Wins"]

    def test_fallback_post_copy_respects_x_limit(self):
        from prachar_api.routers.brands import _fallback_post_copy

        brand = MagicMock()
        brand.name = "CURV AI"
        brand.category = "A" * 300
        brand.tone = {"voice": "bold"}
        copy = _fallback_post_copy(brand, "x", "Insights", 0, None)
        assert len(copy) <= 280

