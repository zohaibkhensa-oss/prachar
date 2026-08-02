"""Tests for the Performance Analysis Engine (P4.3).

Run with:
    .venv/bin/python -m pytest packages/shared/prachar_shared/marketing_intelligence/tests/test_performance_engine.py -q
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_shared.marketing_intelligence.performance_engine import (
    BENCHMARKS,
    PerformanceEngine,
    PerformanceSummary,
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
    ctr = clicks / impressions if impressions else 0.0
    cpa = spend / conversions if conversions else 0.0
    roas = revenue / spend if spend else 0.0
    return SimpleNamespace(
        date=d,
        impressions=impressions,
        clicks=clicks,
        conversions=conversions,
        spend=spend,
        revenue=revenue,
        ctr=ctr,
        cpa=cpa,
        roas=roas,
        channel=channel,
    )


class FakeSession:
    """Async session that returns a pre-seeded list of rows."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=rows)))))


def _engine_with_rows(rows: list[Any]) -> PerformanceEngine:
    session = FakeSession(rows)
    return PerformanceEngine(session_factory=lambda: session)


# ─── analyse: full result ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyse_returns_performance_summary_with_all_fields():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()), days=30)

    assert isinstance(summary, PerformanceSummary)
    d = summary.to_dict()
    for key in (
        "campaign_id",
        "summary",
        "top_metrics",
        "trend",
        "notable_days",
        "benchmark_comparison",
    ):
        assert key in d
    assert isinstance(d["summary"], str) and d["summary"]
    assert isinstance(d["top_metrics"], dict)
    assert d["trend"] in ("up", "down", "flat")
    assert isinstance(d["notable_days"], list)
    assert isinstance(d["benchmark_comparison"], dict)


@pytest.mark.asyncio
async def test_analyse_top_metrics_aggregation():
    today = date.today()
    rows = [
        _row(today - timedelta(days=1), impressions=10_000, clicks=200, conversions=20, spend=200.0, revenue=600.0),
        _row(today - timedelta(days=2), impressions=5_000, clicks=100, conversions=10, spend=100.0, revenue=300.0),
    ]
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    tm = summary.top_metrics

    assert tm["impressions"] == 15_000
    assert tm["clicks"] == 300
    assert tm["conversions"] == 30
    assert tm["spend"] == 300.0
    assert tm["revenue"] == 900.0
    # avg_ctr = 300 / 15000 = 0.02
    assert abs(tm["avg_ctr"] - 0.02) < 1e-6
    # avg_cpa = 300 / 30 = 10
    assert abs(tm["avg_cpa"] - 10.0) < 1e-6
    # avg_roas = 900 / 300 = 3
    assert abs(tm["avg_roas"] - 3.0) < 1e-4


# ─── trend ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trend_up():
    today = date.today()
    # previous 7 days low conversions, last 7 days high conversions
    rows = []
    for i in range(14, 7, -1):  # days -14..-8 (previous 7)
        rows.append(_row(today - timedelta(days=i), conversions=5))
    for i in range(7, 0, -1):  # days -7..-1 (last 7)
        rows.append(_row(today - timedelta(days=i), conversions=20))
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    assert summary.trend == "up"


@pytest.mark.asyncio
async def test_trend_down():
    today = date.today()
    rows = []
    for i in range(14, 7, -1):
        rows.append(_row(today - timedelta(days=i), conversions=20))
    for i in range(7, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=5))
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    assert summary.trend == "down"


@pytest.mark.asyncio
async def test_trend_flat():
    today = date.today()
    rows = []
    for i in range(14, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=10))
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    assert summary.trend == "flat"


def test_compute_trend_flat_with_insufficient_data():
    engine = PerformanceEngine(session_factory=lambda: None)
    today = date.today()
    single = [_row(today, conversions=10)]
    assert engine._compute_trend(single) == "flat"
    assert engine._compute_trend([]) == "flat"


