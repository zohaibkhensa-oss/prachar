from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prachar_shared.adapters.ads.audience_translation import (
    google_geo_target,
    translate_taxonomy,
)
from prachar_shared.adapters.ads.google_ads import GoogleAdsAdapter
from prachar_shared.adapters.ads.meta_ads import MetaAdsAdapter
from prachar_shared.contracts import (
    AudienceSpec,
    CreativeAsset,
    CreativeType,
    Gender,
    NativeTargeting,
    PolicyResult,
    TokenSet,
)


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


def test_google_ads_network_name() -> None:
    assert GoogleAdsAdapter().network == "google_ads"


def test_meta_ads_network_name() -> None:
    assert MetaAdsAdapter().network == "meta_ads"


def test_google_translate_audience_returns_native_targeting() -> None:
    result = GoogleAdsAdapter().translate_audience(_spec())
    assert isinstance(result, NativeTargeting)
    assert result.network == "google_ads"
    assert result.payload, "payload must be non-empty"
    assert "geo_targets" in result.payload
    assert "in_market_audiences" in result.payload
    assert "keywords" in result.payload
    assert len(result.payload["geo_targets"]) == 2
    assert result.payload["in_market_audiences"], "in-market mapping must be non-empty"


def test_meta_translate_audience_returns_native_targeting() -> None:
    result = MetaAdsAdapter().translate_audience(_spec())
    assert isinstance(result, NativeTargeting)
    assert result.network == "meta_ads"
    assert result.payload, "payload must be non-empty"
    assert "targeting" in result.payload
    assert result.payload["targeting"]["interests"], "interests mapping must be non-empty"


def test_google_policy_precheck_blocks_guarantees() -> None:
    creative = CreativeAsset(
        type=CreativeType.copy,
        locale="en-US",
        channel="google_ads",
        variant_group="v1",
        payload={"text": "guaranteed #1 results for your business"},
    )
    result = GoogleAdsAdapter().policy_precheck(creative)
    assert isinstance(result, PolicyResult)
    assert result.passed is False
    assert any("guarantee" in r for r in result.blocked_reasons)


def test_meta_policy_precheck_blocks_guarantees() -> None:
    creative = CreativeAsset(
        type=CreativeType.copy,
        locale="en-US",
        channel="meta_ads",
        variant_group="v1",
        payload={"primary_text": "100% guaranteed returns on ad spend"},
    )
    result = MetaAdsAdapter().policy_precheck(creative)
    assert result.passed is False


def test_google_geo_target_returns_int() -> None:
    val = google_geo_target("US")
    assert isinstance(val, int)
    assert val == 2840


def test_google_geo_target_unmapped_defaults_to_us() -> None:
    val = google_geo_target("ZZ")
    assert isinstance(val, int)
    assert val == 2840


def test_translate_taxonomy_returns_list_of_strings() -> None:
    import asyncio

    out = asyncio.run(translate_taxonomy(["fintech", "trading"], "interests", "google_ads"))
    assert isinstance(out, list)
    assert len(out) == 2
    for item in out:
        assert isinstance(item, str)
        assert item, "mapped item must be non-empty"


def test_google_create_campaign_returns_id() -> None:
    cid = GoogleAdsAdapter().create_campaign(_stub_tokens(), {"objective": "traffic"})
    assert isinstance(cid, str)
    assert cid.startswith("gads-")


def test_meta_create_campaign_returns_id() -> None:
    cid = MetaAdsAdapter().create_campaign(_stub_tokens(), {"objective": "conversions"})
    assert isinstance(cid, str)
    assert cid.startswith("meta-")


def test_google_stats_returns_metric_events() -> None:
    events = GoogleAdsAdapter().stats(
        _stub_tokens(), "gads-abc", datetime.now(UTC) - timedelta(days=3)
    )
    assert events
    metrics = {e.metric for e in events}
    assert {"impressions", "clicks", "cost", "conversions"} <= metrics
    for e in events:
        assert e.channel == "google_ads"


def test_google_set_budget_bid_and_pause_are_noops() -> None:
    adapter = GoogleAdsAdapter()
    adapter.set_budget_bid(_stub_tokens(), "gads-1", 100.0, {"type": "TARGET_CPA"})
    adapter.pause(_stub_tokens(), "gads-1")  # should not raise


def test_registry_has_google_and_meta() -> None:
    from prachar_shared.adapters.ads import google_ads as _ga  # noqa: F401  (registers)
    from prachar_shared.adapters.ads import meta_ads as _ma  # noqa: F401  (registers)
    from prachar_shared.adapters.registry import get_ads

    assert get_ads("google_ads").network == "google_ads"
    assert get_ads("meta_ads").network == "meta_ads"
