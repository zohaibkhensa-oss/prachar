"""Tests for the Proactive Engine — anomaly detection (P5.1) and
recommendation generation (P5.2).

Run with:
    .venv/bin/python -m pytest packages/shared/prachar_shared/marketing_intelligence/tests/test_proactive_engine.py -q
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded
from prachar_shared.marketing_intelligence.proactive_engine import (
    Anomaly,
    ProactiveEngine,
)


# ─── Fakes ────────────────────────────────────────────────────────────────────


def _row(
    d: date,
    *,
    impressions: int = 10_000,
    clicks: int = 200,
    conversions: int = 20,
    spend: float = 200.0,
    revenue: float = 600.0,
    channel: str = "google_ads",
) -> SimpleNamespace:
    """Build a CampaignPerformance-like row without a DB."""
    return SimpleNamespace(
        date=d,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        spend=spend,
        revenue=revenue,
        channel=channel,
    )


def _campaign(cid: str | None = None, brand_id: str | None = None) -> SimpleNamespace:
    """Build a Campaign-like object."""
    return SimpleNamespace(
        id=cid or str(uuid.uuid4()),
        brand_id=brand_id or str(uuid.uuid4()),
    )


class FakeSession:
    """Async session that returns pre-seeded campaigns and performance rows."""

    def __init__(
        self,
        campaigns: list[Any] | None = None,
        perf_rows: list[Any] | None = None,
    ) -> None:
        self._campaigns = campaigns or []
        self._perf_rows = perf_rows or []
        self.execute = AsyncMock(side_effect=self._execute)

    async def _execute(self, stmt: Any) -> Any:
        # Inspect the statement to decide what to return.
        stmt_str = str(stmt)
        # Heuristic: if the query targets Campaign, return campaigns;
        # otherwise return performance rows.
        if "campaigns" in stmt_str and "campaign_performance" not in stmt_str:
            return MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=self._campaigns))
                )
            )
        return MagicMock(
            scalars=MagicMock(
                return_value=MagicMock(all=MagicMock(return_value=self._perf_rows))
            )
        )


def _engine_with_data(
    campaigns: list[Any] | None = None,
    perf_rows: list[Any] | None = None,
) -> ProactiveEngine:
    session = FakeSession(campaigns=campaigns, perf_rows=perf_rows)
    return ProactiveEngine(session_factory=lambda: session)


# ─── detect_anomalies: structure ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_anomalies_returns_list_of_anomaly_objects():
    """detect_anomalies returns a list of Anomaly instances with required fields."""
    brand_id = str(uuid.uuid4())
    camp = _campaign(brand_id=brand_id)
    today = date.today()
    # 14 days of steady data — no anomalies expected, but structure is valid.
    rows = [_row(today - timedelta(days=i)) for i in range(14, 0, -1)]
    engine = _engine_with_data(campaigns=[camp], perf_rows=rows)

    anomalies = await engine.detect_anomalies(brand_id, days=30)

    assert isinstance(anomalies, list)
    for a in anomalies:
        assert isinstance(a, Anomaly)
        d = a.to_dict()
        for key in ("brand_id", "campaign_id", "metric", "magnitude", "timeframe", "severity", "direction"):
            assert key in d
        assert d["direction"] in ("drop", "spike", "plateau")
        assert d["severity"] in ("high", "medium", "low")


# ─── drop detection ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_drop_when_metric_declines_over_20_percent():
    """A >20% week-over-week decline in conversions is detected as a drop."""
    brand_id = str(uuid.uuid4())
    camp = _campaign(brand_id=brand_id)
    today = date.today()
    rows = []
    # Previous 7 days: 100 conversions/day
    for i in range(14, 7, -1):
        rows.append(_row(today - timedelta(days=i), conversions=100))
    # Last 7 days: 50 conversions/day (50% drop)
    for i in range(7, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=50))
    engine = _engine_with_data(campaigns=[camp], perf_rows=rows)

    anomalies = await engine.detect_anomalies(brand_id, days=30)

    drops = [a for a in anomalies if a.direction == "drop" and a.metric == "conversions"]
    assert len(drops) >= 1
    drop = drops[0]
    assert drop.magnitude < -0.20
    assert drop.severity in ("high", "medium", "low")


# ─── spike detection ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_spike_when_metric_increases_over_50_percent():
    """A >50% week-over-week increase in conversions is detected as a spike."""
    brand_id = str(uuid.uuid4())
    camp = _campaign(brand_id=brand_id)
    today = date.today()
    rows = []
    # Previous 7 days: 20 conversions/day
    for i in range(14, 7, -1):
        rows.append(_row(today - timedelta(days=i), conversions=20))
    # Last 7 days: 50 conversions/day (150% increase)
    for i in range(7, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=50))
    engine = _engine_with_data(campaigns=[camp], perf_rows=rows)

    anomalies = await engine.detect_anomalies(brand_id, days=30)

    spikes = [a for a in anomalies if a.direction == "spike" and a.metric == "conversions"]
    assert len(spikes) >= 1
    spike = spikes[0]
    assert spike.magnitude > 0.50
    assert spike.severity in ("high", "medium", "low")


# ─── plateau detection ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_plateau_when_metric_flat_for_2_weeks():
    """A metric that changes <5% for 2+ weeks is detected as a plateau."""
    brand_id = str(uuid.uuid4())
    camp = _campaign(brand_id=brand_id)
    today = date.today()
    rows = []
    # 14 days of perfectly flat conversions (0% change)
    for i in range(14, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=100))
    engine = _engine_with_data(campaigns=[camp], perf_rows=rows)

    anomalies = await engine.detect_anomalies(brand_id, days=30)

    plateaus = [a for a in anomalies if a.direction == "plateau" and a.metric == "conversions"]
    assert len(plateaus) >= 1
    plateau = plateaus[0]
    assert abs(plateau.magnitude) < 0.05
    assert plateau.severity == "low"


# ─── no data ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detect_anomalies_empty_list_when_no_data():
    """detect_anomalies returns an empty list when there is no performance data."""
    brand_id = str(uuid.uuid4())
    camp = _campaign(brand_id=brand_id)
    engine = _engine_with_data(campaigns=[camp], perf_rows=[])

    anomalies = await engine.detect_anomalies(brand_id, days=30)
    assert anomalies == []


@pytest.mark.asyncio
async def test_detect_anomalies_empty_list_when_no_campaigns():
    """detect_anomalies returns an empty list when the brand has no campaigns."""
    brand_id = str(uuid.uuid4())
    engine = _engine_with_data(campaigns=[], perf_rows=[])

    anomalies = await engine.detect_anomalies(brand_id, days=30)
    assert anomalies == []


# ─── to_dict ──────────────────────────────────────────────────────────────────


def test_anomaly_to_dict_contains_all_fields():
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )
    d = anomaly.to_dict()
    assert d == {
        "brand_id": "b1",
        "campaign_id": "c1",
        "metric": "conversions",
        "magnitude": -0.35,
        "timeframe": "last 7 days vs previous 7 days",
        "severity": "medium",
        "direction": "drop",
    }


# ─── generate_recommendation (P5.2) ───────────────────────────────────────────


def _fake_gateway(text: str = '{"what_to_do": "Refresh creative", "why": "CTR is declining", "creative_directions": ["A", "B", "C"], "expected_impact": "Recover 15% CTR"}'):
    """Build a fake AIGateway whose complete() returns a canned response."""
    gw = MagicMock()
    comp = MagicMock()
    comp.text = text
    gw.complete = MagicMock(return_value=comp)
    return gw


@pytest.mark.asyncio
async def test_generate_recommendation_returns_recommendation_dict():
    """generate_recommendation returns a dict with the required keys."""
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )
    gw = _fake_gateway()
    engine = ProactiveEngine(session_factory=lambda: None)

    rec = await engine.generate_recommendation(
        anomaly, gateway=gw, tenant_id=uuid.uuid4(), plan="agency"
    )

    assert isinstance(rec, dict)
    assert "what_to_do" in rec
    assert "why" in rec
    assert "creative_directions" in rec
    assert "expected_impact" in rec
    assert isinstance(rec["creative_directions"], list)
    assert len(rec["creative_directions"]) == 3


@pytest.mark.asyncio
async def test_generate_recommendation_falls_back_to_empty_dict_on_failure():
    """generate_recommendation returns {} when the AI call fails (non-budget)."""
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=RuntimeError("AI is down"))
    engine = ProactiveEngine(session_factory=lambda: None)

    rec = await engine.generate_recommendation(
        anomaly, gateway=gw, tenant_id=uuid.uuid4(), plan="agency"
    )
    assert rec == {}


@pytest.mark.asyncio
async def test_generate_recommendation_reraises_budget_exceeded():
    """generate_recommendation re-raises BudgetExceeded."""
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=BudgetExceeded("over budget"))
    engine = ProactiveEngine(session_factory=lambda: None)

    with pytest.raises(BudgetExceeded):
        await engine.generate_recommendation(
            anomaly, gateway=gw, tenant_id=uuid.uuid4(), plan="agency"
        )


@pytest.mark.asyncio
async def test_generate_recommendation_handles_malformed_json():
    """generate_recommendation returns {} when the AI returns non-JSON."""
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=0.75,
        timeframe="last 7 days vs previous 7 days",
        severity="high",
        direction="spike",
    )
    gw = _fake_gateway(text="This is not JSON at all.")
    engine = ProactiveEngine(session_factory=lambda: None)

    rec = await engine.generate_recommendation(
        anomaly, gateway=gw, tenant_id=uuid.uuid4(), plan="agency"
    )
    # Falls back to empty dict structure (keys present but empty).
    assert isinstance(rec, dict)
    assert rec.get("what_to_do", "") == ""


# ─── C.2.1: Live performance data in proactive recommendations ────────────────


@pytest.mark.asyncio
async def test_generate_recommendation_includes_live_context_in_prompt():
    """When live_context is provided, it is included in the recommendation
    prompt sent to the AI gateway."""
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )

    captured_prompt: list[str] = []
    gw = MagicMock()
    comp = MagicMock()
    comp.text = '{"what_to_do": "Refresh creative", "why": "CTR declining", "creative_directions": ["A", "B", "C"], "expected_impact": "Recover 15%"}'
    gw.complete = MagicMock(side_effect=lambda **kw: captured_prompt.append(kw.get("prompt", "")) or comp)
    engine = ProactiveEngine(session_factory=lambda: None)

    live_ctx = "Instagram: 12K reach, 3% engagement. WhatsApp: 12% conversion."
    await engine.generate_recommendation(
        anomaly, gateway=gw, tenant_id=uuid.uuid4(), plan="agency",
        live_context=live_ctx,
    )

    assert captured_prompt, "gateway.complete should have been called"
    prompt = captured_prompt[0]
    assert "Live performance data" in prompt
    assert "Instagram" in prompt
    assert "12K reach" in prompt
    assert "WhatsApp" in prompt


@pytest.mark.asyncio
async def test_generate_recommendation_without_live_context_works():
    """When live_context is not provided, the prompt works normally
    (backward compatible)."""
    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )

    captured_prompt: list[str] = []
    gw = MagicMock()
    comp = MagicMock()
    comp.text = '{"what_to_do": "Refresh creative", "why": "CTR declining", "creative_directions": ["A", "B", "C"], "expected_impact": "Recover 15%"}'
    gw.complete = MagicMock(side_effect=lambda **kw: captured_prompt.append(kw.get("prompt", "")) or comp)
    engine = ProactiveEngine(session_factory=lambda: None)

    await engine.generate_recommendation(
        anomaly, gateway=gw, tenant_id=uuid.uuid4(), plan="agency",
    )

    assert captured_prompt
    prompt = captured_prompt[0]
    assert "Live performance data" not in prompt
    assert "Anomaly details" in prompt


def test_format_as_prachar_message_includes_live_context():
    """format_as_prachar_message references live data when provided."""
    from prachar_shared.marketing_intelligence.proactive_engine import (
        format_as_prachar_message,
    )

    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )
    live_ctx = "Instagram: 12K reach, 3% engagement. WhatsApp: 12% conversion."
    msg = format_as_prachar_message(anomaly, live_context=live_ctx)

    assert "Instagram" in msg
    assert "12K reach" in msg
    assert "WhatsApp" in msg
    assert "I noticed" in msg


def test_format_as_prachar_message_without_live_context():
    """format_as_prachar_message works without live context (backward compatible)."""
    from prachar_shared.marketing_intelligence.proactive_engine import (
        format_as_prachar_message,
    )

    anomaly = Anomaly(
        brand_id="b1",
        campaign_id="c1",
        metric="conversions",
        magnitude=-0.35,
        timeframe="last 7 days vs previous 7 days",
        severity="medium",
        direction="drop",
    )
    msg = format_as_prachar_message(anomaly)

    assert "I noticed" in msg
    assert "Here's what I'm seeing" not in msg


@pytest.mark.asyncio
async def test_load_live_performance_summary_returns_concise_string():
    """load_live_performance_summary returns a concise per-channel summary."""
    from datetime import date, timedelta

    from types import SimpleNamespace

    brand_id = str(uuid.uuid4())
    camp_id = str(uuid.uuid4())
    today = date.today()
    perf_rows = [
        SimpleNamespace(
            date=today - timedelta(days=1),
            impressions=12_000, clicks=360, conversions=15,
            spend=500.0, revenue=1000.0, channel="instagram",
        ),
        SimpleNamespace(
            date=today - timedelta(days=2),
            impressions=0, clicks=50, conversions=6,
            spend=0.0, revenue=0.0, channel="whatsapp",
        ),
    ]
    campaigns = [SimpleNamespace(id=camp_id, brand_id=brand_id)]

    # Custom session that handles both query patterns:
    # 1. select(Campaign.id) → result.all() returns list of tuples
    # 2. select(CampaignPerformance) → result.scalars().all() returns rows
    class _LiveSession:
        def __init__(self):
            self.execute = AsyncMock(side_effect=self._execute)

        async def _execute(self, stmt):
            stmt_str = str(stmt)
            if "campaigns" in stmt_str and "campaign_performance" not in stmt_str:
                # Campaign ID query — result.all() returns tuples.
                return MagicMock(all=MagicMock(return_value=[(camp_id,)]))
            # Performance query — result.scalars().all() returns rows.
            return MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=perf_rows))
                )
            )

    engine = ProactiveEngine(session_factory=lambda: _LiveSession())

    summary = await engine.load_live_performance_summary(brand_id, days=30)

    # Should mention both platforms.
    assert "Instagram" in summary
    assert "WhatsApp" in summary
    assert "reach" in summary.lower()


@pytest.mark.asyncio
async def test_load_live_performance_summary_empty_when_no_data():
    """load_live_performance_summary returns '' when there is no data."""
    brand_id = str(uuid.uuid4())

    class _EmptySession:
        def __init__(self):
            self.execute = AsyncMock(side_effect=self._execute)

        async def _execute(self, stmt):
            stmt_str = str(stmt)
            if "campaigns" in stmt_str and "campaign_performance" not in stmt_str:
                return MagicMock(all=MagicMock(return_value=[]))
            return MagicMock(
                scalars=MagicMock(
                    return_value=MagicMock(all=MagicMock(return_value=[]))
                )
            )

    engine = ProactiveEngine(session_factory=lambda: _EmptySession())

    summary = await engine.load_live_performance_summary(brand_id, days=30)
    assert summary == ""
