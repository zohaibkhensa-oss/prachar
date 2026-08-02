"""Tests for the performance ingestion worker (P4.2).

Run with:
    .venv/bin/python -m pytest apps/workers/prachar_workers/tests/test_performance.py -q
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from prachar_workers import performance
from prachar_workers.performance import (
    PerformanceStore,
    aggregate_events,
    compute_derived,
    pull_for_campaign,
    run_pull,
    upsert_performance,
)


# ─── Fakes ────────────────────────────────────────────────────────────────────


class FakeStore(PerformanceStore):
    """In-memory store that mirrors the ORM upsert semantics without a DB."""

    def __init__(self) -> None:
        self.rows: dict[tuple[Any, date, str], Any] = {}
        self.added: list[Any] = []

    def find(self, campaign_id: Any, target_date: date, channel: str) -> Any | None:
        return self.rows.get((campaign_id, target_date, channel))

    def add(self, perf: Any) -> None:
        self.added.append(perf)
        # Register so a subsequent find() locates it.
        self.rows[(perf.campaign_id, perf.date, perf.channel)] = perf

    def flush(self) -> None:  # no-op
        pass


class FakeAdapter:
    """Minimal adapter implementing only ``stats``."""

    def __init__(self, events: list[Any], raise_on_stats: bool = False) -> None:
        self._events = events
        self._raise = raise_on_stats
        self.stats_calls: list[tuple[str, str, datetime]] = []

    def stats(self, tokens: Any, campaign_id: str, since: datetime) -> list[Any]:
        self.stats_calls.append((campaign_id, str(tokens), since))
        if self._raise:
            raise RuntimeError("adapter boom")
        return self._events


def _metric(metric: str, value: float, day: date) -> dict[str, Any]:
    return {
        "channel": "google_ads",
        "entity_type": "campaign",
        "entity_id": "gads-1",
        "metric": metric,
        "value": value,
        "ts": datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    }


def _campaign(
    network: str = "google_ads",
    ncid: str = "gads-1",
    brand_id: Any | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        brand_id=brand_id or uuid.uuid4(),
        network=network,
        network_campaign_id=ncid,
    )


def _conn(channel: str = "google_ads") -> SimpleNamespace:
    return SimpleNamespace(channel=channel)


# ─── Pure helper tests ────────────────────────────────────────────────────────


def test_compute_derived_basic():
    ctr, cpa, roas = compute_derived(
        impressions=10_000, clicks=500, conversions=25, spend=1500.0, revenue=4500.0
    )
    assert ctr == pytest.approx(0.05)
    assert cpa == pytest.approx(60.0)
    assert roas == pytest.approx(3.0)


def test_compute_derived_division_by_zero():
    """Zero denominators must yield 0.0, never raise."""
    ctr, cpa, roas = compute_derived(
        impressions=0, clicks=0, conversions=0, spend=0.0, revenue=0.0
    )
    assert ctr == 0.0
    assert cpa == 0.0
    assert roas == 0.0

    # roas with spend=0 but revenue>0 still 0.0
    _, _, roas2 = compute_derived(0, 0, 0, 0.0, 100.0)
    assert roas2 == 0.0


def test_aggregate_events_filters_by_date_and_maps_cost():
    day = date(2026, 7, 25)
    other = date(2026, 7, 24)
    events = [
        _metric("impressions", 1000, day),
        _metric("clicks", 50, day),
        _metric("cost", 12.5, day),
        _metric("conversions", 2, day),
        _metric("revenue", 40.0, day),
        _metric("impressions", 999, other),  # ignored — wrong day
        _metric("unknown_metric", 5, day),  # ignored — unknown
    ]
    agg = aggregate_events(events, day)
    assert agg["impressions"] == 1000
    assert agg["clicks"] == 50
    assert agg["conversions"] == 2
    assert agg["spend"] == 12.5
    assert agg["revenue"] == 40.0


def test_aggregate_events_supports_objects():
    """aggregate_events works with MetricEvent Pydantic objects too."""
    from prachar_shared.contracts import MetricEvent

    day = date(2026, 7, 25)
    ev = MetricEvent(
        channel="google_ads",
        entity_type="campaign",
        entity_id="gads-1",
        metric="impressions",
        value=750,
        ts=datetime(day.year, day.month, day.day, 12, 0, tzinfo=UTC),
    )
    agg = aggregate_events([ev], day)
    assert agg["impressions"] == 750


# ─── Upsert tests ─────────────────────────────────────────────────────────────


def test_upsert_inserts_new_row():
    store = FakeStore()
    cid = uuid.uuid4()
    day = date(2026, 7, 25)
    agg = {
        "impressions": 1000,
        "clicks": 50,
        "conversions": 2,
        "spend": 12.5,
        "revenue": 40.0,
    }
    row = upsert_performance(store, cid, day, "google_ads", agg)
    assert row.campaign_id == cid
    assert row.date == day
    assert row.channel == "google_ads"
    assert row.impressions == 1000
    assert row.ctr == pytest.approx(0.05)
    assert row.roas == pytest.approx(3.2)
    assert len(store.added) == 1


def test_upsert_updates_existing_no_duplicate():
    """Same (campaign_id, date, channel) updates the existing row — no duplicate."""
    store = FakeStore()
    cid = uuid.uuid4()
    day = date(2026, 7, 25)

    upsert_performance(
        store,
        cid,
        day,
        "google_ads",
        {"impressions": 1000, "clicks": 50, "conversions": 2, "spend": 12.5, "revenue": 40.0},
    )
    # Second pull for the same key with refreshed numbers.
    upsert_performance(
        store,
        cid,
        day,
        "google_ads",
        {"impressions": 2000, "clicks": 120, "conversions": 6, "spend": 30.0, "revenue": 90.0},
    )

    # Only one row in the store, with updated values.
    assert len(store.added) == 1
    row = store.rows[(cid, day, "google_ads")]
    assert row.impressions == 2000
    assert row.clicks == 120
    assert row.conversions == 6
    assert float(row.spend) == 30.0
    assert row.ctr == pytest.approx(0.06)
    assert row.cpa == pytest.approx(5.0)
    assert row.roas == pytest.approx(3.0)


def test_upsert_different_channels_create_separate_rows():
    store = FakeStore()
    cid = uuid.uuid4()
    day = date(2026, 7, 25)
    upsert_performance(
        store, cid, day, "google_ads",
        {"impressions": 100, "clicks": 5, "conversions": 1, "spend": 1.0, "revenue": 2.0},
    )
    upsert_performance(
        store, cid, day, "meta_ads",
        {"impressions": 200, "clicks": 10, "conversions": 2, "spend": 2.0, "revenue": 4.0},
    )
    assert len(store.added) == 2
    assert store.rows[(cid, day, "google_ads")].impressions == 100
    assert store.rows[(cid, day, "meta_ads")].impressions == 200


# ─── pull_for_campaign tests ──────────────────────────────────────────────────


def test_pull_for_campaign_processes_channel_and_upserts():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")
    events = [
        _metric("impressions", 1000, day),
        _metric("clicks", 50, day),
        _metric("cost", 12.5, day),
        _metric("conversions", 2, day),
        _metric("revenue", 40.0, day),
    ]
    adapter = FakeAdapter(events)
    result = pull_for_campaign(
        store, camp, [_conn("google_ads")], day, adapter_factory=lambda _n: adapter
    )
    assert result["campaign_id"] == str(camp.id)
    assert result["channels"]["google_ads"]["status"] == "ok"
    assert result["channels"]["google_ads"]["impressions"] == 1000
    # Row was upserted.
    row = store.rows[(camp.id, day, "google_ads")]
    assert row.impressions == 1000
    assert row.ctr == pytest.approx(0.05)
    # Adapter was called with the network campaign id.
    assert adapter.stats_calls[0][0] == "gads-1"


def test_pull_for_campaign_per_channel_error_isolation():
    """One channel failing must not block other channels for the same campaign."""
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")

    good_events = [
        _metric("impressions", 1000, day),
        _metric("clicks", 50, day),
        _metric("cost", 12.5, day),
        _metric("conversions", 2, day),
    ]
    good_adapter = FakeAdapter(good_events)
    bad_adapter = FakeAdapter([], raise_on_stats=True)

    def factory(network: str) -> Any:
        if network == "meta_ads":
            return bad_adapter
        return good_adapter

    # Two connected channels for the brand: google_ads (succeeds) and
    # meta_ads (adapter raises).  The meta_ads failure must not prevent the
    # google_ads pull from completing and upserting.
    result = pull_for_campaign(
        store,
        camp,
        [_conn("google_ads"), _conn("meta_ads")],
        day,
        adapter_factory=factory,
    )
    assert result["channels"]["google_ads"]["status"] == "ok"
    assert result["channels"]["meta_ads"]["status"] == "error"
    assert "adapter boom" in result["channels"]["meta_ads"]["error"]
    # The successful channel still upserted its row.
    assert (camp.id, day, "google_ads") in store.rows
    # The failed channel did not upsert anything.
    assert (camp.id, day, "meta_ads") not in store.rows


def test_pull_for_campaign_error_when_adapter_raises_on_matching_channel():
    """When the matching channel's adapter raises, the channel is marked error."""
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid="gads-1")
    bad_adapter = FakeAdapter([], raise_on_stats=True)

    result = pull_for_campaign(
        store, camp, [_conn("google_ads")], day, adapter_factory=lambda _n: bad_adapter
    )
    assert result["channels"]["google_ads"]["status"] == "error"
    assert "adapter boom" in result["channels"]["google_ads"]["error"]
    # Nothing was upserted.
    assert store.added == []


