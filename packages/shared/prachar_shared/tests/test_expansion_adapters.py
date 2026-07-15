from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prachar_shared.adapters.ads.linkedin_ads import LinkedInAdsAdapter
from prachar_shared.adapters.ads.pinterest_ads import PinterestAdsAdapter
from prachar_shared.adapters.ads.tiktok_ads import TikTokAdsAdapter
from prachar_shared.adapters.ads.x_ads import XAdsAdapter
from prachar_shared.adapters.organic.linkedin import LinkedInAdapter
from prachar_shared.adapters.organic.pinterest import PinterestAdapter
from prachar_shared.adapters.organic.tiktok import TikTokAdapter
from prachar_shared.adapters.organic.x import XAdapter
from prachar_shared.contracts import (
    AudienceSpec,
    CreativeAsset,
    CreativeType,
    Gender,
    NativeTargeting,
    PolicyResult,
    TokenSet,
)

# ---- fixtures ----


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from prachar_shared.config import get_settings

    get_settings.cache_clear()


def _stub_tokens() -> TokenSet:
    return TokenSet(access_token="stub", expires_at=datetime.now(UTC) + timedelta(hours=1))


def _spec() -> AudienceSpec:
    return AudienceSpec(
        geo=["US-CA", "IN-MH"],
        age=(25, 45),
        gender=Gender.any,
        interests=["fintech", "trading"],
        intents=["buy trading software"],
        languages=["en"],
    )


def _guarantee_creative(channel: str) -> CreativeAsset:
    return CreativeAsset(
        type=CreativeType.copy,
        locale="en-US",
        channel=channel,
        variant_group="v1",
        payload={"text": "guaranteed #1 results for your business"},
    )


# ============================================================
# Organic adapters
# ============================================================

# ---- TikTok ----
def test_tiktok_channel_name() -> None:
    assert TikTokAdapter().channel == "tiktok"


def test_tiktok_schema_keys() -> None:
    schema = TikTokAdapter().generate_schema()
    props = schema["properties"]
    for key in (
        "caption",
        "hashtags",
        "video_url",
        "sound_id",
        "duet_enabled",
        "stitch_enabled",
        "comment_enabled",
        "schedule_at",
    ):
        assert key in props
    assert props["caption"]["maxLength"] == 2200


def test_tiktok_policy_gate_long_caption_blocked() -> None:
    result = TikTokAdapter().policy_gate({"caption": "A" * 2201, "video_url": "u"})
    assert not result.passed
    assert any("2200" in r for r in result.blocked_reasons)


def test_tiktok_policy_gate_valid_passes() -> None:
    result = TikTokAdapter().policy_gate(
        {"caption": "Great content about fintech", "hashtags": ["#fintech"], "video_url": "u"}
    )
    assert result.passed


def test_tiktok_auth_url_contains_domain_and_state() -> None:
    url = TikTokAdapter().auth_url("tt-state-xyz")
    assert "tiktok.com" in url
    assert "tt-state-xyz" in url


# ---- LinkedIn ----
def test_linkedin_channel_name() -> None:
    assert LinkedInAdapter().channel == "linkedin"


def test_linkedin_schema_keys() -> None:
    schema = LinkedInAdapter().generate_schema()
    props = schema["properties"]
    for key in (
        "text",
        "visibility",
        "media_category",
        "media_url",
        "article_url",
        "article_title",
        "article_description",
    ):
        assert key in props
    assert props["text"]["maxLength"] == 3000
    assert props["visibility"]["enum"] == ["public", "connections"]


def test_linkedin_policy_gate_long_text_blocked() -> None:
    result = LinkedInAdapter().policy_gate({"text": "A" * 3001, "visibility": "public"})
    assert not result.passed
    assert any("3000" in r for r in result.blocked_reasons)


