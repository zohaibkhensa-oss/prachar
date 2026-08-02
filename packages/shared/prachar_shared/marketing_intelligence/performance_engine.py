"""Performance Analysis Engine — the "What happened" layer (P4.3).

Given a campaign id, ``PerformanceEngine.analyse`` loads the daily
``CampaignPerformance`` rows (written by the P4.2 ingestion worker) and
produces a ``PerformanceSummary`` describing:

* **summary** — a natural-language, executive-friendly sentence.
* **top_metrics** — aggregated totals / averages over the window.
* **trend** — ``up`` / ``down`` / ``flat`` comparing the last 7 days of
  conversions against the previous 7 days.
* **notable_days** — days where any core metric spiked or dropped by more
  than 20 % from the rolling average.
* **benchmark_comparison** — the campaign's CTR / CPA / ROAS measured
  against simple hardcoded industry benchmarks (CTR 2 %, CPA $10, ROAS 3x).

The engine is deliberately framework-light: it only needs a *session
factory* — a zero-arg callable that returns a SQLAlchemy session (sync or
async).  This keeps it trivially mockable in unit tests while still working
inside the FastAPI router where the session is provided by ``SessionDep``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Iterable

from sqlalchemy import select

logger = logging.getLogger(__name__)


# ─── Hardcoded industry benchmarks (P4.3 — replaced by real data later) ──────

BENCHMARKS: dict[str, float] = {
    "ctr": 0.02,   # 2 %
    "cpa": 10.0,   # $10
    "roas": 3.0,   # 3x
}

# Threshold for flagging a day as "notable" — deviation from the average.
NOTABLE_THRESHOLD = 0.20  # 20 %


# ─── Dataclass ───────────────────────────────────────────────────────────────


@dataclass
class PerformanceSummary:
    """Result of ``PerformanceEngine.analyse``.

    Attributes:
        campaign_id:          the analysed campaign id (stringified).
        summary:              natural-language summary string.
        top_metrics:          aggregated totals / averages for the window.
        trend:                ``up`` / ``down`` / ``flat``.
        notable_days:         list of ``{date, metric, value, note}`` dicts.
        benchmark_comparison: per-metric comparison to industry benchmarks.
    """

    campaign_id: str
    summary: str
    top_metrics: dict[str, Any]
    trend: str
    notable_days: list[dict[str, Any]]
    benchmark_comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "summary": self.summary,
            "top_metrics": self.top_metrics,
            "trend": self.trend,
            "notable_days": self.notable_days,
            "benchmark_comparison": self.benchmark_comparison,
        }


# ─── Engine ──────────────────────────────────────────────────────────────────


class PerformanceEngine:
    """Analyse campaign performance data and produce a ``PerformanceSummary``."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        """``session_factory`` is a zero-arg callable returning a SQLAlchemy
        session (async or sync).  The engine never opens/closes the session —
        the caller owns its lifecycle."""
        self.session_factory = session_factory

    # ── public API ───────────────────────────────────────────────────────────

    async def analyse(self, campaign_id: str, days: int = 30) -> PerformanceSummary:
        """Load performance data for ``campaign_id`` (last ``days`` days) and
        return a fully-populated ``PerformanceSummary``.

        Handles the empty-data case gracefully — a campaign with no
        performance rows yet returns a summary explaining that no data is
        available rather than raising.
        """
        data = await self._load_performance(campaign_id, days)
        cid = str(campaign_id)

        if not data:
            return PerformanceSummary(
                campaign_id=cid,
                summary=(
                    f"No performance data available for campaign {cid} in the "
                    f"last {days} days."
                ),
                top_metrics={},
                trend="flat",
                notable_days=[],
                benchmark_comparison={},
            )

        top_metrics = self._compute_top_metrics(data)
        trend = self._compute_trend(data)
        notable_days = self._find_notable_days(data)
        benchmark_comparison = self._benchmark_comparison(top_metrics)
        summary = self._build_summary(cid, top_metrics, trend, notable_days, days)

        return PerformanceSummary(
            campaign_id=cid,
            summary=summary,
            top_metrics=top_metrics,
            trend=trend,
            notable_days=notable_days,
            benchmark_comparison=benchmark_comparison,
        )

    # ── "Why" root-cause analysis (P4.4) ──────────────────────────────────────

    async def explain(self, campaign_id: str, days: int = 30) -> dict[str, Any]:
        """Return *likely causes* explaining the campaign's performance.

        Each cause is a dict ``{cause, evidence, confidence}`` where
        ``confidence`` is one of ``high`` / ``medium`` / ``low``.

        Detected causes (data-driven heuristics, no AI needed):

        * ``creative_fatigue`` — CTR is declining over time.
        * ``audience_saturation`` — impressions declining while spend stays
          stable (the audience pool is exhausted).
        * ``budget_too_low`` — impressions are low relative to the benchmark.
        * ``seasonality`` — performance in this period differs markedly from
          the campaign's own longer-term average.
        * ``competitor_activity`` — a sudden drop in impressions/clicks with no
          corresponding budget change.

        Handles empty data gracefully — returns an empty ``likely_causes``
        list with a note.
        """
        data = await self._load_performance(campaign_id, days)
        cid = str(campaign_id)

        if not data:
            return {
                "campaign_id": cid,
                "likely_causes": [],
                "note": (
                    f"No performance data available for campaign {cid} in the "
                    f"last {days} days."
                ),
            }

        daily = self._daily_totals(data)
        sorted_days = sorted(daily.items(), key=lambda kv: kv[0])
        top_metrics = self._compute_top_metrics(data)

        causes: list[dict[str, Any]] = []

        # creative_fatigue — declining CTR over time.
        ctr_cause = self._detect_creative_fatigue(sorted_days)
        if ctr_cause:
            causes.append(ctr_cause)

        # audience_saturation — declining impressions with stable spend.
        sat_cause = self._detect_audience_saturation(sorted_days)
        if sat_cause:
            causes.append(sat_cause)

        # budget_too_low — low impressions relative to benchmark.
        budget_cause = self._detect_budget_too_low(top_metrics, len(data))
        if budget_cause:
            causes.append(budget_cause)

        # seasonality — compare recent window to longer-term average.
        season_cause = await self._detect_seasonality(campaign_id, days, top_metrics)
        if season_cause:
            causes.append(season_cause)

        # competitor_activity — sudden drop with no budget change.
        comp_cause = self._detect_competitor_activity(sorted_days)
        if comp_cause:
            causes.append(comp_cause)

        return {
            "campaign_id": cid,
            "likely_causes": causes,
            "root_cause": self._identify_root_cause(causes),
            "business_impact": self._assess_business_impact(top_metrics, causes),
            "what_changed": self._what_changed(sorted_days),
            "corrective_actions": self._corrective_actions(causes),
            "confidence": self._explain_confidence(causes, len(data)),
        }

    # ── "What next" recommendations (P4.5) ────────────────────────────────────

    async def recommend(self, campaign_id: str, days: int = 30) -> dict[str, Any]:
        """Return *recommendations* for what to do next with the campaign.

        Each recommendation is a dict ``{action, expected_impact, priority}``
        where ``priority`` is one of ``high`` / ``medium`` / ``low``.

        Recommendations are derived from the performance data and the
        ``explain()`` root-cause analysis:

        * Scale winning creative — if ROAS > benchmark.
        * Pause losing audience — if CTR is declining.
        * Increase budget — if ROAS is good but impressions are low.
        * Refresh creative — if creative fatigue detected.
        * Test new hook — if A/B concepts available (always suggested as a
          low-priority experiment when there is active spend).

        Handles empty data gracefully — returns an empty ``recommendations``
        list with a note.
        """
        explanation = await self.explain(campaign_id, days)
        data = await self._load_performance(campaign_id, days)
        cid = str(campaign_id)

        if not data:
            return {
                "campaign_id": cid,
                "recommendations": [],
                "note": (
                    f"No performance data available for campaign {cid} in the "
                    f"last {days} days."
                ),
            }

        top_metrics = self._compute_top_metrics(data)
        causes = explanation.get("likely_causes", [])
        cause_names = {c["cause"] for c in causes}

        recs: list[dict[str, Any]] = []
        roas = top_metrics.get("avg_roas", 0.0)
        ctr = top_metrics.get("avg_ctr", 0.0)
        impressions = top_metrics.get("impressions", 0)
        spend = top_metrics.get("spend", 0.0)

        # Scale winning creative — ROAS above benchmark.
        if roas > BENCHMARKS["roas"]:
            recs.append(
                {
                    "action": "Scale winning creative",
                    "expected_impact": (
                        f"ROAS is {roas:.2f}x (above {BENCHMARKS['roas']}x benchmark); "
                        "increasing budget on top performers should lift revenue proportionally."
                    ),
                    "priority": "high",
                }
            )

        # Pause losing audience — CTR declining.
        if "creative_fatigue" in cause_names or ctr < BENCHMARKS["ctr"]:
            recs.append(
                {
                    "action": "Pause losing audience segments",
                    "expected_impact": (
                        "CTR is declining or below benchmark; pausing underperforming "
                        "segments will real spend toward better converters."
                    ),
                    "priority": "medium",
                }
            )

        # Increase budget — ROAS good but impressions low.
        if roas >= BENCHMARKS["roas"] and impressions < 50_000:
            recs.append(
                {
                    "action": "Increase daily budget",
                    "expected_impact": (
                        f"ROAS is healthy ({roas:.2f}x) but impressions are low "
                        f"({impressions}); more budget will unlock additional reach."
                    ),
                    "priority": "high",
                }
            )

        # Refresh creative — creative fatigue detected.
        if "creative_fatigue" in cause_names:
            recs.append(
                {
                    "action": "Refresh creative assets",
                    "expected_impact": (
                        "Creative fatigue detected (CTR declining); new creative "
                        "variants typically recover 15-30% of lost CTR."
                    ),
                    "priority": "high",
                }
            )

        # Test new hook — always suggest an experiment when there is spend.
        if spend > 0:
            recs.append(
                {
                    "action": "Test a new hook variant",
                    "expected_impact": (
                        "A/B testing a new opening hook against the current best "
                        "creative surfaces fresh winners and guards against fatigue."
                    ),
                    "priority": "low",
                }
            )

        return {
            "campaign_id": cid,
            "recommendations": recs,
            "categorised": self._categorise_recommendations(recs),
            "quick_wins": self._extract_quick_wins(recs),
            "opportunities": self._identify_opportunities(top_metrics, causes),
            "expected_business_impact": self._estimate_business_impact(top_metrics, recs),
        }

    # ── "Story" narrative (A.5.1) ─────────────────────────────────────────────

    # Friendly platform names — de-jargonised for the narrative.
    _PLATFORM_NAMES: dict[str, str] = {
        "google_ads": "Google Ads",
        "meta_ads": "Meta Ads",
        "instagram": "Instagram",
        "facebook": "Facebook",
        "whatsapp": "WhatsApp",
        "youtube": "YouTube",
        "tiktok": "TikTok",
        "linkedin": "LinkedIn",
        "pinterest": "Pinterest",
        "x": "X",
        "twitter": "X",
        "telegram": "Telegram",
        "line": "LINE",
        "vk": "VK",
        "reddit": "Reddit",
        "snapchat": "Snapchat",
        "microsoft_ads": "Microsoft Ads",
        "yandex": "Yandex",
        "naver": "Naver",
        "email": "Email",
        "sms": "SMS",
    }

    async def tell_story(self, campaign_id: str, days: int = 30) -> dict[str, Any]:
        """Generate a narrative *story* from the campaign's performance data.

        Instead of a dashboard of metrics, this returns a human-readable story:

        * **headline** — a single punchy sentence (the "newspaper headline").
        * **paragraphs** — 2-4 narrative paragraphs that flow naturally.
        * **highlights** — callout cards with ``{metric, value, insight}``.
        * **platform_breakdown** — per-platform share + conversion rate (only
          when multiple channels are present).
        * **time_insights** — weekend vs weekday comparison (only when enough
          data is available).

        All metrics are de-jargonised:
          ROAS → "Revenue per ₹100 spent", CPA → "Cost per new customer",
          CTR → "Click rate", Conversions → "New customers / enquiries".

        Handles empty data gracefully — returns a "still collecting" story.
        """
        data = await self._load_performance(campaign_id, days)
        cid = str(campaign_id)

        if not data:
            return {
                "campaign_id": cid,
                "headline": "We're still collecting data — check back in a few days.",
                "paragraphs": [
                    "Your campaign is live and we're gathering performance data. "
                    "Once we have a few days of results, we'll tell you the full story here."
                ],
                "highlights": [],
                "platform_breakdown": [],
                "time_insights": [],
            }

        top_metrics = self._compute_top_metrics(data)
        daily = self._daily_totals(data)
        sorted_days = sorted(daily.items(), key=lambda kv: kv[0])
        dates = [d for d, _ in sorted_days]
        trend = self._compute_trend(data)

        # ── Week-over-week conversion comparison for the headline ──────────────
        last_7 = dates[-7:]
        prev_7 = (
            dates[-14:-7]
            if len(dates) >= 14
            else dates[: max(0, len(dates) - 7)]
        )
        this_week_convs = sum(daily[d]["conversions"] for d in last_7)
        last_week_convs = sum(daily[d]["conversions"] for d in prev_7) if prev_7 else 0
        diff = this_week_convs - last_week_convs

        if last_week_convs == 0:
            if this_week_convs > 0:
                headline = (
                    f"This week's campaign brought in {this_week_convs} new enquiries."
                )
            else:
                headline = (
                    "Your campaign is running — no enquiries yet this week."
                )
        elif diff > 0:
            headline = (
                f"This week's campaign brought in {this_week_convs} new enquiries "
                f"— up {diff} from last week."
            )
        elif diff < 0:
            headline = (
                f"This week's campaign brought in {this_week_convs} new enquiries "
                f"— down {abs(diff)} from last week."
            )
        else:
            headline = (
                f"This week's campaign brought in {this_week_convs} new enquiries "
                f"— steady with last week."
            )

        # ── Platform breakdown ─────────────────────────────────────────────────
        platform_breakdown = self._platform_breakdown(data)
        has_platforms = len(platform_breakdown) >= 2

        # ── Time insights (weekend vs weekday) ─────────────────────────────────
        time_insights = self._time_insights(sorted_days)

        # ── Highlights (de-jargonised callout cards) ───────────────────────────
        highlights = self._build_highlights(top_metrics, this_week_convs, diff)

        # ── Narrative paragraphs ───────────────────────────────────────────────
        paragraphs: list[str] = []

        # Paragraph 1: The big picture.
        spend = top_metrics.get("spend", 0)
        revenue = top_metrics.get("revenue", 0)
        total_convs = top_metrics.get("conversions", 0)
        clicks = top_metrics.get("clicks", 0)
        impressions = top_metrics.get("impressions", 0)

        p1_parts: list[str] = []
        p1_parts.append(
            f"Over the last {len(dates)} days, your campaign reached "
            f"{impressions:,} people and turned that into {total_convs} enquiries."
        )
        if spend > 0:
            roas_per_100 = top_metrics.get("avg_roas", 0) * 100
            p1_parts.append(
                f"You spent ₹{spend:,.0f} to bring in ₹{revenue:,.0f} in revenue "
                f"— that's ₹{roas_per_100:.0f} back for every ₹100 spent."
            )
        paragraphs.append(" ".join(p1_parts))

        # Paragraph 2: Platform story.
        if has_platforms:
            top_platform = platform_breakdown[0]
            top_name = top_platform["platform"]
            top_share = top_platform["share"]
            # Find highest conversion rate platform.
            best_conv = max(
                platform_breakdown, key=lambda p: p.get("conversion_rate", 0)
            )
            best_name = best_conv["platform"]
            best_rate = best_conv.get("conversion_rate", 0) * 100

            p2 = f"{top_name} was your star performer, delivering {top_share * 100:.0f}% of enquiries."
            if best_name != top_name and best_rate > 0:
                p2 += (
                    f" {best_name} had the highest conversion rate at {best_rate:.0f}%."
                )
            # Add reach detail for the top platform.
            top_reach = top_platform.get("reach", 0)
            if top_reach > 0:
                reach_str = f"{top_reach / 1000:.0f}K" if top_reach >= 1000 else str(top_reach)
                p2 += f" {top_name} reached {reach_str} people."
            paragraphs.append(p2)
        elif len(platform_breakdown) == 1:
            # Single channel — skip platform breakdown gracefully.
            pass

        # Paragraph 3: Time insights.
        for ti in time_insights:
            paragraphs.append(ti["insight"])

        # Paragraph 4: Efficiency / what it means.
        if clicks > 0 and total_convs > 0:
            click_rate = top_metrics.get("avg_ctr", 0) * 100
            cost_per_customer = top_metrics.get("avg_cpa", 0)
            p4_parts: list[str] = []
            p4_parts.append(
                f"Your click rate is {click_rate:.1f}% — that's how many people "
                f"who saw the ad actually clicked."
            )
            if cost_per_customer > 0:
                p4_parts.append(
                    f"Each new customer cost you ₹{cost_per_customer:,.0f}."
                )
            paragraphs.append(" ".join(p4_parts))

        return {
            "campaign_id": cid,
            "headline": headline,
            "paragraphs": paragraphs,
            "highlights": highlights,
            "platform_breakdown": platform_breakdown,
            "time_insights": time_insights,
            "kpis": self._build_kpi_grid(top_metrics, trend),
            "trend": {"direction": trend, "description": self._trend_description(trend, sorted_days)},
            "alerts": self._build_alerts(top_metrics, sorted_days),
        }

    # ── forecasting (Phase I4) ─────────────────────────────────────────────────

    async def forecast(self, campaign_id: str, days_ahead: int = 7) -> dict[str, Any]:
        """Project key metrics for the next N days based on historical trends.

        Returns optimistic / realistic / pessimistic projections with
        confidence intervals and inflection point detection.

        Handles empty data gracefully — returns a "collecting" forecast.
        """
        data = await self._load_performance(campaign_id, 30)
        cid = str(campaign_id)

        if not data or len(data) < 3:
            return {
                "campaign_id": cid,
                "days_ahead": days_ahead,
                "projections": {},
                "note": "Not enough historical data to forecast. Need at least 3 days.",
            }

        daily = self._daily_totals(data)
        sorted_days = sorted(daily.items(), key=lambda kv: kv[0])
        recent_7 = sorted_days[-7:]
        prev_7 = sorted_days[-14:-7] if len(sorted_days) >= 14 else sorted_days[:max(0, len(sorted_days) - 7)]

        # Calculate daily averages
        avg_daily_convs = sum(d["conversions"] for _, d in recent_7) / max(1, len(recent_7))
        avg_daily_spend = sum(d["spend"] for _, d in recent_7) / max(1, len(recent_7))
        avg_daily_impressions = sum(d["impressions"] for _, d in recent_7) / max(1, len(recent_7))
        avg_daily_clicks = sum(d["clicks"] for _, d in recent_7) / max(1, len(recent_7))

        # Calculate trend velocity
        prev_convs = sum(d["conversions"] for _, d in prev_7) / max(1, len(prev_7)) if prev_7 else avg_daily_convs
        conv_velocity = (avg_daily_convs - prev_convs) / max(1.0, prev_convs) if prev_convs > 0 else 0.0

        # Projections
        realistic_convs = avg_daily_convs * days_ahead
        optimistic_convs = realistic_convs * (1 + max(0.1, conv_velocity + 0.1))
        pessimistic_convs = realistic_convs * (1 + min(-0.1, conv_velocity - 0.1))

        realistic_reach = avg_daily_impressions * days_ahead
        realistic_spend = avg_daily_spend * days_ahead

        # Inflection points — when a metric crosses a threshold
        inflection_points: list[dict[str, Any]] = []
        if conv_velocity > 0.15:
            inflection_points.append({
                "metric": "conversions",
                "event": "accelerating",
                "description": f"Conversions growing {conv_velocity:.0%} week-over-week",
                "implication": "Consider increasing budget to capture momentum",
            })
        elif conv_velocity < -0.15:
            inflection_points.append({
                "metric": "conversions",
                "event": "declining",
                "description": f"Conversions declining {abs(conv_velocity):.0%} week-over-week",
                "implication": "Refresh creative or adjust targeting urgently",
            })

        return {
            "campaign_id": cid,
            "days_ahead": days_ahead,
            "projections": {
                "conversions": {
                    "optimistic": round(optimistic_convs),
                    "realistic": round(realistic_convs),
                    "pessimistic": round(max(0, pessimistic_convs)),
                },
                "reach": {
                    "optimistic": round(realistic_reach * 1.2),
                    "realistic": round(realistic_reach),
                    "pessimistic": round(realistic_reach * 0.8),
                },
                "spend": round(realistic_spend, 2),
                "expected_cpa": round(realistic_spend / max(1, realistic_convs), 2),
            },
            "trend_velocity": round(conv_velocity, 4),
            "inflection_points": inflection_points,
            "confidence": "high" if len(sorted_days) >= 14 else "medium" if len(sorted_days) >= 7 else "low",
        }

    # ── Phase I4 helper methods ────────────────────────────────────────────────

    def _identify_root_cause(self, causes: list[dict[str, Any]]) -> str:
        """Identify the single most likely root cause from the list of causes."""
        if not causes:
            return "No significant issues detected — performance is within normal parameters."
        # Sort by confidence (high > medium > low)
        confidence_order = {"high": 3, "medium": 2, "low": 1}
        sorted_causes = sorted(causes, key=lambda c: confidence_order.get(c.get("confidence", "low"), 0), reverse=True)
        top = sorted_causes[0]
        return f"{top.get('cause', 'Unknown').replace('_', ' ').title()}: {top.get('evidence', '')}"

    def _assess_business_impact(self, top_metrics: dict[str, Any], causes: list[dict[str, Any]]) -> dict[str, Any]:
        """Assess the business impact of the current performance."""
        roas = top_metrics.get("avg_roas", 0.0)
        ctr = top_metrics.get("avg_ctr", 0.0)
        conversions = top_metrics.get("conversions", 0)
        spend = top_metrics.get("spend", 0.0)
        revenue = top_metrics.get("revenue", 0.0)

        if roas >= BENCHMARKS["roas"]:
            impact_level = "positive"
            summary = f"Campaign is profitable (ROAS {roas:.2f}x vs benchmark {BENCHMARKS['roas']}x). Revenue ₹{revenue:,.0f} from ₹{spend:,.0f} spend."
        elif roas >= BENCHMARKS["roas"] * 0.7:
            impact_level = "marginal"
            summary = f"Campaign is marginally profitable (ROAS {roas:.2f}x). Close to benchmark but not optimal."
        else:
            impact_level = "negative"
            summary = f"Campaign is underperforming (ROAS {roas:.2f}x vs benchmark {BENCHMARKS['roas']}x). Spending ₹{spend:,.0f} for ₹{revenue:,.0f} revenue."

        return {
            "level": impact_level,
            "summary": summary,
            "revenue": round(revenue, 2),
            "spend": round(spend, 2),
            "net": round(revenue - spend, 2),
            "conversions": conversions,
        }

    def _what_changed(self, sorted_days: list[tuple[date, dict[str, float]]]) -> dict[str, Any]:
        """Identify what changed in the recent period vs the previous period."""
        if len(sorted_days) < 4:
            return {"summary": "Not enough data to identify changes.", "changes": []}

        recent = sorted_days[-7:] if len(sorted_days) >= 7 else sorted_days[-3:]
        previous = sorted_days[-14:-7] if len(sorted_days) >= 14 else sorted_days[:-len(recent)]

        if not previous:
            return {"summary": "Establishing baseline — no comparison period yet.", "changes": []}

        changes: list[dict[str, Any]] = []
        for metric in ["impressions", "clicks", "conversions", "spend"]:
            recent_avg = sum(d[metric] for _, d in recent) / len(recent)
            prev_avg = sum(d[metric] for _, d in previous) / len(previous)
            if prev_avg > 0:
                pct_change = ((recent_avg - prev_avg) / prev_avg) * 100
                if abs(pct_change) > 10:  # Only report significant changes
                    direction = "increased" if pct_change > 0 else "decreased"
                    changes.append({
                        "metric": metric,
                        "direction": direction,
                        "change_pct": round(pct_change, 1),
                        "recent_avg": round(recent_avg, 2),
                        "previous_avg": round(prev_avg, 2),
                    })

        if not changes:
            return {"summary": "Performance is stable — no significant changes detected.", "changes": []}

        summary_parts = [f"{c['metric']} {c['direction']} {abs(c['change_pct'])}%" for c in changes]
        return {"summary": "Compared to last week: " + ", ".join(summary_parts) + ".", "changes": changes}

    def _corrective_actions(self, causes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate corrective actions based on identified causes."""
        actions: list[dict[str, Any]] = []
        for cause in causes:
            cause_name = cause.get("cause", "")
            if cause_name == "creative_fatigue":
                actions.append({
                    "title": "Refresh ad creative",
                    "action": "Generate 3 new creative variants and A/B test against current best performer.",
                    "priority": "high",
                    "expected_recovery": "15-30% CTR recovery within 3-5 days",
                })
            elif cause_name == "audience_saturation":
                actions.append({
                    "title": "Expand audience targeting",
                    "action": "Add lookalike audiences or expand interest targeting to reach new users.",
                    "priority": "high",
                    "expected_recovery": "20-40% impression recovery within 2-3 days",
                })
            elif cause_name == "budget_too_low":
                actions.append({
                    "title": "Increase daily budget",
                    "action": "Increase budget by 30-50% to unlock additional reach.",
                    "priority": "medium",
                    "expected_recovery": "Immediate impression increase proportional to budget",
                })
            elif cause_name == "seasonality":
                actions.append({
                    "title": "Adjust for seasonality",
                    "action": "Align messaging and offers with current seasonal context.",
                    "priority": "medium",
                    "expected_recovery": "Gradual improvement as seasonal factors shift",
                })
            elif cause_name == "competitor_activity":
                actions.append({
                    "title": "Counter competitor activity",
                    "action": "Differentiate messaging and increase bid competitiveness.",
                    "priority": "high",
                    "expected_recovery": "5-15% recovery within 5-7 days",
                })
        return actions

    def _explain_confidence(self, causes: list[dict[str, Any]], data_points: int) -> str:
        """Assess overall confidence in the explanation."""
        if not causes:
            return "high" if data_points >= 14 else "medium"
        high_count = sum(1 for c in causes if c.get("confidence") == "high")
        if high_count >= 2 and data_points >= 14:
            return "high"
        elif high_count >= 1 and data_points >= 7:
            return "medium"
        return "low"

    def _categorise_recommendations(self, recs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Group recommendations by category."""
        categories: dict[str, list[dict[str, Any]]] = {
            "creative": [],
            "targeting": [],
            "budget": [],
            "channel": [],
            "timing": [],
            "experiment": [],
        }
        for rec in recs:
            action = rec.get("action", "").lower()
            if "creative" in action or "hook" in action:
                categories["creative"].append(rec)
            elif "audience" in action or "segment" in action:
                categories["targeting"].append(rec)
            elif "budget" in action:
                categories["budget"].append(rec)
            elif "channel" in action:
                categories["channel"].append(rec)
            else:
                categories["experiment"].append(rec)
        return {k: v for k, v in categories.items() if v}

    def _extract_quick_wins(self, recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract quick wins — high-impact actions that can be done in < 1 hour."""
        quick_win_keywords = ["pause", "refresh", "increase budget", "test"]
        quick_wins: list[dict[str, Any]] = []
        for rec in recs:
            action = rec.get("action", "").lower()
            if any(kw in action for kw in quick_win_keywords) and rec.get("priority") in ("high", "medium"):
                quick_wins.append({
                    **rec,
                    "time_to_implement": "< 1 hour",
                    "why_quick": "Can be executed directly from the dashboard without creative production",
                })
        return quick_wins

    def _identify_opportunities(self, top_metrics: dict[str, Any], causes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Identify growth opportunities from the performance data."""
        opportunities: list[dict[str, Any]] = []
        roas = top_metrics.get("avg_roas", 0.0)
        ctr = top_metrics.get("avg_ctr", 0.0)
        impressions = top_metrics.get("impressions", 0)

        if roas > BENCHMARKS["roas"] * 1.5:
            opportunities.append({
                "title": "Scale aggressively",
                "impact": "high",
                "difficulty": "low",
                "timeframe": "this week",
                "description": f"ROAS is {roas:.2f}x — 50% above benchmark. Scaling budget could 2-3x revenue.",
            })
        if ctr > BENCHMARKS["ctr"] * 1.5 and impressions < 50_000:
            opportunities.append({
                "title": "Expand reach with proven creative",
                "impact": "high",
                "difficulty": "medium",
                "timeframe": "1-2 weeks",
                "description": f"CTR is {ctr:.2%} — well above benchmark. Expanding audience could unlock significant reach.",
            })
        if not any(c.get("cause") == "creative_fatigue" for c in causes):
            opportunities.append({
                "title": "Test bold creative variations",
                "impact": "medium",
                "difficulty": "medium",
                "timeframe": "1 week",
                "description": "Creative is performing well — good time to test bold variations to find new winners.",
            })
        return opportunities

    def _estimate_business_impact(self, top_metrics: dict[str, Any], recs: list[dict[str, Any]]) -> dict[str, Any]:
        """Estimate the business impact of implementing all recommendations."""
        roas = top_metrics.get("avg_roas", 0.0)
        spend = top_metrics.get("spend", 0.0)
        conversions = top_metrics.get("conversions", 0)
        revenue = top_metrics.get("revenue", 0.0)

        # Conservative estimate: 10-20% improvement from implementing recommendations
        est_revenue_lift = revenue * 0.15
        est_conversion_lift = conversions * 0.15

        return {
            "estimated_revenue_lift": round(est_revenue_lift, 2),
            "estimated_conversion_lift": round(est_conversion_lift),
            "estimated_roi_of_action": round(est_revenue_lift / max(1, spend) * 100, 1),
            "timeframe": "2-4 weeks",
            "assumption": "Based on typical improvement when implementing all recommendations",
        }

    def _build_kpi_grid(self, top_metrics: dict[str, Any], trend: str) -> list[dict[str, Any]]:
        """Build KPI grid for artefact emission."""
        kpis: list[dict[str, Any]] = []
        trend_arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(trend, "→")
        trend_label = {"up": "improving", "down": "declining", "flat": "stable"}.get(trend, "stable")

        if top_metrics.get("impressions"):
            kpis.append({"label": "Reach", "value": f"{top_metrics['impressions']:,}", "trend": trend_label})
        if top_metrics.get("conversions") is not None:
            kpis.append({"label": "Enquiries", "value": str(top_metrics.get("conversions", 0)), "trend": f"{trend_arrow} {trend_label}"})
        if top_metrics.get("avg_ctr"):
            kpis.append({"label": "Click Rate", "value": f"{top_metrics['avg_ctr']:.1%}", "trend": ""})
        if top_metrics.get("avg_roas"):
            kpis.append({"label": "Revenue / ₹100", "value": f"₹{top_metrics['avg_roas']*100:.0f}", "trend": ""})
        if top_metrics.get("spend"):
            kpis.append({"label": "Spend", "value": f"₹{top_metrics['spend']:,.0f}", "trend": ""})
        return kpis

    def _trend_description(self, trend: str, sorted_days: list[tuple[date, dict[str, float]]]) -> str:
        """Build a human-readable trend description."""
        if len(sorted_days) < 7:
            return "Still gathering data — trend will be available after 7 days."
        recent = sorted_days[-7:]
        prev = sorted_days[-14:-7] if len(sorted_days) >= 14 else []
        recent_convs = sum(d["conversions"] for _, d in recent)
        if prev:
            prev_convs = sum(d["conversions"] for _, d in prev)
            if prev_convs > 0:
                pct = ((recent_convs - prev_convs) / prev_convs) * 100
                direction = {"up": f"up {pct:.0f}%", "down": f"down {abs(pct):.0f}%", "flat": "stable"}.get(trend, "stable")
                return f"Conversions are {direction} compared to last week ({recent_convs} this week vs {prev_convs} last week)."
        return f"Conversions this week: {recent_convs}."

    def _build_alerts(self, top_metrics: dict[str, Any], sorted_days: list[tuple[date, dict[str, float]]]) -> list[dict[str, Any]]:
        """Build alerts for concerning metrics."""
        alerts: list[dict[str, Any]] = []
        roas = top_metrics.get("avg_roas", 0.0)
        ctr = top_metrics.get("avg_ctr", 0.0)
        spend = top_metrics.get("spend", 0.0)

        if roas > 0 and roas < BENCHMARKS["roas"] * 0.5:
            alerts.append({
                "severity": "critical",
                "title": "ROAS critically low",
                "detail": f"Revenue per ₹100 spent is ₹{roas*100:.0f} — below 50% of benchmark.",
                "action": "Pause underperforming channels and review creative immediately.",
            })
        elif roas > 0 and roas < BENCHMARKS["roas"]:
            alerts.append({
                "severity": "warning",
                "title": "ROAS below benchmark",
                "detail": f"Revenue per ₹100 spent is ₹{roas*100:.0f} — benchmark is ₹{BENCHMARKS['roas']*100:.0f}.",
                "action": "Review budget allocation and creative performance.",
            })

        if ctr > 0 and ctr < BENCHMARKS["ctr"] * 0.5:
            alerts.append({
                "severity": "warning",
                "title": "Click rate very low",
                "detail": f"Click rate is {ctr:.2%} — below 50% of benchmark.",
                "action": "Refresh creative — the audience isn't engaging with the current ads.",
            })

        if spend > 0 and top_metrics.get("conversions", 0) == 0:
            alerts.append({
                "severity": "critical",
                "title": "Spending with zero conversions",
                "detail": f"₹{spend:,.0f} spent with no enquiries. Campaign may not be reaching the right audience.",
                "action": "Pause campaign and review targeting + landing page.",
            })

        return alerts

    # ── story helpers (private) ────────────────────────────────────────────────

    def _platform_breakdown(self, data: list[Any]) -> list[dict[str, Any]]:
        """Aggregate performance by channel and compute share + conversion rate.

        Returns a list of ``{platform, share, conversion_rate, conversions,
        reach, engagement_rate, spend, roas}`` sorted by share descending.
        Returns an empty list if no channel info is present or there are no
        conversions.
        """
        per_channel: dict[str, dict[str, float]] = {}
        for r in data:
            ch = getattr(r, "channel", None)
            if not ch:
                continue
            ch = str(ch)
            bucket = per_channel.setdefault(
                ch,
                {
                    "impressions": 0,
                    "clicks": 0,
                    "conversions": 0,
                    "spend": 0.0,
                    "revenue": 0.0,
                },
            )
            bucket["impressions"] += int(r.impressions or 0)
            bucket["clicks"] += int(r.clicks or 0)
            bucket["conversions"] += int(r.conversions or 0)
            bucket["spend"] += float(r.spend or 0)
            bucket["revenue"] += float(r.revenue or 0)

        if not per_channel:
            return []

        total_convs = sum(b["conversions"] for b in per_channel.values())
        if total_convs == 0:
            return []

        result: list[dict[str, Any]] = []
        for ch, b in per_channel.items():
            share = b["conversions"] / total_convs if total_convs else 0.0
            conv_rate = self._safe_div(b["conversions"], b["clicks"])
            eng_rate = self._safe_div(b["clicks"], b["impressions"])
            roas = self._safe_div(b["revenue"], b["spend"])
            result.append(
                {
                    "platform": self._PLATFORM_NAMES.get(ch, ch.replace("_", " ").title()),
                    "share": round(share, 4),
                    "conversion_rate": round(conv_rate, 6),
                    "conversions": b["conversions"],
                    "reach": b["impressions"],
                    "engagement_rate": round(eng_rate, 6),
                    "spend": round(b["spend"], 2),
                    "roas": round(roas, 4),
                }
            )
        result.sort(key=lambda p: p["share"], reverse=True)
        return result

    def _time_insights(
        self, sorted_days: list[tuple[date, dict[str, float]]]
    ) -> list[dict[str, Any]]:
        """Compare weekend (Sat/Sun) vs weekday performance.

        Returns a list with at most one insight dict
        ``{period, insight}`` if a meaningful difference is found.
        Returns an empty list if there isn't enough data.
        """
        if len(sorted_days) < 7:
            return []

        weekend_convs: list[float] = []
        weekday_convs: list[float] = []
        for d, totals in sorted_days:
            if d.weekday() >= 5:  # Saturday=5, Sunday=6
                weekend_convs.append(totals["conversions"])
            else:
                weekday_convs.append(totals["conversions"])

        if not weekend_convs or not weekday_convs:
            return []

        weekend_avg = sum(weekend_convs) / len(weekend_convs)
        weekday_avg = sum(weekday_convs) / len(weekday_convs)

        if weekday_avg <= 0:
            return []

        delta_pct = (weekend_avg - weekday_avg) / weekday_avg
        # Only report if the difference is meaningful (>10%).
        if abs(delta_pct) < 0.10:
            return []

        if delta_pct > 0:
            insight = (
                f"Weekend campaigns outperformed weekdays by {delta_pct:.0%} — "
                f"your audience is more active on Saturdays and Sundays."
            )
        else:
            insight = (
                f"Weekday campaigns outperformed weekends by {abs(delta_pct):.0%} — "
                f"your audience is more active during the work week."
            )
        return [{"period": "weekend_vs_weekday", "insight": insight}]

    def _build_highlights(
        self,
        top_metrics: dict[str, Any],
        this_week_convs: int,
        diff: int,
    ) -> list[dict[str, Any]]:
        """Build de-jargonised highlight callout cards.

        Each card: ``{metric, value, insight}``.
        """
        highlights: list[dict[str, Any]] = []

        # New enquiries this week.
        if diff > 0:
            highlights.append(
                {
                    "metric": "New enquiries this week",
                    "value": str(this_week_convs),
                    "insight": f"Up {diff} from last week",
                }
            )
        elif diff < 0:
            highlights.append(
                {
                    "metric": "New enquiries this week",
                    "value": str(this_week_convs),
                    "insight": f"Down {abs(diff)} from last week",
                }
            )
        else:
            highlights.append(
                {
                    "metric": "New enquiries this week",
                    "value": str(this_week_convs),
                    "insight": "Steady with last week",
                }
            )

        # Revenue per ₹100 spent (de-jargonised ROAS).
        roas = top_metrics.get("avg_roas", 0)
        if roas > 0:
            per_100 = roas * 100
            highlights.append(
                {
                    "metric": "Revenue per ₹100 spent",
                    "value": f"₹{per_100:.0f}",
                    "insight": (
                        "Every ₹100 you put in brings this back"
                        if per_100 >= 100
                        else "You're spending more than you're earning — let's optimise"
                    ),
                }
            )

        # Cost per new customer (de-jargonised CPA).
        cpa = top_metrics.get("avg_cpa", 0)
        if cpa > 0:
            highlights.append(
                {
                    "metric": "Cost per new customer",
                    "value": f"₹{cpa:,.0f}",
                    "insight": "What it costs to acquire one enquiry",
                }
            )

        # Click rate (de-jargonised CTR).
        ctr = top_metrics.get("avg_ctr", 0)
        if ctr > 0:
            highlights.append(
                {
                    "metric": "Click rate",
                    "value": f"{ctr * 100:.1f}%",
                    "insight": "Share of people who clicked after seeing the ad",
                }
            )

        return highlights

    # ── root-cause detectors (private) ────────────────────────────────────────

    def _detect_creative_fatigue(
        self, sorted_days: list[tuple[date, dict[str, float]]]
    ) -> dict[str, Any] | None:
        """Detect declining CTR over time (creative fatigue).

        Compares the CTR of the first third of days against the last third.
        A drop of more than 20 % is flagged.
        """
        if len(sorted_days) < 3:
            return None

        n = len(sorted_days)
        first_third = sorted_days[: max(1, n // 3)]
        last_third = sorted_days[max(1, n - n // 3):]

        def _avg_ctr(days_slice: list[tuple[date, dict[str, float]]]) -> float:
            ctrs = [
                self._safe_div(d["clicks"], d["impressions"])
                for _, d in days_slice
                if d["impressions"] > 0
            ]
            return sum(ctrs) / len(ctrs) if ctrs else 0.0

        early_ctr = _avg_ctr(first_third)
        late_ctr = _avg_ctr(last_third)

        if early_ctr <= 0:
            return None

        delta = (late_ctr - early_ctr) / early_ctr
        if delta < -0.20:
            return {
                "cause": "creative_fatigue",
                "evidence": (
                    f"CTR declined from {early_ctr:.2%} (early period) to "
                    f"{late_ctr:.2%} (recent period), a {delta:+.0%} change — "
                    "classic creative fatigue signal."
                ),
                "confidence": "high" if delta < -0.40 else "medium",
            }
        return None

    def _detect_audience_saturation(
        self, sorted_days: list[tuple[date, dict[str, float]]]
    ) -> dict[str, Any] | None:
        """Detect declining impressions with stable spend (saturation).

        Compares the first third vs last third of days: impressions must drop
        >20 % while spend stays within ±15 %.
        """
        if len(sorted_days) < 3:
            return None

        n = len(sorted_days)
        first_third = sorted_days[: max(1, n // 3)]
        last_third = sorted_days[max(1, n - n // 3):]

        early_imp = sum(d["impressions"] for _, d in first_third)
        late_imp = sum(d["impressions"] for _, d in last_third)
        early_spend = sum(d["spend"] for _, d in first_third)
        late_spend = sum(d["spend"] for _, d in last_third)

        if early_imp <= 0:
            return None

        imp_delta = (late_imp - early_imp) / early_imp
        spend_delta = (
            (late_spend - early_spend) / early_spend if early_spend > 0 else 0.0
        )

        if imp_delta < -0.20 and abs(spend_delta) < 0.15:
            return {
                "cause": "audience_saturation",
                "evidence": (
                    f"Impessions declined {imp_delta:+.0%} while spend changed only "
                    f"{spend_delta:+.0%} — the audience pool may be exhausted."
                ),
                "confidence": "high" if imp_delta < -0.40 else "medium",
            }
        return None

    def _detect_budget_too_low(
        self, top_metrics: dict[str, Any], day_count: int
    ) -> dict[str, Any] | None:
        """Detect low impressions relative to a simple benchmark.

        Uses a heuristic of <5,000 impressions/day as "low".
        """
        impressions = top_metrics.get("impressions", 0)
        if day_count <= 0:
            return None
        avg_daily_imp = impressions / day_count
        if avg_daily_imp < 5_000:
            return {
                "cause": "budget_too_low",
                "evidence": (
                    f"Average daily impressions are {avg_daily_imp:,.0f} (below the "
                    "5,000/day threshold) — budget may be too low to reach the audience."
                ),
                "confidence": "medium",
            }
        return None

    async def _detect_seasonality(
        self, campaign_id: Any, days: int, top_metrics: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Detect seasonality by comparing the recent window to a longer period.

        Loads a 2x longer history and compares average daily conversions.  A
        difference of more than 30 % suggests a seasonal effect.
        """
        longer_data = await self._load_performance(campaign_id, days * 2)
        # Need enough longer-history beyond the recent window to compare.
        if len(longer_data) < days + 3:
            return None

        recent_convs = top_metrics.get("conversions", 0)
        recent_days = max(1, days)
        recent_avg = recent_convs / recent_days

        longer_convs = sum(int(r.conversions or 0) for r in longer_data)
        longer_days = max(1, len(longer_data))
        longer_avg = longer_convs / longer_days

        if longer_avg <= 0:
            return None

        delta = (recent_avg - longer_avg) / longer_avg
        if abs(delta) > 0.30:
            direction = "higher" if delta > 0 else "lower"
            return {
                "cause": "seasonality",
                "evidence": (
                    f"Recent average daily conversions ({recent_avg:.1f}) are {direction} "
                    f"than the longer-term average ({longer_avg:.1f}), a {delta:+.0%} "
                    "change — consistent with seasonal demand shifts."
                ),
                "confidence": "low",
            }
        return None

    def _detect_competitor_activity(
        self, sorted_days: list[tuple[date, dict[str, float]]]
    ) -> dict[str, Any] | None:
        """Detect a sudden drop in impressions/clicks with no budget change.

        Looks for a single-day drop >40 % in impressions while spend stays
        flat (±10 %) — a signal of competitor activity entering the auction.
        """
        if len(sorted_days) < 4:
            return None

        # Build per-day impressions & spend lists.
        imps = [d["impressions"] for _, d in sorted_days]
        spends = [d["spend"] for _, d in sorted_days]

        for i in range(2, len(sorted_days)):
            prev_imp = imps[i - 1]
            cur_imp = imps[i]
            prev_spend = spends[i - 1]
            cur_spend = spends[i]
            if prev_imp <= 0:
                continue
            imp_drop = (cur_imp - prev_imp) / prev_imp
            spend_change = (
                (cur_spend - prev_spend) / prev_spend if prev_spend > 0 else 0.0
            )
            if imp_drop < -0.40 and abs(spend_change) < 0.10:
                day_str = str(sorted_days[i][0])
                return {
                    "cause": "competitor_activity",
                    "evidence": (
                        f"Impessions dropped {imp_drop:+.0%} on {day_str} with spend "
                        f"changing only {spend_change:+.0%} — a sudden auction shift "
                        "suggests competitor activity."
                    ),
                    "confidence": "low",
                }
        return None

    # ── data loading ─────────────────────────────────────────────────────────

    async def _load_performance(self, campaign_id: Any, days: int) -> list[Any]:
        """Query the ``CampaignPerformance`` table for the last ``days`` days.

        Returns a list of ORM rows ordered by date ascending.  Works with an
        async session (``await session.execute(...)``).
        """
        from prachar_api.models.tables import CampaignPerformance

        session = self.session_factory()
        cutoff = date.today() - timedelta(days=days)
        stmt = (
            select(CampaignPerformance)
            .where(
                CampaignPerformance.campaign_id == campaign_id,
                CampaignPerformance.date >= cutoff,
            )
            .order_by(CampaignPerformance.date.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ── pure helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _safe_div(num: float, denom: float) -> float:
        return num / denom if denom else 0.0

    def _compute_top_metrics(self, data: list[Any]) -> dict[str, Any]:
        """Aggregate totals and averages across all rows in the window."""
        impressions = sum(int(r.impressions or 0) for r in data)
        clicks = sum(int(r.clicks or 0) for r in data)
        conversions = sum(int(r.conversions or 0) for r in data)
        spend = sum(float(r.spend or 0) for r in data)
        revenue = sum(float(r.revenue or 0) for r in data)

        avg_ctr = self._safe_div(clicks, impressions)
        avg_cpa = self._safe_div(spend, conversions)
        avg_roas = self._safe_div(revenue, spend)

        return {
            "impressions": impressions,
            "clicks": clicks,
            "conversions": conversions,
            "spend": round(spend, 2),
            "revenue": round(revenue, 2),
            "avg_ctr": round(avg_ctr, 6),
            "avg_cpa": round(avg_cpa, 2),
            "avg_roas": round(avg_roas, 4),
        }

    def _compute_trend(self, data: list[Any]) -> str:
        """Compare the last 7 days of conversions against the previous 7 days.

        Returns ``up`` / ``down`` / ``flat``.  ``flat`` is also returned when
        there is not enough data to make a comparison.
        """
        daily = self._daily_totals(data)
        if len(daily) < 2:
            return "flat"

        # Sort by date ascending.
        sorted_days = sorted(daily.items(), key=lambda kv: kv[0])
        dates = [d for d, _ in sorted_days]

        last_7 = dates[-7:]
        prev_7 = dates[-14:-7] if len(dates) >= 14 else dates[: max(1, len(dates) - 7)]

        last_sum = sum(daily[d]["conversions"] for d in last_7)
        prev_sum = sum(daily[d]["conversions"] for d in prev_7) if prev_7 else 0.0

        if prev_sum == 0:
            return "up" if last_sum > 0 else "flat"

        delta = (last_sum - prev_sum) / prev_sum
        if delta > 0.05:
            return "up"
        if delta < -0.05:
            return "down"
        return "flat"

    def _find_notable_days(self, data: list[Any]) -> list[dict[str, Any]]:
        """Find days where any core metric deviates >20 % from its average.

        Returns a list of ``{date, metric, value, note}`` dicts sorted by
        date ascending.  ``value`` is the per-day total for that metric.
        """
        daily = self._daily_totals(data)
        if not daily:
            return []

        # Compute per-metric averages across all days.
        metrics = ("impressions", "clicks", "conversions", "spend", "revenue")
        averages: dict[str, float] = {}
        for m in metrics:
            values = [daily[d][m] for d in daily]
            averages[m] = sum(values) / len(values) if values else 0.0

        notable: list[dict[str, Any]] = []
        for day in sorted(daily):
            for m in metrics:
                avg = averages[m]
                value = daily[day][m]
                if avg == 0:
                    # Flag non-zero values on a zero-average baseline as spikes.
                    if value > 0:
                        notable.append(
                            {
                                "date": str(day),
                                "metric": m,
                                "value": round(float(value), 2),
                                "note": "spike (above-zero on zero baseline)",
                            }
                        )
                    continue
                delta = (value - avg) / avg
                if abs(delta) > NOTABLE_THRESHOLD:
                    note = "spike" if delta > 0 else "drop"
                    notable.append(
                        {
                            "date": str(day),
                            "metric": m,
                            "value": round(float(value), 2),
                            "note": f"{note} ({delta:+.0%} vs avg)",
                        }
                    )
        return notable

    def _benchmark_comparison(self, top_metrics: dict[str, Any]) -> dict[str, Any]:
        """Compare the campaign's CTR / CPA / ROAS to hardcoded benchmarks."""
        result: dict[str, Any] = {}
        for metric, benchmark in BENCHMARKS.items():
            actual = top_metrics.get(f"avg_{metric}", 0.0)
            if metric == "cpa":
                # Lower is better for CPA.
                if benchmark == 0:
                    status = "unknown"
                elif actual <= benchmark:
                    status = "better"
                else:
                    status = "worse"
                diff = actual - benchmark
            else:
                # Higher is better for CTR / ROAS.
                if actual >= benchmark:
                    status = "better"
                else:
                    status = "worse"
                diff = actual - benchmark
            result[metric] = {
                "actual": round(float(actual), 6),
                "benchmark": benchmark,
                "difference": round(float(diff), 6),
                "status": status,
            }
        return result

    def _build_summary(
        self,
        campaign_id: str,
        top_metrics: dict[str, Any],
        trend: str,
        notable_days: list[dict[str, Any]],
        days: int,
    ) -> str:
        """Build a natural-language executive summary string."""
        conv = top_metrics.get("conversions", 0)
        spend = top_metrics.get("spend", 0)
        revenue = top_metrics.get("revenue", 0)
        roas = top_metrics.get("avg_roas", 0)
        ctr = top_metrics.get("avg_ctr", 0)
        trend_word = {"up": "trending up", "down": "trending down", "flat": "flat"}.get(
            trend, "flat"
        )
        notable_count = len(notable_days)
        return (
            f"Campaign {campaign_id} generated {conv} conversions over the last "
            f"{days} days on {spend:.2f} spend ({revenue:.2f} revenue, "
            f"ROAS {roas:.2f}x, CTR {ctr:.2%}). Conversions are {trend_word}."
            + (f" {notable_count} notable day(s) detected." if notable_count else "")
        )

    # ── internal aggregation ─────────────────────────────────────────────────

    @staticmethod
    def _daily_totals(data: Iterable[Any]) -> dict[date, dict[str, float]]:
        """Aggregate rows into per-day totals keyed by date.

        Multiple channels on the same day are summed together.
        """
        daily: dict[date, dict[str, float]] = {}
        for r in data:
            d = r.date
            if not isinstance(d, date):
                # Defensive: coerce ISO strings.
                d = date.fromisoformat(str(d)[:10])
            bucket = daily.setdefault(
                d,
                {"impressions": 0, "clicks": 0, "conversions": 0, "spend": 0.0, "revenue": 0.0},
            )
            bucket["impressions"] += int(r.impressions or 0)
            bucket["clicks"] += int(r.clicks or 0)
            bucket["conversions"] += int(r.conversions or 0)
            bucket["spend"] += float(r.spend or 0)
            bucket["revenue"] += float(r.revenue or 0)
        return daily
