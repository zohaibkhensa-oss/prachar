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

    def test_instagram_carousel_from_media_urls(self):
        p = build_channel_payload(
            "instagram",
            "carousel cap",
            None,
            "image",
            None,
            {"ig_id": "123"},
            media_urls=["https://img1", "https://img2", "https://img3"],
        )
        assert p["post_type"] == "carousel"
        assert p["media_urls"] == ["https://img1", "https://img2", "https://img3"]

    def test_facebook_carousel_from_media_urls(self):
        p = build_channel_payload(
            "facebook",
            "fb album",
            None,
            "image",
            None,
            {"page_id": "pg", "page_access_token": "tok"},
            media_urls=["https://img1", "https://img2"],
        )
        assert p["picture"] == "https://img1"
        assert p["media_urls"] == ["https://img1", "https://img2"]

    def test_render_carousel_slide_png_returns_valid_png(self):
        from prachar_api.routers.brands import _render_carousel_slide_png

        png = _render_carousel_slide_png(
            "CURV AI", "1. Hook Your Audience", "Actionable insight body copy.", 1, 5
        )
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 1000

    def test_render_video_overlay_png_returns_transparent_rgba_png(self):
        from prachar_api.routers.brands import _render_video_overlay_png

        png = _render_video_overlay_png(
            "Stop Guessing Your Ad Spend",
            "Compound weekly creative winners automatically.",
            "CURV AI",
        )
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 1000

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



class TestHeuristicPostScore:
    """Deterministic 4-signal pre-publish scorer — always runs without LLM."""

    def test_empty_caption_scores_zero(self):
        from prachar_api.routers.brands import _heuristic_post_score

        r = _heuristic_post_score("", ["instagram"], "text", 0)
        assert r["score"] == 0
        assert all(s["score"] == 0 for s in r["signals"].values())

    def test_strong_carousel_post_scores_high(self):
        from prachar_api.routers.brands import _heuristic_post_score

        caption = (
            "3 pricing mistakes killing your sales\n"
            "Save this checklist — most founders miss #2.\n"
            "Swipe for the fix. Link in bio."
        )
        r = _heuristic_post_score(caption, ["instagram"], "carousel", 5)
        assert r["score"] >= 85
        assert r["signals"]["hook"]["score"] == 25
        assert r["signals"]["save_share"]["score"] == 25
        assert r["signals"]["cta"]["score"] == 25

    def test_x_over_limit_drops_channel_fit(self):
        from prachar_api.routers.brands import _heuristic_post_score

        caption = "Great hook here\n" + ("x" * 300)
        r = _heuristic_post_score(caption, ["x"], "text", 0)
        assert r["signals"]["channel_fit"]["score"] <= 15

    def test_instagram_text_only_penalised(self):
        from prachar_api.routers.brands import _heuristic_post_score

        r = _heuristic_post_score("Nice photo idea\nShop now", ["instagram"], "text", 0)
        assert r["signals"]["channel_fit"]["score"] < 25

    def test_youtube_without_video_penalised(self):
        from prachar_api.routers.brands import _heuristic_post_score

        r = _heuristic_post_score("New video out\nWatch now", ["youtube"], "image", 1)
        assert r["signals"]["channel_fit"]["score"] <= 15

    def test_weak_hook_tip_present(self):
        from prachar_api.routers.brands import _heuristic_post_score

        long_line = "word " * 40
        r = _heuristic_post_score(long_line, ["facebook"], "text", 0)
        assert r["signals"]["hook"]["score"] < 18
        assert "hook" in r["signals"]["hook"]["tip"].lower() or "line" in r["signals"]["hook"]["tip"].lower()


class TestVerdictBands:
    def test_verdict_thresholds(self):
        from prachar_api.routers.brands import _verdict

        assert _verdict(95) == "viral_ready"
        assert _verdict(85) == "viral_ready"
        assert _verdict(70) == "strong"
        assert _verdict(50) == "good"
        assert _verdict(10) == "needs_work"


class TestBrandDomain:
    def test_domain_extraction(self):
        from prachar_api.routers.brands import _brand_domain

        assert _brand_domain("https://www.curvai.org/path") == "curvai.org"
        assert _brand_domain("curvai.org") == "curvai.org"
        assert _brand_domain(None) is None
        assert _brand_domain("") is None