def test_linkedin_policy_gate_valid_passes() -> None:
    result = LinkedInAdapter().policy_gate(
        {"text": "Professional update about our latest product launch.", "visibility": "public"}
    )
    assert result.passed


def test_linkedin_auth_url_contains_domain_and_state() -> None:
    url = LinkedInAdapter().auth_url("li-state-abc")
    assert "linkedin.com" in url
    assert "li-state-abc" in url


# ---- Pinterest ----
def test_pinterest_channel_name() -> None:
    assert PinterestAdapter().channel == "pinterest"


def test_pinterest_schema_keys() -> None:
    schema = PinterestAdapter().generate_schema()
    props = schema["properties"]
    for key in ("title", "description", "board", "link", "alt_text", "image_url"):
        assert key in props
    assert props["title"]["maxLength"] == 100
    assert props["description"]["maxLength"] == 500


def test_pinterest_policy_gate_long_title_blocked() -> None:
    result = PinterestAdapter().policy_gate(
        {"title": "A" * 101, "description": "ok", "board": "b", "image_url": "u"}
    )
    assert not result.passed
    assert any("title" in r and "100" in r for r in result.blocked_reasons)


def test_pinterest_policy_gate_valid_passes() -> None:
    result = PinterestAdapter().policy_gate(
        {"title": "My Pin", "description": "A nice pin", "board": "b", "image_url": "u"}
    )
    assert result.passed


def test_pinterest_auth_url_contains_domain_and_state() -> None:
    url = PinterestAdapter().auth_url("pin-state-123")
    assert "pinterest.com" in url
    assert "pin-state-123" in url


# ---- X (Twitter) ----
def test_x_channel_name() -> None:
    assert XAdapter().channel == "x"


def test_x_schema_keys() -> None:
    schema = XAdapter().generate_schema()
    props = schema["properties"]
    for key in ("text", "media_ids", "reply_to_id", "quote_tweet_id", "poll"):
        assert key in props
    assert props["text"]["maxLength"] == 280
    assert "options" in props["poll"]["properties"]
    assert "duration_minutes" in props["poll"]["properties"]


def test_x_policy_gate_long_text_blocked() -> None:
    result = XAdapter().policy_gate({"text": "A" * 281})
    assert not result.passed
    assert any("280" in r for r in result.blocked_reasons)


def test_x_policy_gate_valid_passes() -> None:
    result = XAdapter().policy_gate({"text": "Just shipped a new feature!"})
    assert result.passed


def test_x_auth_url_contains_domain_and_state() -> None:
    url = XAdapter().auth_url("x-state-456")
    assert "twitter.com" in url
    assert "x-state-456" in url


# ============================================================
# Ads adapters
# ============================================================

# ---- TikTok Ads ----
def test_tiktok_ads_network_name() -> None:
    assert TikTokAdsAdapter().network == "tiktok_ads"


def test_tiktok_ads_translate_audience_returns_native_targeting() -> None:
    result = TikTokAdsAdapter().translate_audience(_spec())
    assert isinstance(result, NativeTargeting)
    assert result.network == "tiktok_ads"
    assert result.payload, "payload must be non-empty"
    assert "location" in result.payload
    assert "interests" in result.payload
    assert "hashtag_audiences" in result.payload
    assert len(result.payload["location"]) == 2
    assert result.payload["interests"], "interests mapping must be non-empty"


def test_tiktok_ads_policy_precheck_blocks_guarantees() -> None:
    result = TikTokAdsAdapter().policy_precheck(_guarantee_creative("tiktok_ads"))
    assert isinstance(result, PolicyResult)
    assert result.passed is False
    assert any("guarantee" in r for r in result.blocked_reasons)


# ---- LinkedIn Ads ----
def test_linkedin_ads_network_name() -> None:
    assert LinkedInAdsAdapter().network == "linkedin_ads"