# ─── notable days ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_notable_days_detects_spike():
    today = date.today()
    rows = []
    # 10 days at conversions=10, one day with conversions=100 (spike)
    for i in range(10, 0, -1):
        conv = 100 if i == 5 else 10
        rows.append(_row(today - timedelta(days=i), conversions=conv))
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    notable = summary.notable_days
    assert len(notable) >= 1
    spike = [n for n in notable if n["metric"] == "conversions" and "spike" in n["note"]]
    assert len(spike) >= 1
    assert spike[0]["value"] == 100


@pytest.mark.asyncio
async def test_notable_days_detects_drop():
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        conv = 1 if i == 5 else 10
        rows.append(_row(today - timedelta(days=i), conversions=conv))
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    notable = summary.notable_days
    drops = [n for n in notable if n["metric"] == "conversions" and "drop" in n["note"]]
    assert len(drops) >= 1
    assert drops[0]["value"] == 1


def test_find_notable_days_empty():
    engine = PerformanceEngine(session_factory=lambda: None)
    assert engine._find_notable_days([]) == []


# ─── benchmark comparison ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_benchmark_comparison_better_and_worse():
    today = date.today()
    # CTR = 300/10000 = 3% > 2% benchmark (better)
    # CPA = 200/30 = 6.67 < 10 benchmark (better)
    # ROAS = 600/200 = 3.0 == 3x benchmark (better, >=)
    rows = [_row(today - timedelta(days=1), impressions=10_000, clicks=300, conversions=30, spend=200.0, revenue=600.0)]
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    bc = summary.benchmark_comparison

    assert set(bc.keys()) == {"ctr", "cpa", "roas"}
    for m in bc:
        assert bc[m]["benchmark"] == BENCHMARKS[m]
        assert bc[m]["status"] in ("better", "worse", "unknown")
        assert "actual" in bc[m] and "difference" in bc[m]
    assert bc["ctr"]["status"] == "better"
    assert bc["cpa"]["status"] == "better"
    assert bc["roas"]["status"] == "better"


@pytest.mark.asyncio
async def test_benchmark_comparison_worse():
    today = date.today()
    # CTR = 100/10000 = 1% < 2% (worse)
    # CPA = 200/5 = 40 > 10 (worse)
    # ROAS = 100/200 = 0.5 < 3 (worse)
    rows = [_row(today - timedelta(days=1), impressions=10_000, clicks=100, conversions=5, spend=200.0, revenue=100.0)]
    engine = _engine_with_rows(rows)

    summary = await engine.analyse(str(uuid.uuid4()))
    bc = summary.benchmark_comparison
    assert bc["ctr"]["status"] == "worse"
    assert bc["cpa"]["status"] == "worse"
    assert bc["roas"]["status"] == "worse"


# ─── empty data ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyse_empty_campaign_returns_graceful_summary():
    engine = _engine_with_rows([])
    summary = await engine.analyse(str(uuid.uuid4()), days=30)

    assert isinstance(summary, PerformanceSummary)
    assert summary.trend == "flat"
    assert summary.top_metrics == {}
    assert summary.notable_days == []
    assert summary.benchmark_comparison == {}
    assert "No performance data" in summary.summary


# ─── to_dict ──────────────────────────────────────────────────────────────────


def test_performance_summary_to_dict_roundtrip():
    s = PerformanceSummary(
        campaign_id="abc",
        summary="hello",
        top_metrics={"conversions": 1},
        trend="up",
        notable_days=[{"date": "2026-01-01", "metric": "conversions", "value": 5, "note": "spike"}],
        benchmark_comparison={"ctr": {"actual": 0.03, "benchmark": 0.02, "difference": 0.01, "status": "better"}},
    )
    d = s.to_dict()
    assert d["campaign_id"] == "abc"
    assert d["trend"] == "up"
    assert d["notable_days"][0]["metric"] == "conversions"
    assert d["benchmark_comparison"]["ctr"]["status"] == "better"