def test_pull_for_campaign_skips_when_no_network_campaign_id():
    store = FakeStore()
    day = date(2026, 7, 25)
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeAdapter([])
    result = pull_for_campaign(
        store, camp, [_conn("google_ads")], day, adapter_factory=lambda _n: adapter
    )
    assert result["channels"]["google_ads"]["status"] == "skipped"
    assert result["channels"]["google_ads"]["reason"] == "no_network_campaign_id"
    assert adapter.stats_calls == []


# ─── run_pull tests ───────────────────────────────────────────────────────────


def test_run_pull_processes_all_active_campaigns():
    store = FakeStore()
    day = date(2026, 7, 25)
    c1 = _campaign(network="google_ads", ncid="gads-1")
    c2 = _campaign(network="meta_ads", ncid="meta-1")

    events = [
        _metric("impressions", 500, day),
        _metric("clicks", 25, day),
        _metric("cost", 5.0, day),
        _metric("conversions", 1, day),
        _metric("revenue", 15.0, day),
    ]
    adapter = FakeAdapter(events)

    def factory(network: str) -> Any:
        return adapter

    def connections_by_brand(brand_id: Any) -> list[Any]:
        # Return a connection matching whatever network each campaign uses.
        # We map by brand id deterministically.
        if brand_id == c1.brand_id:
            return [_conn("google_ads")]
        return [_conn("meta_ads")]

    results = run_pull(
        store, [c1, c2], connections_by_brand, day, adapter_factory=factory
    )
    assert len(results) == 2
    ids = {r["campaign_id"] for r in results}
    assert ids == {str(c1.id), str(c2.id)}
    # Both campaigns produced a row.
    assert (c1.id, day, "google_ads") in store.rows
    assert (c2.id, day, "meta_ads") in store.rows