def test_linkedin_ads_translate_audience_returns_native_targeting() -> None:
    result = LinkedInAdsAdapter().translate_audience(_spec())
    assert isinstance(result, NativeTargeting)
    assert result.network == "linkedin_ads"
    assert result.payload, "payload must be non-empty"
    assert "locations" in result.payload
    assert "job_titles" in result.payload
    assert "skills" in result.payload
    assert "company_sizes" in result.payload
    assert result.payload["job_titles"], "job titles mapping must be non-empty"


def test_linkedin_ads_policy_precheck_blocks_guarantees() -> None:
    result = LinkedInAdsAdapter().policy_precheck(_guarantee_creative("linkedin_ads"))
    assert isinstance(result, PolicyResult)
    assert result.passed is False
    assert any("guarantee" in r for r in result.blocked_reasons)


# ---- Pinterest Ads ----
def test_pinterest_ads_network_name() -> None:
    assert PinterestAdsAdapter().network == "pinterest_ads"


def test_pinterest_ads_translate_audience_returns_native_targeting() -> None:
    result = PinterestAdsAdapter().translate_audience(_spec())
    assert isinstance(result, NativeTargeting)
    assert result.network == "pinterest_ads"
    assert result.payload, "payload must be non-empty"
    assert "geo" in result.payload
    assert "interest_categories" in result.payload
    assert "act_audiences" in result.payload
    assert result.payload["interest_categories"], "interest categories mapping must be non-empty"


def test_pinterest_ads_policy_precheck_blocks_guarantees() -> None:
    result = PinterestAdsAdapter().policy_precheck(_guarantee_creative("pinterest_ads"))
    assert isinstance(result, PolicyResult)
    assert result.passed is False
    assert any("guarantee" in r for r in result.blocked_reasons)


# ---- X Ads ----
def test_x_ads_network_name() -> None:
    assert XAdsAdapter().network == "x_ads"


def test_x_ads_translate_audience_returns_native_targeting() -> None:
    result = XAdsAdapter().translate_audience(_spec())
    assert isinstance(result, NativeTargeting)
    assert result.network == "x_ads"
    assert result.payload, "payload must be non-empty"
    assert "location" in result.payload
    assert "conversation_topics" in result.payload
    assert "followers_targeting" in result.payload
    assert result.payload["conversation_topics"], "conversation topics mapping must be non-empty"


def test_x_ads_policy_precheck_blocks_guarantees() -> None:
    result = XAdsAdapter().policy_precheck(_guarantee_creative("x_ads"))
    assert isinstance(result, PolicyResult)
    assert result.passed is False
    assert any("guarantee" in r for r in result.blocked_reasons)


# ============================================================
# Registry integration
# ============================================================
def test_registry_has_all_expansion_adapters() -> None:
    from prachar_shared.adapters.organic import linkedin as _li  # noqa: F401
    from prachar_shared.adapters.organic import pinterest as _pin  # noqa: F401
    from prachar_shared.adapters.organic import tiktok as _tt  # noqa: F401
    from prachar_shared.adapters.organic import x as _x  # noqa: F401
    from prachar_shared.adapters.ads import linkedin_ads as _liads  # noqa: F401
    from prachar_shared.adapters.ads import pinterest_ads as _pinads  # noqa: F401
    from prachar_shared.adapters.ads import tiktok_ads as _ttads  # noqa: F401
    from prachar_shared.adapters.ads import x_ads as _xads  # noqa: F401
    from prachar_shared.adapters.registry import get_ads, get_organic

    assert get_organic("tiktok").channel == "tiktok"
    assert get_organic("linkedin").channel == "linkedin"
    assert get_organic("pinterest").channel == "pinterest"
    assert get_organic("x").channel == "x"
    assert get_ads("tiktok_ads").network == "tiktok_ads"
    assert get_ads("linkedin_ads").network == "linkedin_ads"
    assert get_ads("pinterest_ads").network == "pinterest_ads"
    assert get_ads("x_ads").network == "x_ads"
