"""Tests for performance ingestion (PRACHAR Phase C.1.1 – C.1.6).

Covers:
* ``ingest_gbp_metrics`` — pulls live GBP insights and maps them to
  CampaignPerformance rows; graceful skip when GBP is not connected.
* ``ingest_meta_metrics`` — pulls live Meta (Facebook + Instagram organic and
  Meta ads) metrics and maps them to CampaignPerformance rows; graceful skip
  when Meta is not connected.
* ``ingest_linkedin_metrics`` — pulls LinkedIn organic share statistics
  (impressions, clicks, likes, comments); graceful skip when not connected.
* ``ingest_whatsapp_metrics`` — pulls WhatsApp Business message insights
  (delivered, read); graceful skip when not connected.
* ``ingest_google_ads_metrics`` — pulls Google Ads performance (impressions,
  clicks, conversions, spend); graceful skip when not connected.
* ``ingest_youtube_metrics`` — pulls YouTube Analytics (views, impressions,
  watch time); graceful skip when not connected.

Adapters are mocked so no network / OAuth calls are made.

Run with:
    .venv/bin/python -m pytest apps/workers/prachar_workers/tests/test_performance_ingestion.py -q
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from prachar_workers.performance import (
    GBP_METRIC_MAP,
    LINKEDIN_METRIC_MAP,
    META_ORGANIC_METRIC_MAP,
    WHATSAPP_METRIC_MAP,
    YOUTUBE_METRIC_MAP,
    PerformanceStore,
    aggregate_events,
    ingest_google_ads_metrics,
    ingest_gbp_metrics,
    ingest_linkedin_metrics,
    ingest_meta_metrics,
    ingest_whatsapp_metrics,
    ingest_youtube_metrics,
    pull_for_campaign,
    run_pull,
)


# ─── Fakes (mirror test_performance.py) ────────────────────────────────────────


class FakeStore(PerformanceStore):
    """In-memory store mirroring the ORM upsert semantics without a DB."""

    def __init__(self) -> None:
        self.rows: dict[tuple[Any, date, str], Any] = {}
        self.added: list[Any] = []

    def find(self, campaign_id: Any, target_date: date, channel: str) -> Any | None:
        return self.rows.get((campaign_id, target_date, channel))

    def add(self, perf: Any) -> None:
        self.added.append(perf)
        self.rows[(perf.campaign_id, perf.date, perf.channel)] = perf

    def flush(self) -> None:  # no-op
        pass


def _campaign(network: str = "gmb", ncid: str | None = "loc-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        brand_id=uuid.uuid4(),
        network=network,
        network_campaign_id=ncid,
    )


def _conn(channel: str = "gmb") -> SimpleNamespace:
    return SimpleNamespace(channel=channel)


def _ev(metric: str, value: float, day: date, channel: str = "gmb") -> dict[str, Any]:
    return {
        "channel": channel,
        "entity_type": "location",
        "entity_id": "loc-1",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


# ─── Fake adapters ────────────────────────────────────────────────────────────


class FakeGBPAdapter:
    """Sync organic adapter exposing ``metrics``."""

    def __init__(self, events: list[Any], raise_on_metrics: bool = False) -> None:
        self._events = events
        self._raise = raise_on_metrics
        self.calls: list[tuple[Any, datetime]] = []

    def metrics(self, tokens: Any, since: datetime) -> list[Any]:
        self.calls.append((tokens, since))
        if self._raise:
            raise RuntimeError("gbp boom")
        return self._events


class FakeMetaAdsAdapter:
    """Ads adapter exposing ``stats``."""

    def __init__(self, events: list[Any], raise_on_stats: bool = False) -> None:
        self._events = events
        self._raise = raise_on_stats
        self.calls: list[tuple[str, str, datetime]] = []

    def stats(self, tokens: Any, campaign_id: str, since: datetime) -> list[Any]:
        self.calls.append((campaign_id, str(tokens), since))
        if self._raise:
            raise RuntimeError("meta ads boom")
        return self._events


class FakeMetaOrganicAdapter:
    """Organic adapter exposing an async ``metrics``."""

    def __init__(self, events: list[Any], raise_on_metrics: bool = False) -> None:
        self._events = events
        self._raise = raise_on_metrics
        self.calls: list[tuple[Any, datetime]] = []

    async def metrics(self, tokens: Any, since: datetime) -> list[Any]:
        self.calls.append((tokens, since))
        if self._raise:
            raise RuntimeError("meta organic boom")
        return self._events


# ─── Metric-map sanity ────────────────────────────────────────────────────────


def test_gbp_metric_map_buckets():
    assert GBP_METRIC_MAP["search_impressions"] == "impressions"
    assert GBP_METRIC_MAP["directions_requests"] == "clicks"
    assert GBP_METRIC_MAP["calls"] == "conversions"
    assert GBP_METRIC_MAP["photo_views"] == "revenue"


def test_meta_organic_metric_map_buckets():
    assert META_ORGANIC_METRIC_MAP["fb_page_impressions"] == "impressions"
    assert META_ORGANIC_METRIC_MAP["ig_impressions"] == "impressions"
    assert META_ORGANIC_METRIC_MAP["fb_page_post_engagements"] == "clicks"
    assert META_ORGANIC_METRIC_MAP["fb_page_fan_adds"] == "conversions"


def test_aggregate_events_with_custom_map():
    day = date(2026, 7, 25)
    events = [
        _ev("search_impressions", 500, day),
        _ev("directions_requests", 20, day),
        _ev("calls", 3, day),
        _ev("photo_views", 80, day),
        _ev("unknown", 999, day),  # ignored
        _ev("search_impressions", 1, date(2026, 7, 24)),  # wrong day
    ]
    agg = aggregate_events(events, day, GBP_METRIC_MAP)
    assert agg["impressions"] == 500
    assert agg["clicks"] == 20
    assert agg["conversions"] == 3
    assert agg["revenue"] == 80
    assert agg["spend"] == 0


# ─── ingest_gbp_metrics ───────────────────────────────────────────────────────


def test_ingest_gbp_metrics_pulls_and_maps_data():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="gmb", ncid="loc-1")
    events = [
        _ev("search_impressions", 1200, day),
        _ev("directions_requests", 45, day),
        _ev("calls", 7, day),
        _ev("photo_views", 300, day),
    ]
    adapter = FakeGBPAdapter(events)
    result = ingest_gbp_metrics(
        store, camp, _conn("gmb"), day, adapter=adapter
    )
    assert result["channel"] == "gmb"
    assert result["status"] == "ok"
    assert result["impressions"] == 1200
    assert result["clicks"] == 45
    assert result["conversions"] == 7
    assert result["revenue"] == 300
    assert result["spend"] == 0
    # Row upserted with channel "gmb".
    row = store.rows[(camp.id, day, "gmb")]
    assert row.impressions == 1200
    assert row.clicks == 45
    assert row.conversions == 7
    assert float(row.revenue) == 300.0
    assert float(row.spend) == 0.0
    # Derived ctr computed from mapped clicks/impressions.
    assert row.ctr == pytest.approx(45 / 1200)
    # Adapter was invoked once.
    assert len(adapter.calls) == 1


def test_ingest_gbp_metrics_graceful_skip_when_not_connected():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="gmb", ncid="loc-1")
    adapter = FakeGBPAdapter([])
    result = ingest_gbp_metrics(store, camp, None, day, adapter=adapter)
    assert result["channel"] == "gmb"
    assert result["status"] == "skipped"
    assert result["reason"] == "not_connected"
    # Adapter never called, nothing upserted.
    assert adapter.calls == []
    assert store.added == []


def test_ingest_gbp_metrics_isolates_adapter_error():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="gmb", ncid="loc-1")
    adapter = FakeGBPAdapter([], raise_on_metrics=True)
    result = ingest_gbp_metrics(store, camp, _conn("gmb"), day, adapter=adapter)
    assert result["status"] == "error"
    assert "gbp boom" in result["error"]
    assert store.added == []


# ─── ingest_meta_metrics ──────────────────────────────────────────────────────


def _meta_ads_ev(metric: str, value: float, day: date) -> dict[str, Any]:
    return {
        "channel": "meta_ads",
        "entity_type": "campaign",
        "entity_id": "meta-1",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


def test_ingest_meta_metrics_pulls_ads_data_and_maps():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    events = [
        _meta_ads_ev("impressions", 5000, day),
        _meta_ads_ev("clicks", 180, day),
        _meta_ads_ev("cost", 42.5, day),
        _meta_ads_ev("conversions", 9, day),
    ]
    ads_adapter = FakeMetaAdsAdapter(events)
    result = ingest_meta_metrics(
        store, camp, _conn("meta_ads"), day,
        ads_adapter_factory=lambda _n: ads_adapter,
    )
    assert result["channel"] == "meta_ads"
    assert result["status"] == "ok"
    assert result["impressions"] == 5000
    assert result["clicks"] == 180
    assert result["conversions"] == 9
    assert result["spend"] == 42.5
    row = store.rows[(camp.id, day, "meta_ads")]
    assert row.impressions == 5000
    assert float(row.spend) == 42.5
    assert ads_adapter.calls[0][0] == "meta-1"


def test_ingest_meta_metrics_ads_skips_without_network_campaign_id():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid=None)
    ads_adapter = FakeMetaAdsAdapter([])
    result = ingest_meta_metrics(
        store, camp, _conn("meta_ads"), day,
        ads_adapter_factory=lambda _n: ads_adapter,
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "no_network_campaign_id"
    assert ads_adapter.calls == []
    assert store.added == []


def test_ingest_meta_metrics_pulls_facebook_organic_and_maps():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    events = [
        _ev("fb_page_impressions", 3200, day, channel="facebook"),
        _ev("fb_page_post_engagements", 210, day, channel="facebook"),
        _ev("fb_page_fan_adds", 12, day, channel="facebook"),
    ]
    fb_adapter = FakeMetaOrganicAdapter(events)
    result = ingest_meta_metrics(
        store, camp, _conn("facebook"), day,
        organic_adapter_factory=lambda _ch: fb_adapter,
    )
    assert result["channel"] == "facebook"
    assert result["status"] == "ok"
    assert result["impressions"] == 3200
    assert result["clicks"] == 210
    assert result["conversions"] == 12
    assert result["spend"] == 0
    row = store.rows[(camp.id, day, "facebook")]
    assert row.impressions == 3200
    assert row.clicks == 210
    assert row.conversions == 12
    assert len(fb_adapter.calls) == 1


def test_ingest_meta_metrics_pulls_instagram_organic_and_maps():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    events = [
        _ev("ig_impressions", 8800, day, channel="instagram"),
        _ev("ig_profile_views", 64, day, channel="instagram"),
    ]
    ig_adapter = FakeMetaOrganicAdapter(events)
    result = ingest_meta_metrics(
        store, camp, _conn("instagram"), day,
        organic_adapter_factory=lambda _ch: ig_adapter,
    )
    assert result["channel"] == "instagram"
    assert result["status"] == "ok"
    assert result["impressions"] == 8800
    assert result["clicks"] == 64
    row = store.rows[(camp.id, day, "instagram")]
    assert row.impressions == 8800
    assert row.clicks == 64


def test_ingest_meta_metrics_graceful_skip_when_not_connected():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    result = ingest_meta_metrics(
        store, camp, None, day,
        ads_adapter_factory=lambda _n: FakeMetaAdsAdapter([]),
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "not_connected"
    assert store.added == []


def test_ingest_meta_metrics_organic_isolates_error():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    fb_adapter = FakeMetaOrganicAdapter([], raise_on_metrics=True)
    result = ingest_meta_metrics(
        store, camp, _conn("facebook"), day,
        organic_adapter_factory=lambda _ch: fb_adapter,
    )
    assert result["status"] == "error"
    assert "meta organic boom" in result["error"]
    assert store.added == []


# ─── Integration via pull_for_campaign / run_pull ──────────────────────────────


def test_pull_for_campaign_routes_gmb_to_gbp_ingest():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="gmb", ncid="loc-1")
    events = [
        _ev("search_impressions", 700, day),
        _ev("directions_requests", 30, day),
        _ev("calls", 4, day),
    ]
    gbp_adapter = FakeGBPAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("gmb")], day, gbp_adapter=gbp_adapter
    )
    assert result["channels"]["gmb"]["status"] == "ok"
    assert result["channels"]["gmb"]["impressions"] == 700
    assert (camp.id, day, "gmb") in store.rows


def test_pull_for_campaign_routes_meta_ads_via_ingest_meta():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    events = [
        _meta_ads_ev("impressions", 2000, day),
        _meta_ads_ev("clicks", 90, day),
        _meta_ads_ev("cost", 18.0, day),
    ]
    ads_adapter = FakeMetaAdsAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("meta_ads")], day,
        adapter_factory=lambda _n: ads_adapter,
    )
    assert result["channels"]["meta_ads"]["status"] == "ok"
    assert result["channels"]["meta_ads"]["spend"] == 18.0
    assert (camp.id, day, "meta_ads") in store.rows


def test_pull_for_campaign_routes_facebook_organic():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")
    events = [
        _ev("fb_page_impressions", 1500, day, channel="facebook"),
        _ev("fb_page_post_engagements", 75, day, channel="facebook"),
    ]
    fb_adapter = FakeMetaOrganicAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("facebook")], day,
        meta_organic_adapter_factory=lambda _ch: fb_adapter,
    )
    assert result["channels"]["facebook"]["status"] == "ok"
    assert result["channels"]["facebook"]["impressions"] == 1500
    assert (camp.id, day, "facebook") in store.rows


def test_pull_for_campaign_gbp_not_connected_is_skipped():
    """No gmb connection present -> no gbp row, no crash."""
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="gmb", ncid="loc-1")
    result = pull_for_campaign(store, camp, [], day, gbp_adapter=FakeGBPAdapter([]))
    assert result["channels"] == {}
    assert store.added == []


def test_run_pull_ingests_gbp_and_meta_for_one_campaign():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="meta_ads", ncid="meta-1")

    gbp_events = [_ev("search_impressions", 400, day)]
    gbp_adapter = FakeGBPAdapter(gbp_events)

    fb_events = [_ev("fb_page_impressions", 900, day, channel="facebook")]
    fb_adapter = FakeMetaOrganicAdapter(fb_events)

    ads_events = [_meta_ads_ev("impressions", 3000, day), _meta_ads_ev("cost", 5.0, day)]
    ads_adapter = FakeMetaAdsAdapter(ads_events)

    def connections_by_brand(brand_id: Any) -> list[Any]:
        return [_conn("gmb"), _conn("facebook"), _conn("meta_ads")]

    results = run_pull(
        store, [camp], connections_by_brand, day,
        adapter_factory=lambda _n: ads_adapter,
        gbp_adapter=gbp_adapter,
        meta_organic_adapter_factory=lambda _ch: fb_adapter,
    )
    assert len(results) == 1
    channels = results[0]["channels"]
    assert channels["gmb"]["status"] == "ok"
    assert channels["facebook"]["status"] == "ok"
    assert channels["meta_ads"]["status"] == "ok"
    assert (camp.id, day, "gmb") in store.rows
    assert (camp.id, day, "facebook") in store.rows
    assert (camp.id, day, "meta_ads") in store.rows


# ─── LinkedIn (C.1.3) ─────────────────────────────────────────────────────────


class FakeLinkedInAdapter:
    """Sync organic adapter exposing ``metrics``."""

    def __init__(self, events: list[Any], raise_on_metrics: bool = False) -> None:
        self._events = events
        self._raise = raise_on_metrics
        self.calls: list[tuple[Any, datetime]] = []

    def metrics(self, tokens: Any, since: datetime) -> list[Any]:
        self.calls.append((tokens, since))
        if self._raise:
            raise RuntimeError("linkedin boom")
        return self._events


def _li_ev(metric: str, value: float, day: date) -> dict[str, Any]:
    return {
        "channel": "linkedin",
        "entity_type": "organization",
        "entity_id": "self",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


def test_linkedin_metric_map_buckets():
    assert LINKEDIN_METRIC_MAP["impressions"] == "impressions"
    assert LINKEDIN_METRIC_MAP["clicks"] == "clicks"
    assert LINKEDIN_METRIC_MAP["likes"] == "conversions"
    assert LINKEDIN_METRIC_MAP["comments"] == "revenue"


def test_ingest_linkedin_metrics_pulls_and_maps_data():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="linkedin", ncid="li-1")
    events = [
        _li_ev("impressions", 5400, day),
        _li_ev("clicks", 120, day),
        _li_ev("likes", 38, day),
        _li_ev("comments", 9, day),
    ]
    adapter = FakeLinkedInAdapter(events)
    result = ingest_linkedin_metrics(
        store, camp, _conn("linkedin"), day, adapter=adapter
    )
    assert result["channel"] == "linkedin"
    assert result["status"] == "ok"
    assert result["impressions"] == 5400
    assert result["clicks"] == 120
    assert result["conversions"] == 38
    assert result["revenue"] == 9
    assert result["spend"] == 0
    row = store.rows[(camp.id, day, "linkedin")]
    assert row.impressions == 5400
    assert row.clicks == 120
    assert row.conversions == 38
    assert float(row.revenue) == 9.0
    assert row.ctr == pytest.approx(120 / 5400, abs=1e-5)
    assert len(adapter.calls) == 1


def test_ingest_linkedin_metrics_graceful_skip_when_not_connected():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="linkedin", ncid="li-1")
    adapter = FakeLinkedInAdapter([])
    result = ingest_linkedin_metrics(store, camp, None, day, adapter=adapter)
    assert result["channel"] == "linkedin"
    assert result["status"] == "skipped"
    assert result["reason"] == "not_connected"
    assert adapter.calls == []
    assert store.added == []


def test_ingest_linkedin_metrics_isolates_adapter_error():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="linkedin", ncid="li-1")
    adapter = FakeLinkedInAdapter([], raise_on_metrics=True)
    result = ingest_linkedin_metrics(store, camp, _conn("linkedin"), day, adapter=adapter)
    assert result["status"] == "error"
    assert "linkedin boom" in result["error"]
    assert store.added == []


# ─── WhatsApp Business (C.1.4) ────────────────────────────────────────────────


class FakeWhatsAppAdapter:
    """Async organic adapter exposing ``metrics``."""

    def __init__(self, events: list[Any], raise_on_metrics: bool = False) -> None:
        self._events = events
        self._raise = raise_on_metrics
        self.calls: list[tuple[Any, datetime]] = []

    async def metrics(self, tokens: Any, since: datetime) -> list[Any]:
        self.calls.append((tokens, since))
        if self._raise:
            raise RuntimeError("whatsapp boom")
        return self._events


def _wa_ev(metric: str, value: float, day: date) -> dict[str, Any]:
    return {
        "channel": "whatsapp",
        "entity_type": "message",
        "entity_id": "phone-1",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


def test_whatsapp_metric_map_buckets():
    assert WHATSAPP_METRIC_MAP["delivered"] == "impressions"
    assert WHATSAPP_METRIC_MAP["read"] == "clicks"
    assert WHATSAPP_METRIC_MAP["replied"] == "conversions"


def test_ingest_whatsapp_metrics_pulls_and_maps_data():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="whatsapp", ncid="wa-1")
    events = [
        _wa_ev("delivered", 2100, day),
        _wa_ev("read", 540, day),
        _wa_ev("failed", 12, day),  # unmapped -> ignored
    ]
    adapter = FakeWhatsAppAdapter(events)
    result = ingest_whatsapp_metrics(
        store, camp, _conn("whatsapp"), day, adapter=adapter
    )
    assert result["channel"] == "whatsapp"
    assert result["status"] == "ok"
    assert result["impressions"] == 2100
    assert result["clicks"] == 540
    assert result["spend"] == 0
    row = store.rows[(camp.id, day, "whatsapp")]
    assert row.impressions == 2100
    assert row.clicks == 540
    assert row.ctr == pytest.approx(540 / 2100, abs=1e-5)
    assert len(adapter.calls) == 1


def test_ingest_whatsapp_metrics_graceful_skip_when_not_connected():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="whatsapp", ncid="wa-1")
    adapter = FakeWhatsAppAdapter([])
    result = ingest_whatsapp_metrics(store, camp, None, day, adapter=adapter)
    assert result["channel"] == "whatsapp"
    assert result["status"] == "skipped"
    assert result["reason"] == "not_connected"
    assert adapter.calls == []
    assert store.added == []


def test_ingest_whatsapp_metrics_isolates_adapter_error():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="whatsapp", ncid="wa-1")
    adapter = FakeWhatsAppAdapter([], raise_on_metrics=True)
    result = ingest_whatsapp_metrics(store, camp, _conn("whatsapp"), day, adapter=adapter)
    assert result["status"] == "error"
    assert "whatsapp boom" in result["error"]
    assert store.added == []


# ─── Google Ads (C.1.5) ───────────────────────────────────────────────────────


class FakeGoogleAdsAdapter:
    """Ads adapter exposing ``stats``."""

    def __init__(self, events: list[Any], raise_on_stats: bool = False) -> None:
        self._events = events
        self._raise = raise_on_stats
        self.calls: list[tuple[str, str, datetime]] = []

    def stats(self, tokens: Any, campaign_id: str, since: datetime) -> list[Any]:
        self.calls.append((campaign_id, str(tokens), since))
        if self._raise:
            raise RuntimeError("google ads boom")
        return self._events


def _gads_ev(metric: str, value: float, day: date) -> dict[str, Any]:
    return {
        "channel": "google_ads",
        "entity_type": "campaign",
        "entity_id": "gads-1",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


def test_ingest_google_ads_metrics_pulls_and_maps_data():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")
    events = [
        _gads_ev("impressions", 8000, day),
        _gads_ev("clicks", 320, day),
        _gads_ev("cost", 96.0, day),
        _gads_ev("conversions", 14, day),
    ]
    adapter = FakeGoogleAdsAdapter(events)
    result = ingest_google_ads_metrics(
        store, camp, _conn("google_ads"), day,
        ads_adapter_factory=lambda _n: adapter,
    )
    assert result["channel"] == "google_ads"
    assert result["status"] == "ok"
    assert result["impressions"] == 8000
    assert result["clicks"] == 320
    assert result["conversions"] == 14
    assert result["spend"] == 96.0
    row = store.rows[(camp.id, day, "google_ads")]
    assert row.impressions == 8000
    assert float(row.spend) == 96.0
    assert row.ctr == pytest.approx(320 / 8000, abs=1e-5)
    assert adapter.calls[0][0] == "gads-1"


def test_ingest_google_ads_metrics_graceful_skip_when_not_connected():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")
    adapter = FakeGoogleAdsAdapter([])
    result = ingest_google_ads_metrics(
        store, camp, None, day,
        ads_adapter_factory=lambda _n: adapter,
    )
    assert result["channel"] == "google_ads"
    assert result["status"] == "skipped"
    assert result["reason"] == "not_connected"
    assert adapter.calls == []
    assert store.added == []


def test_ingest_google_ads_metrics_skips_without_network_campaign_id():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeGoogleAdsAdapter([])
    result = ingest_google_ads_metrics(
        store, camp, _conn("google_ads"), day,
        ads_adapter_factory=lambda _n: adapter,
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "no_network_campaign_id"
    assert adapter.calls == []
    assert store.added == []


def test_ingest_google_ads_metrics_isolates_adapter_error():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")
    adapter = FakeGoogleAdsAdapter([], raise_on_stats=True)
    result = ingest_google_ads_metrics(
        store, camp, _conn("google_ads"), day,
        ads_adapter_factory=lambda _n: adapter,
    )
    assert result["status"] == "error"
    assert "google ads boom" in result["error"]
    assert store.added == []


# ─── YouTube (C.1.6) ──────────────────────────────────────────────────────────


class FakeYouTubeAdapter:
    """Sync organic adapter exposing ``metrics``."""

    def __init__(self, events: list[Any], raise_on_metrics: bool = False) -> None:
        self._events = events
        self._raise = raise_on_metrics
        self.calls: list[tuple[Any, datetime]] = []

    def metrics(self, tokens: Any, since: datetime) -> list[Any]:
        self.calls.append((tokens, since))
        if self._raise:
            raise RuntimeError("youtube boom")
        return self._events


def _yt_ev(metric: str, value: float, day: date) -> dict[str, Any]:
    return {
        "channel": "youtube",
        "entity_type": "channel",
        "entity_id": "self",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


def test_youtube_metric_map_buckets():
    assert YOUTUBE_METRIC_MAP["impressions"] == "impressions"
    assert YOUTUBE_METRIC_MAP["views"] == "clicks"
    assert YOUTUBE_METRIC_MAP["watch_time_minutes"] == "revenue"


def test_ingest_youtube_metrics_pulls_and_maps_data():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="youtube", ncid="yt-1")
    events = [
        _yt_ev("impressions", 12000, day),
        _yt_ev("views", 900, day),
        _yt_ev("watch_time_minutes", 420.5, day),
        _yt_ev("ctr", 0.075, day),  # unmapped -> ignored (derived recomputed)
    ]
    adapter = FakeYouTubeAdapter(events)
    result = ingest_youtube_metrics(
        store, camp, _conn("youtube"), day, adapter=adapter
    )
    assert result["channel"] == "youtube"
    assert result["status"] == "ok"
    assert result["impressions"] == 12000
    assert result["clicks"] == 900
    assert result["revenue"] == 420.5
    assert result["spend"] == 0
    row = store.rows[(camp.id, day, "youtube")]
    assert row.impressions == 12000
    assert row.clicks == 900
    assert float(row.revenue) == 420.5
    # Derived ctr = views / impressions (real YouTube CTR).
    assert row.ctr == pytest.approx(900 / 12000, abs=1e-5)
    assert len(adapter.calls) == 1


def test_ingest_youtube_metrics_graceful_skip_when_not_connected():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="youtube", ncid="yt-1")
    adapter = FakeYouTubeAdapter([])
    result = ingest_youtube_metrics(store, camp, None, day, adapter=adapter)
    assert result["channel"] == "youtube"
    assert result["status"] == "skipped"
    assert result["reason"] == "not_connected"
    assert adapter.calls == []
    assert store.added == []


def test_ingest_youtube_metrics_isolates_adapter_error():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="youtube", ncid="yt-1")
    adapter = FakeYouTubeAdapter([], raise_on_metrics=True)
    result = ingest_youtube_metrics(store, camp, _conn("youtube"), day, adapter=adapter)
    assert result["status"] == "error"
    assert "youtube boom" in result["error"]
    assert store.added == []


# ─── Routing via pull_for_campaign / run_pull (C.1.3–C.1.6) ────────────────────


def test_pull_for_campaign_routes_linkedin_to_ingest():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="linkedin", ncid="li-1")
    events = [_li_ev("impressions", 3000, day), _li_ev("clicks", 75, day)]
    adapter = FakeLinkedInAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("linkedin")], day, linkedin_adapter=adapter
    )
    assert result["channels"]["linkedin"]["status"] == "ok"
    assert result["channels"]["linkedin"]["impressions"] == 3000
    assert (camp.id, day, "linkedin") in store.rows


def test_pull_for_campaign_routes_whatsapp_to_ingest():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="whatsapp", ncid="wa-1")
    events = [_wa_ev("delivered", 1500, day), _wa_ev("read", 300, day)]
    adapter = FakeWhatsAppAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("whatsapp")], day, whatsapp_adapter=adapter
    )
    assert result["channels"]["whatsapp"]["status"] == "ok"
    assert result["channels"]["whatsapp"]["impressions"] == 1500
    assert (camp.id, day, "whatsapp") in store.rows


def test_pull_for_campaign_routes_google_ads_to_ingest():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")
    events = [
        _gads_ev("impressions", 6000, day),
        _gads_ev("clicks", 210, day),
        _gads_ev("cost", 45.0, day),
    ]
    adapter = FakeGoogleAdsAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("google_ads")], day,
        adapter_factory=lambda _n: adapter,
    )
    assert result["channels"]["google_ads"]["status"] == "ok"
    assert result["channels"]["google_ads"]["spend"] == 45.0
    assert (camp.id, day, "google_ads") in store.rows


def test_pull_for_campaign_routes_youtube_to_ingest():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="youtube", ncid="yt-1")
    events = [_yt_ev("impressions", 9000, day), _yt_ev("views", 720, day)]
    adapter = FakeYouTubeAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("youtube")], day, youtube_adapter=adapter
    )
    assert result["channels"]["youtube"]["status"] == "ok"
    assert result["channels"]["youtube"]["impressions"] == 9000
    assert (camp.id, day, "youtube") in store.rows


def test_pull_for_campaign_new_channels_not_connected_are_skipped():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="linkedin", ncid="li-1")
    result = pull_for_campaign(
        store, camp, [], day,
        linkedin_adapter=FakeLinkedInAdapter([]),
        whatsapp_adapter=FakeWhatsAppAdapter([]),
        youtube_adapter=FakeYouTubeAdapter([]),
    )
    assert result["channels"] == {}
    assert store.added == []


def test_run_pull_ingests_all_new_channels_for_one_campaign():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")

    li_adapter = FakeLinkedInAdapter([_li_ev("impressions", 1000, day)])
    wa_adapter = FakeWhatsAppAdapter([_wa_ev("delivered", 800, day)])
    yt_adapter = FakeYouTubeAdapter([_yt_ev("impressions", 5000, day)])
    gads_adapter = FakeGoogleAdsAdapter(
        [_gads_ev("impressions", 4000, day), _gads_ev("cost", 20.0, day)]
    )

    def connections_by_brand(brand_id: Any) -> list[Any]:
        return [
            _conn("linkedin"),
            _conn("whatsapp"),
            _conn("youtube"),
            _conn("google_ads"),
        ]

    results = run_pull(
        store, [camp], connections_by_brand, day,
        adapter_factory=lambda _n: gads_adapter,
        linkedin_adapter=li_adapter,
        whatsapp_adapter=wa_adapter,
        youtube_adapter=yt_adapter,
    )
    assert len(results) == 1
    channels = results[0]["channels"]
    assert channels["linkedin"]["status"] == "ok"
    assert channels["whatsapp"]["status"] == "ok"
    assert channels["youtube"]["status"] == "ok"
    assert channels["google_ads"]["status"] == "ok"
    assert (camp.id, day, "linkedin") in store.rows
    assert (camp.id, day, "whatsapp") in store.rows
    assert (camp.id, day, "youtube") in store.rows
    assert (camp.id, day, "google_ads") in store.rows