# ─── explain: root-cause analysis (P4.4) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_explain_returns_likely_causes_with_required_fields():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.explain(str(uuid.uuid4()), days=30)

    assert "campaign_id" in result
    assert "likely_causes" in result
    assert isinstance(result["likely_causes"], list)
    for cause in result["likely_causes"]:
        assert "cause" in cause
        assert "evidence" in cause and isinstance(cause["evidence"], str)
        assert cause["confidence"] in ("high", "medium", "low")


@pytest.mark.asyncio
async def test_explain_detects_creative_fatigue():
    today = date.today()
    rows = []
    # Early days: high CTR (10%), late days: low CTR (1%) → fatigue.
    for i in range(10, 0, -1):
        if i > 5:
            rows.append(_row(today - timedelta(days=i), impressions=10_000, clicks=1_000))
        else:
            rows.append(_row(today - timedelta(days=i), impressions=10_000, clicks=100))
    engine = _engine_with_rows(rows)

    result = await engine.explain(str(uuid.uuid4()), days=30)
    causes = {c["cause"] for c in result["likely_causes"]}
    assert "creative_fatigue" in causes
    fatigue = next(c for c in result["likely_causes"] if c["cause"] == "creative_fatigue")
    assert "CTR declined" in fatigue["evidence"]


@pytest.mark.asyncio
async def test_explain_detects_audience_saturation():
    today = date.today()
    rows = []
    # Early days: high impressions, late days: low impressions, spend stable.
    for i in range(10, 0, -1):
        if i > 5:
            rows.append(_row(today - timedelta(days=i), impressions=20_000, spend=200.0))
        else:
            rows.append(_row(today - timedelta(days=i), impressions=8_000, spend=200.0))
    engine = _engine_with_rows(rows)

    result = await engine.explain(str(uuid.uuid4()), days=30)
    causes = {c["cause"] for c in result["likely_causes"]}
    assert "audience_saturation" in causes