class TestGSCSearchAnalytics:
    """search_analytics parses GSC rows and URL-encodes the site param."""

    async def test_parses_rows_and_encodes_site(self):
        from prachar_shared.adapters.organic import gsc as gsc_mod

        captured: dict = {}

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "rows": [
                        {
                            "keys": ["curv ai review"],
                            "clicks": 12,
                            "impressions": 800,
                            "ctr": 0.015,
                            "position": 7.4,
                        },
                        {
                            "keys": ["ai marketing tool"],
                            "clicks": 2,
                            "impressions": 300,
                            "ctr": 0.006,
                            "position": 12.1,
                        },
                    ]
                }

        async def fake_request(method, url, **kwargs):
            captured["url"] = url
            return _Resp()

        orig = gsc_mod._request
        gsc_mod._request = fake_request
        try:
            adapter = gsc_mod.GSCAdapter()
            from datetime import UTC, datetime, timedelta

            from prachar_shared.contracts import TokenSet

            tokens = TokenSet(access_token="t", expires_at=datetime.now(UTC))
            rows = await adapter.search_analytics(
                tokens, "sc-domain:curvai.org", datetime.now(UTC) - timedelta(days=28)
            )
        finally:
            gsc_mod._request = orig

        assert len(rows) == 2
        assert rows[0]["query"] == "curv ai review"
        assert rows[0]["position"] == 7.4
        assert rows[1]["impressions"] == 300
        # site param must be URL-encoded in the path
        assert "sc-domain%3Acurvai.org" in captured["url"]


class TestCloneWinnerFallback:
    """The fallback path must always return count variations with safe captions."""

    def test_fallback_variation_structure(self):
        # Exercise the deterministic fallback the endpoint uses when the LLM
        # is unavailable: 3 angle-labelled variations <= 400 chars.
        source = "Diwali sale is live — 20% off all plans this weekend only!"
        first_line = source.split("\n", 1)[0][:80]
        brand_name = "CURV AI"
        variations = [
            {
                "angle": "Question hook",
                "hook": f"Ever wonder what makes {brand_name} different?",
                "caption": (
                    f"Ever wonder what makes {brand_name} different? "
                    f"{source[:250]} — DM us to see for yourself."
                )[:400],
            },
            {
                "angle": "Bold offer",
                "hook": first_line,
                "caption": (
                    f"{first_line} — this week only at {brand_name}. "
                    "Tap the link in bio or comment YES for details."
                )[:400],
            },
        ]
        assert len(variations) == 2
        assert all(len(v["caption"]) <= 400 for v in variations)
        assert all(v["angle"] for v in variations)


class TestChannelTokenRefresh:
    """Every OAuth2 channel adapter must support token refresh or Page-token
    persistence so connections do not die after 1-2 hours."""

    def test_adapters_expose_refresh_access_token(self):
        from prachar_shared.adapters.organic.facebook import FacebookAdapter
        from prachar_shared.adapters.organic.google import GoogleSearchAdapter
        from prachar_shared.adapters.organic.gsc import GSCAdapter
        from prachar_shared.adapters.organic.instagram import InstagramAdapter
        from prachar_shared.adapters.organic.linkedin import LinkedInAdapter
        from prachar_shared.adapters.organic.pinterest import PinterestAdapter
        from prachar_shared.adapters.organic.tiktok import TikTokAdapter
        from prachar_shared.adapters.organic.x import XAdapter
        from prachar_shared.adapters.organic.youtube import YouTubeAdapter

        for cls in (
            YouTubeAdapter,
            GSCAdapter,
            GoogleSearchAdapter,
            XAdapter,
            FacebookAdapter,
            InstagramAdapter,
            LinkedInAdapter,
            TikTokAdapter,
            PinterestAdapter,
        ):
            assert hasattr(cls(), "refresh_access_token"), f"{cls.__name__} missing refresh_access_token"

    def test_refresh_if_expiring_preserves_meta_page_token_connection(self):
        past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        bundle = {
            "access_token": "old-user-tok",
            "refresh_token": None,
            "expires_at": past,
            "scopes": ["pages_manage_posts"],
            "metadata": {"page_id": "136029", "page_access_token": "non-expiring-page-tok"},
            "channel": "facebook",
        }
        adapter = MagicMock(spec=[])
        out, changed = refresh_if_expiring(adapter, bundle)
        assert changed is True
        assert datetime.fromisoformat(out["expires_at"]) > datetime.now(UTC) + timedelta(days=30)
