"""Phase I4 tests — Performance Advisor Intelligence.

Tests that the Performance Engine produces rich, decision-oriented output:
- explain() returns root_cause, business_impact, what_changed, corrective_actions
- recommend() returns categorised, quick_wins, opportunities, expected_business_impact
- tell_story() returns kpis, trend, alerts
- forecast() returns projections with confidence intervals
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prachar_shared.marketing_intelligence.performance_engine import (
    BENCHMARKS,
    PerformanceEngine,
)


def _make_perf_row(
    d: date,
    impressions: int = 1000,
    clicks: int = 20,
    conversions: int = 2,
    spend: float = 100.0,
    revenue: float = 300.0,
    channel: str = "google_ads",
):
    """Create a mock performance row."""
    row = MagicMock()
    row.date = d
    row.impressions = impressions
    row.clicks = clicks
    row.conversions = conversions
    row.spend = spend
    row.revenue = revenue
    row.channel = channel
    return row


def _make_data(days: int = 14, convs: int = 2) -> list:
    """Create N days of performance data."""
    today = date.today()
    return [_make_perf_row(today - timedelta(days=i), conversions=convs) for i in range(days)]


class TestExplainIntelligence:
    """explain() returns rich root-cause analysis."""

    async def test_explain_returns_root_cause(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.explain("test-campaign", 30)
        assert "root_cause" in result
        assert isinstance(result["root_cause"], str)

    async def test_explain_returns_business_impact(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.explain("test-campaign", 30)
        assert "business_impact" in result
        impact = result["business_impact"]
        assert "level" in impact
        assert "summary" in impact
        assert "revenue" in impact
        assert "spend" in impact
        assert "net" in impact

    async def test_explain_returns_what_changed(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.explain("test-campaign", 30)
        assert "what_changed" in result
        assert "summary" in result["what_changed"]
        assert "changes" in result["what_changed"]

    async def test_explain_returns_corrective_actions(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14, convs=0)  # poor performance → corrective actions
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.explain("test-campaign", 30)
        assert "corrective_actions" in result
        assert isinstance(result["corrective_actions"], list)

    async def test_explain_returns_confidence(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.explain("test-campaign", 30)
        assert "confidence" in result
        assert result["confidence"] in ("high", "medium", "low")

    async def test_explain_empty_data_returns_note(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=[]):
            result = await engine.explain("test-campaign", 30)
        assert result["likely_causes"] == []
        assert "note" in result


class TestRecommendIntelligence:
    """recommend() returns categorised, prioritised, measurable recommendations."""

    async def test_recommend_returns_categorised(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            with patch.object(engine, "explain", new_callable=AsyncMock, return_value={"likely_causes": []}):
                result = await engine.recommend("test-campaign", 30)
        assert "categorised" in result
        assert isinstance(result["categorised"], dict)

    async def test_recommend_returns_quick_wins(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            with patch.object(engine, "explain", new_callable=AsyncMock, return_value={"likely_causes": [{"cause": "creative_fatigue"}]}):
                result = await engine.recommend("test-campaign", 30)
        assert "quick_wins" in result
        assert isinstance(result["quick_wins"], list)

    async def test_recommend_returns_opportunities(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            with patch.object(engine, "explain", new_callable=AsyncMock, return_value={"likely_causes": []}):
                result = await engine.recommend("test-campaign", 30)
        assert "opportunities" in result
        assert isinstance(result["opportunities"], list)

    async def test_recommend_returns_expected_business_impact(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            with patch.object(engine, "explain", new_callable=AsyncMock, return_value={"likely_causes": []}):
                result = await engine.recommend("test-campaign", 30)
        assert "expected_business_impact" in result
        impact = result["expected_business_impact"]
        assert "estimated_revenue_lift" in impact
        assert "estimated_conversion_lift" in impact
        assert "timeframe" in impact

    async def test_recommend_empty_data_returns_note(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=[]):
            with patch.object(engine, "explain", new_callable=AsyncMock, return_value={"likely_causes": []}):
                result = await engine.recommend("test-campaign", 30)
        assert result["recommendations"] == []
        assert "note" in result


class TestStoryIntelligence:
    """tell_story() returns KPIs, trend, and alerts."""

    async def test_story_returns_kpis(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.tell_story("test-campaign", 30)
        assert "kpis" in result
        assert isinstance(result["kpis"], list)
        assert len(result["kpis"]) > 0

    async def test_story_returns_trend(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.tell_story("test-campaign", 30)
        assert "trend" in result
        assert "direction" in result["trend"]
        assert "description" in result["trend"]

    async def test_story_returns_alerts(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.tell_story("test-campaign", 30)
        assert "alerts" in result
        assert isinstance(result["alerts"], list)

    async def test_story_alert_for_zero_conversions(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14, convs=0)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.tell_story("test-campaign", 30)
        alerts = result["alerts"]
        assert any(a["severity"] == "critical" for a in alerts)

    async def test_story_empty_data_returns_collecting(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=[]):
            result = await engine.tell_story("test-campaign", 30)
        assert "still collecting" in result["headline"].lower()


class TestForecast:
    """forecast() returns projections with confidence intervals."""

    async def test_forecast_returns_projections(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.forecast("test-campaign", days_ahead=7)
        assert "projections" in result
        projections = result["projections"]
        assert "conversions" in projections
        assert "reach" in projections
        assert "spend" in projections

    async def test_forecast_has_confidence_intervals(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.forecast("test-campaign", days_ahead=7)
        convs = result["projections"]["conversions"]
        assert "optimistic" in convs
        assert "realistic" in convs
        assert "pessimistic" in convs
        assert convs["optimistic"] >= convs["realistic"] >= convs["pessimistic"]

    async def test_forecast_returns_confidence_level(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.forecast("test-campaign", days_ahead=7)
        assert "confidence" in result
        assert result["confidence"] in ("high", "medium", "low")

    async def test_forecast_returns_inflection_points(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.forecast("test-campaign", days_ahead=7)
        assert "inflection_points" in result
        assert isinstance(result["inflection_points"], list)

    async def test_forecast_empty_data_returns_note(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=[]):
            result = await engine.forecast("test-campaign", days_ahead=7)
        assert "note" in result

    async def test_forecast_insufficient_data_returns_note(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(2)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.forecast("test-campaign", days_ahead=7)
        assert "note" in result

    async def test_forecast_expected_cpa(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        data = _make_data(14)
        with patch.object(engine, "_load_performance", new_callable=AsyncMock, return_value=data):
            result = await engine.forecast("test-campaign", days_ahead=7)
        assert "expected_cpa" in result["projections"]
        assert result["projections"]["expected_cpa"] > 0


class TestHelperMethods:
    """Test the internal helper methods directly."""

    def test_identify_root_cause_empty(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        result = engine._identify_root_cause([])
        assert "No significant issues" in result

    def test_identify_root_cause_with_causes(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        causes = [
            {"cause": "creative_fatigue", "confidence": "high", "evidence": "CTR declining 30%"},
            {"cause": "budget_too_low", "confidence": "medium", "evidence": "Impressions below benchmark"},
        ]
        result = engine._identify_root_cause(causes)
        assert "Creative Fatigue" in result

    def test_assess_business_impact_positive(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        metrics = {"avg_roas": 5.0, "avg_ctr": 0.03, "conversions": 50, "spend": 1000.0, "revenue": 5000.0}
        result = engine._assess_business_impact(metrics, [])
        assert result["level"] == "positive"
        assert result["net"] == 4000.0

    def test_assess_business_impact_negative(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        metrics = {"avg_roas": 1.0, "avg_ctr": 0.01, "conversions": 5, "spend": 1000.0, "revenue": 1000.0}
        result = engine._assess_business_impact(metrics, [])
        assert result["level"] == "negative"

    def test_categorise_recommendations(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        recs = [
            {"action": "Refresh creative assets", "priority": "high"},
            {"action": "Pause losing audience segments", "priority": "medium"},
            {"action": "Increase daily budget", "priority": "high"},
            {"action": "Test a new hook variant", "priority": "low"},
        ]
        result = engine._categorise_recommendations(recs)
        assert "creative" in result
        assert "targeting" in result
        assert "budget" in result

    def test_extract_quick_wins(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        recs = [
            {"action": "Refresh creative assets", "priority": "high"},
            {"action": "Test a new hook variant", "priority": "low"},
        ]
        result = engine._extract_quick_wins(recs)
        assert len(result) == 1
        assert result[0]["time_to_implement"] == "< 1 hour"

    def test_build_kpi_grid(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        metrics = {"impressions": 12000, "conversions": 45, "avg_ctr": 0.032, "avg_roas": 4.5, "spend": 5000.0}
        kpis = engine._build_kpi_grid(metrics, "up")
        assert len(kpis) == 5
        labels = [k["label"] for k in kpis]
        assert "Reach" in labels
        assert "Enquiries" in labels

    def test_build_alerts_low_roas(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        metrics = {"avg_roas": 2.0, "avg_ctr": 0.03, "spend": 1000.0, "conversions": 5}
        alerts = engine._build_alerts(metrics, [])
        assert any(a["severity"] == "warning" and "ROAS" in a["title"] for a in alerts)

    def test_build_alerts_zero_conversions(self):
        engine = PerformanceEngine(session_factory=lambda: None)
        metrics = {"avg_roas": 0, "avg_ctr": 0.01, "spend": 500.0, "conversions": 0}
        alerts = engine._build_alerts(metrics, [])
        assert any(a["severity"] == "critical" and "zero conversions" in a["title"] for a in alerts)