@pytest.mark.asyncio
async def test_explain_detects_budget_too_low():
    today = date.today()
    # Very low impressions → budget_too_low.
    rows = [_row(today - timedelta(days=i), impressions=1_000) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.explain(str(uuid.uuid4()), days=30)
    causes = {c["cause"] for c in result["likely_causes"]}
    assert "budget_too_low" in causes


@pytest.mark.asyncio
async def test_explain_detects_competitor_activity():
    today = date.today()
    rows = []
    # Stable impressions then a sudden 50% drop with flat spend.
    for i in range(10, 3, -1):
        rows.append(_row(today - timedelta(days=i), impressions=10_000, spend=200.0))
    rows.append(_row(today - timedelta(days=3), impressions=4_000, spend=200.0))
    rows.append(_row(today - timedelta(days=2), impressions=10_000, spend=200.0))
    rows.append(_row(today - timedelta(days=1), impressions=10_000, spend=200.0))
    engine = _engine_with_rows(rows)

    result = await engine.explain(str(uuid.uuid4()), days=30)
    causes = {c["cause"] for c in result["likely_causes"]}
    assert "competitor_activity" in causes


@pytest.mark.asyncio
async def test_explain_empty_data_returns_empty_causes():
    engine = _engine_with_rows([])
    result = await engine.explain(str(uuid.uuid4()), days=30)

    assert result["likely_causes"] == []
    assert "No performance data" in result["note"]


@pytest.mark.asyncio
async def test_explain_no_false_positives_on_healthy_campaign():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.explain(str(uuid.uuid4()), days=30)
    # A healthy, stable campaign should not flag creative_fatigue or saturation.
    causes = {c["cause"] for c in result["likely_causes"]}
    assert "creative_fatigue" not in causes
    assert "audience_saturation" not in causes


# ─── recommend: "What next" recommendations (P4.5) ────────────────────────────


@pytest.mark.asyncio
async def test_recommend_returns_recommendations_with_required_fields():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.recommend(str(uuid.uuid4()), days=30)

    assert "campaign_id" in result
    assert "recommendations" in result
    assert isinstance(result["recommendations"], list)
    for rec in result["recommendations"]:
        assert "action" in rec and isinstance(rec["action"], str)
        assert "expected_impact" in rec and isinstance(rec["expected_impact"], str)
        assert rec["priority"] in ("high", "medium", "low")


@pytest.mark.asyncio
async def test_recommend_scales_winning_creative_when_roas_above_benchmark():
    today = date.today()
    # ROAS = 1200/200 = 6x > 3x benchmark.
    rows = [_row(today - timedelta(days=i), spend=200.0, revenue=1200.0, impressions=60_000) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.recommend(str(uuid.uuid4()), days=30)
    actions = [r["action"] for r in result["recommendations"]]
    assert any("Scale winning" in a for a in actions)


@pytest.mark.asyncio
async def test_recommend_refreshes_creative_when_fatigue_detected():
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        if i > 5:
            rows.append(_row(today - timedelta(days=i), impressions=10_000, clicks=1_000))
        else:
            rows.append(_row(today - timedelta(days=i), impressions=10_000, clicks=100))
    engine = _engine_with_rows(rows)

    result = await engine.recommend(str(uuid.uuid4()), days=30)
    actions = [r["action"] for r in result["recommendations"]]
    assert any("Refresh creative" in a for a in actions)


@pytest.mark.asyncio
async def test_recommend_increases_budget_when_roas_good_impressions_low():
    today = date.today()
    # ROAS = 600/200 = 3x (>= benchmark), impressions low.
    rows = [_row(today - timedelta(days=i), impressions=2_000, spend=200.0, revenue=600.0) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.recommend(str(uuid.uuid4()), days=30)
    actions = [r["action"] for r in result["recommendations"]]
    assert any("Increase" in a and "budget" in a for a in actions)


@pytest.mark.asyncio
async def test_recommend_pauses_losing_audience_when_ctr_below_benchmark():
    today = date.today()
    # CTR = 50/10000 = 0.5% < 2% benchmark.
    rows = [_row(today - timedelta(days=i), impressions=10_000, clicks=50, spend=200.0, revenue=600.0) for i in range(10)]
    engine = _engine_with_rows(rows)

    result = await engine.recommend(str(uuid.uuid4()), days=30)
    actions = [r["action"] for r in result["recommendations"]]
    assert any("Pause" in a for a in actions)


@pytest.mark.asyncio
async def test_recommend_empty_data_returns_empty_recommendations():
    engine = _engine_with_rows([])
    result = await engine.recommend(str(uuid.uuid4()), days=30)

    assert result["recommendations"] == []
    assert "No performance data" in result["note"]


# ─── tell_story: narrative story (A.5.1) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_tell_story_returns_required_fields():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    for key in ("campaign_id", "headline", "paragraphs", "highlights",
                "platform_breakdown", "time_insights"):
        assert key in story, f"missing key: {key}"
    assert isinstance(story["headline"], str) and story["headline"]
    assert isinstance(story["paragraphs"], list)
    assert isinstance(story["highlights"], list)
    assert isinstance(story["platform_breakdown"], list)
    assert isinstance(story["time_insights"], list)


@pytest.mark.asyncio
async def test_tell_story_empty_data_returns_collecting_message():
    engine = _engine_with_rows([])
    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert "collecting data" in story["headline"].lower()
    assert len(story["paragraphs"]) >= 1
    assert story["highlights"] == []
    assert story["platform_breakdown"] == []
    assert story["time_insights"] == []


@pytest.mark.asyncio
async def test_tell_story_headline_includes_enquiry_count():
    today = date.today()
    rows = []
    for i in range(14, 7, -1):
        rows.append(_row(today - timedelta(days=i), conversions=5))
    for i in range(7, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=20))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    # This week's conversions = 7 * 20 = 140
    assert "140" in story["headline"]
    assert "up" in story["headline"].lower()


@pytest.mark.asyncio
async def test_tell_story_headline_down_trend():
    today = date.today()
    rows = []
    for i in range(14, 7, -1):
        rows.append(_row(today - timedelta(days=i), conversions=20))
    for i in range(7, 0, -1):
        rows.append(_row(today - timedelta(days=i), conversions=5))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    # This week = 7 * 5 = 35, last week = 7 * 20 = 140, diff = -105
    assert "35" in story["headline"]
    assert "down" in story["headline"].lower()


@pytest.mark.asyncio
async def test_tell_story_dejargonises_metrics_in_highlights():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)
    highlight_metrics = [h["metric"] for h in story["highlights"]]

    # Should NOT contain jargon.
    assert not any("ROAS" in m for m in highlight_metrics)
    assert not any("CPA" in m for m in highlight_metrics)
    assert not any("CTR" in m for m in highlight_metrics)
    # Should contain de-jargonised names.
    assert any("Revenue per" in m for m in highlight_metrics)
    assert any("Cost per" in m for m in highlight_metrics)
    assert any("Click rate" in m for m in highlight_metrics)