def test_run_pull_isolates_per_campaign_crash():
    """A campaign that crashes must not stop subsequent campaigns."""
    store = FakeStore()
    day = date(2026, 7, 25)
    good = _campaign(network="google_ads", ncid="gads-1")
    bad = SimpleNamespace(id=uuid.uuid4(), brand_id=uuid.uuid4(), network="google_ads", network_campaign_id="gads-x")

    good_adapter = FakeAdapter([_metric("impressions", 100, day)])

    def factory(network: str) -> Any:
        return good_adapter

    def connections_by_brand(brand_id: Any) -> list[Any]:
        # For the "bad" brand, return a non-iterable to force a crash inside
        # pull_for_campaign's connection handling path is not enough — instead
        # we make connections_by_brand raise for the bad brand.
        if brand_id == bad.brand_id:
            raise RuntimeError("brand lookup boom")
        return [_conn("google_ads")]

    results = run_pull(
        store, [bad, good], connections_by_brand, day, adapter_factory=factory
    )
    # bad campaign errored, good campaign still processed.
    assert len(results) == 2
    assert results[0]["status"] == "error"
    assert results[1]["channels"]["google_ads"]["status"] == "ok"
    assert (good.id, day, "google_ads") in store.rows


# ─── Celery task registration ─────────────────────────────────────────────────


def test_pull_daily_performance_is_registered_task():
    from prachar_workers.performance import pull_daily_performance

    assert hasattr(pull_daily_performance, "delay")
    assert pull_daily_performance.name == "prachar_workers.performance.pull_daily_performance"


def test_pull_daily_performance_runs_eager_without_db():
    """In eager mode the task must not raise even when the DB is unavailable."""
    from prachar_workers.performance import pull_daily_performance

    prev = performance.celery_app.conf.task_always_eager
    prev_prop = performance.celery_app.conf.task_eager_propagates
    performance.celery_app.conf.task_always_eager = True
    performance.celery_app.conf.task_eager_propagates = True
    try:
        result = pull_daily_performance.apply(args=("2026-07-25",)).get()
    finally:
        performance.celery_app.conf.task_always_eager = prev
        performance.celery_app.conf.task_eager_propagates = prev_prop
    # DB unavailable in test env → graceful error dict, never an exception.
    assert isinstance(result, dict)
    assert result["date"] == "2026-07-25"