@pytest.mark.asyncio
async def test_tell_story_highlights_have_value_and_insight():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(10)]
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    for h in story["highlights"]:
        assert "metric" in h and isinstance(h["metric"], str)
        assert "value" in h and isinstance(h["value"], str)
        assert "insight" in h and isinstance(h["insight"], str)


@pytest.mark.asyncio
async def test_tell_story_platform_breakdown_multi_channel():
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        rows.append(_row(today - timedelta(days=i), channel="instagram", conversions=30, clicks=300))
        rows.append(_row(today - timedelta(days=i), channel="whatsapp", conversions=10, clicks=50))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert len(story["platform_breakdown"]) == 2
    # Instagram should have the larger share (30/(30+10) = 75%).
    ig = next(p for p in story["platform_breakdown"] if p["platform"] == "Instagram")
    assert ig["share"] > 0.7
    # WhatsApp should have higher conversion rate (10/50 = 20% vs 30/300 = 10%).
    wa = next(p for p in story["platform_breakdown"] if p["platform"] == "WhatsApp")
    assert wa["conversion_rate"] > ig["conversion_rate"]
    # Sorted by share descending.
    assert story["platform_breakdown"][0]["share"] >= story["platform_breakdown"][1]["share"]


@pytest.mark.asyncio
async def test_tell_story_platform_breakdown_single_channel_skipped():
    today = date.today()
    rows = [_row(today - timedelta(days=i), channel="google_ads") for i in range(10)]
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    # Single channel → no platform breakdown.
    assert len(story["platform_breakdown"]) == 1
    # Paragraphs should NOT contain platform comparison text.
    platform_para = [p for p in story["paragraphs"] if "star performer" in p]
    assert len(platform_para) == 0


@pytest.mark.asyncio
async def test_tell_story_platform_breakdown_no_channel_skipped():
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        r = _row(today - timedelta(days=i))
        r.channel = None
        rows.append(r)
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert story["platform_breakdown"] == []


@pytest.mark.asyncio
async def test_tell_story_time_insights_weekend_outperforms():
    today = date.today()
    rows = []
    # Build 14 days where weekends have much higher conversions.
    for i in range(14, 0, -1):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:  # weekend
            rows.append(_row(d, conversions=50))
        else:
            rows.append(_row(d, conversions=10))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert len(story["time_insights"]) >= 1
    assert "weekend" in story["time_insights"][0]["insight"].lower()
    assert "outperform" in story["time_insights"][0]["insight"].lower()


@pytest.mark.asyncio
async def test_tell_story_time_insights_weekday_outperforms():
    today = date.today()
    rows = []
    for i in range(14, 0, -1):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            rows.append(_row(d, conversions=5))
        else:
            rows.append(_row(d, conversions=30))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert len(story["time_insights"]) >= 1
    assert "weekday" in story["time_insights"][0]["insight"].lower()


@pytest.mark.asyncio
async def test_tell_story_time_insights_skipped_when_insufficient_data():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(3)]
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert story["time_insights"] == []


@pytest.mark.asyncio
async def test_tell_story_paragraphs_are_narrative():
    today = date.today()
    rows = [_row(today - timedelta(days=i)) for i in range(14)]
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    # Should have at least one paragraph.
    assert len(story["paragraphs"]) >= 1
    # First paragraph should be a sentence (not a number).
    assert len(story["paragraphs"][0]) > 20
    # Should not contain raw jargon like "ROAS 3.00x".
    for p in story["paragraphs"]:
        assert "ROAS" not in p
        assert "CPA" not in p


@pytest.mark.asyncio
async def test_tell_story_platform_names_dejargonised():
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        rows.append(_row(today - timedelta(days=i), channel="google_ads", conversions=10))
        rows.append(_row(today - timedelta(days=i), channel="meta_ads", conversions=20))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    platforms = [p["platform"] for p in story["platform_breakdown"]]
    # Should use friendly names, not raw channel strings.
    assert "Google Ads" in platforms
    assert "Meta Ads" in platforms
    assert not any("google_ads" in p.lower() for p in platforms)


# ─── C.2.2: Live data in platform breakdown ───────────────────────────────────


@pytest.mark.asyncio
async def test_tell_story_platform_breakdown_includes_live_data_fields():
    """Platform breakdown should include live data fields: reach,
    engagement_rate, spend, roas (C.2.2)."""
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        rows.append(_row(
            today - timedelta(days=i), channel="instagram",
            impressions=12_000, clicks=360, conversions=30,
            spend=500.0, revenue=1500.0,
        ))
        rows.append(_row(
            today - timedelta(days=i), channel="whatsapp",
            impressions=0, clicks=100, conversions=12,
            spend=0.0, revenue=0.0,
        ))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    assert len(story["platform_breakdown"]) == 2
    for p in story["platform_breakdown"]:
        assert "reach" in p, f"missing 'reach' in {p}"
        assert "engagement_rate" in p, f"missing 'engagement_rate' in {p}"
        assert "spend" in p, f"missing 'spend' in {p}"
        assert "roas" in p, f"missing 'roas' in {p}"
        assert "conversions" in p
        assert "share" in p
        assert "conversion_rate" in p

    # Instagram should have reach = 12K * 10 = 120000.
    ig = next(p for p in story["platform_breakdown"] if p["platform"] == "Instagram")
    assert ig["reach"] == 120_000
    assert ig["spend"] == 5000.0
    assert ig["roas"] == 3.0  # 15000 / 5000


@pytest.mark.asyncio
async def test_tell_story_platform_paragraph_includes_reach():
    """The narrative paragraph should reference live reach data for the
    top platform (C.2.2)."""
    today = date.today()
    rows = []
    for i in range(10, 0, -1):
        rows.append(_row(
            today - timedelta(days=i), channel="instagram",
            impressions=15_000, clicks=450, conversions=30,
        ))
        rows.append(_row(
            today - timedelta(days=i), channel="whatsapp",
            impressions=0, clicks=50, conversions=10,
        ))
    engine = _engine_with_rows(rows)

    story = await engine.tell_story(str(uuid.uuid4()), days=30)

    # Find the platform paragraph.
    platform_para = [p for p in story["paragraphs"] if "star performer" in p]
    assert len(platform_para) == 1
    # Should mention reach.
    assert "reached" in platform_para[0].lower() or "reach" in platform_para[0].lower()
