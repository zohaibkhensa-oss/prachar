"""Proactive Engine — anomaly detection & recommendation generation (P5.1/P5.2).

The Proactive Engine is the "What should I worry about?" layer.  It scans all
campaigns for a brand, looks at their daily performance data, and surfaces
anomalies — drops, spikes, and plateaus — that warrant the user's attention.

For each anomaly, ``generate_recommendation`` asks the AI to produce a
concrete recommendation: what to do, why, three creative directions, and the
expected impact.

The engine is deliberately framework-light: it only needs a *session factory*
— a zero-arg callable that returns a SQLAlchemy session (sync or async).  This
keeps it trivially mockable in unit tests while still working inside the
FastAPI router where the session is provided by ``SessionDep``.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable

from sqlalchemy import select

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

logger = logging.getLogger(__name__)


# ─── Thresholds ───────────────────────────────────────────────────────────────

DROP_THRESHOLD = 0.20   # >20% week-over-week decline → drop
SPIKE_THRESHOLD = 0.50  # >50% week-over-week increase → spike
PLATEAU_THRESHOLD = 0.05  # <5% change for 2+ weeks → plateau

# Core metrics we scan for anomalies.
_METRICS = ("impressions", "clicks", "conversions", "spend", "revenue")


# ─── Anomaly dataclass ────────────────────────────────────────────────────────


@dataclass
class Anomaly:
    """A single detected anomaly in a campaign's performance data.

    Attributes:
        brand_id:    the brand the campaign belongs to.
        campaign_id: the campaign exhibiting the anomaly.
        metric:      the metric that is anomalous (e.g. "conversions").
        magnitude:   the fractional change (e.g. -0.35 for a 35% drop).
        timeframe:   human-readable description of the window.
        severity:    "high" | "medium" | "low".
        direction:   "drop" | "spike" | "plateau".
    """

    brand_id: str
    campaign_id: str
    metric: str
    magnitude: float
    timeframe: str
    severity: str
    direction: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "brand_id": self.brand_id,
            "campaign_id": self.campaign_id,
            "metric": self.metric,
            "magnitude": self.magnitude,
            "timeframe": self.timeframe,
            "severity": self.severity,
            "direction": self.direction,
        }


# ─── Engine ───────────────────────────────────────────────────────────────────


class ProactiveEngine:
    """Detect anomalies in campaign performance and generate recommendations.

    The engine is constructed with a *session factory* — a zero-arg callable
    that returns a SQLAlchemy session (sync or async).  The engine never
    opens/closes the session; the caller owns its lifecycle.
    """

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self.session_factory = session_factory

    # ── public API ───────────────────────────────────────────────────────────

    async def detect_anomalies(
        self, brand_id: str, days: int = 30
    ) -> list[Anomaly]:
        """Load all campaigns for ``brand_id`` and scan for anomalies.

        For each campaign, the last ``days`` days of ``CampaignPerformance``
        rows are analysed.  Anomalies are detected by comparing the most
        recent week of data against the previous week:

        * **drops** — a metric declined by more than 20% week-over-week.
        * **spikes** — a metric increased by more than 50% week-over-week.
        * **plateaus** — a metric changed by less than 5% for 2+ consecutive
          weeks (i.e. the last two weeks are both flat relative to each
          other and to the week before).

        Returns a list of :class:`Anomaly` objects.  An empty list is
        returned if there is no data or no anomalies are found.
        """
        campaigns = await self._load_campaigns(brand_id)
        if not campaigns:
            return []

        anomalies: list[Anomaly] = []
        for campaign in campaigns:
            cid = str(getattr(campaign, "id", ""))
            data = await self._load_performance(cid, days)
            if not data:
                continue
            anomalies.extend(self._scan_campaign(brand_id, cid, data))
        return anomalies

    async def load_live_performance_summary(
        self, brand_id: str, days: int = 30
    ) -> str:
        """Load a concise live performance summary for a brand (C.2.1).

        Queries CampaignPerformance across all the brand's campaigns for the
        last ``days`` days and returns a concise per-channel summary string.
        Returns "" when there is no data (graceful).
        """
        from prachar_shared.marketing_intelligence.brain import (
            _format_live_performance_summary,
        )

        return await _format_live_performance_summary(
            self.session_factory, brand_id, days=days
        )

    async def generate_recommendation(
        self,
        anomaly: Anomaly,
        *,
        gateway: AIGateway,
        tenant_id: Any,
        plan: str,
        live_context: str = "",
    ) -> dict[str, Any]:
        """Generate an AI-powered recommendation for a single anomaly.

        Returns a dict with keys:
            - what_to_do:           a concrete action to take.
            - why:                  the reasoning behind the recommendation.
            - creative_directions:  a list of 3 creative direction strings.
            - expected_impact:      a description of the expected outcome.

        When ``live_context`` is provided (a concise live performance summary
        from C.2.1), it is included in the prompt so PRACHAR AI can reference real
        data in its recommendation.

        Falls back to an empty dict on any failure (so the proactive
        workflow still works without AI).  Re-raises :class:`BudgetExceeded`
        so callers can surface budget issues to the user.
        """
        prompt = self._build_recommendation_prompt(anomaly, live_context=live_context)
        try:
            comp = gateway.complete(
                prompt=prompt,
                tier=Tier.large,
                task="proactive_recommendation",
                tenant_id=tenant_id,
                plan=plan,
                max_tokens=1200,
                temperature=0.7,
                user_input=anomaly.metric,
                prompt_version="proactive_recommendation_v1.0",
            )
            try:
                raw = extract_json(comp.text) or {}
            except Exception:
                raw = {}
            return self._parse_recommendation(raw)
        except BudgetExceeded:
            raise
        except Exception as exc:
            logger.warning("proactive recommendation generation failed: %s", exc)
            return {}

    # ── anomaly scanning (pure) ──────────────────────────────────────────────

    def _scan_campaign(
        self, brand_id: str, campaign_id: str, data: list[Any]
    ) -> list[Anomaly]:
        """Scan a single campaign's performance rows for anomalies."""
        daily = self._daily_totals(data)
        if len(daily) < 2:
            return []

        sorted_days = sorted(daily.items(), key=lambda kv: kv[0])
        dates = [d for d, _ in sorted_days]

        # We need at least two weeks of data to compare week-over-week.
        if len(dates) < 7:
            return []

        anomalies: list[Anomaly] = []
        last_week = dates[-7:]
        prev_week = dates[-14:-7] if len(dates) >= 14 else dates[: max(1, len(dates) - 7)]

        timeframe = f"last 7 days vs previous 7 days"

        for metric in _METRICS:
            last_sum = sum(daily[d][metric] for d in last_week)
            prev_sum = sum(daily[d][metric] for d in prev_week) if prev_week else 0.0

            # Skip metrics with no activity at all.
            if last_sum == 0 and prev_sum == 0:
                continue

            if prev_sum == 0:
                # Going from zero to non-zero is a spike.
                if last_sum > 0:
                    anomalies.append(
                        Anomaly(
                            brand_id=brand_id,
                            campaign_id=campaign_id,
                            metric=metric,
                            magnitude=1.0,
                            timeframe=timeframe,
                            severity=self._severity(1.0, "spike"),
                            direction="spike",
                        )
                    )
                continue

            if last_sum == 0:
                # Going from non-zero to zero is a severe drop.
                magnitude = -1.0
                anomalies.append(
                    Anomaly(
                        brand_id=brand_id,
                        campaign_id=campaign_id,
                        metric=metric,
                        magnitude=magnitude,
                        timeframe=timeframe,
                        severity=self._severity(abs(magnitude), "drop"),
                        direction="drop",
                    )
                )
                continue

            delta = (last_sum - prev_sum) / prev_sum

            if delta < -DROP_THRESHOLD:
                anomalies.append(
                    Anomaly(
                        brand_id=brand_id,
                        campaign_id=campaign_id,
                        metric=metric,
                        magnitude=round(delta, 4),
                        timeframe=timeframe,
                        severity=self._severity(abs(delta), "drop"),
                        direction="drop",
                    )
                )
            elif delta > SPIKE_THRESHOLD:
                anomalies.append(
                    Anomaly(
                        brand_id=brand_id,
                        campaign_id=campaign_id,
                        metric=metric,
                        magnitude=round(delta, 4),
                        timeframe=timeframe,
                        severity=self._severity(abs(delta), "spike"),
                        direction="spike",
                    )
                )
            elif abs(delta) < PLATEAU_THRESHOLD:
                # Plateau: also check that the previous week was flat
                # relative to the week before it (if we have 3+ weeks).
                if len(dates) >= 21:
                    prev_prev_week = dates[-21:-14]
                    if prev_prev_week:
                        prev_prev_sum = sum(
                            daily[d][metric] for d in prev_prev_week
                        )
                        if prev_prev_sum > 0:
                            prev_delta = (prev_sum - prev_prev_sum) / prev_prev_sum
                            if abs(prev_delta) < PLATEAU_THRESHOLD:
                                anomalies.append(
                                    Anomaly(
                                        brand_id=brand_id,
                                        campaign_id=campaign_id,
                                        metric=metric,
                                        magnitude=round(delta, 4),
                                        timeframe="last 2+ weeks",
                                        severity="low",
                                        direction="plateau",
                                    )
                                )
                        else:
                            # Previous week was zero, now flat at non-zero —
                            # still a plateau.
                            anomalies.append(
                                Anomaly(
                                    brand_id=brand_id,
                                    campaign_id=campaign_id,
                                    metric=metric,
                                    magnitude=round(delta, 4),
                                    timeframe="last 2+ weeks",
                                    severity="low",
                                    direction="plateau",
                                )
                            )
                else:
                    # With 2 weeks of flat data, flag as a mild plateau.
                    anomalies.append(
                        Anomaly(
                            brand_id=brand_id,
                            campaign_id=campaign_id,
                            metric=metric,
                            magnitude=round(delta, 4),
                            timeframe="last 2 weeks",
                            severity="low",
                            direction="plateau",
                        )
                    )

        return anomalies

    @staticmethod
    def _severity(magnitude: float, direction: str) -> str:
        """Classify the severity of an anomaly based on its magnitude."""
        if direction == "drop":
            if magnitude >= 0.50:
                return "high"
            if magnitude >= 0.30:
                return "medium"
            return "low"
        if direction == "spike":
            if magnitude >= 1.0:
                return "high"
            if magnitude >= 0.75:
                return "medium"
            return "low"
        return "low"

    # ── recommendation prompt (pure) ─────────────────────────────────────────

    def _build_recommendation_prompt(
        self, anomaly: Anomaly, *, live_context: str = ""
    ) -> str:
        """Assemble the recommendation prompt from an anomaly.

        When ``live_context`` is provided, it is included so PRACHAR AI can reference
        real live performance data in its recommendation.
        """
        direction_desc = {
            "drop": "a significant decline",
            "spike": "a sudden increase",
            "plateau": "a flat, stagnant period",
        }.get(anomaly.direction, anomaly.direction)

        pct = abs(anomaly.magnitude) * 100

        prompt = (
            "You are a senior marketing strategist. A performance anomaly has "
            "been detected in a campaign and the user needs a concrete "
            "recommendation on what to do about it.\n\n"
            f"Anomaly details:\n"
            f"- Campaign: {anomaly.campaign_id}\n"
            f"- Metric: {anomaly.metric}\n"
            f"- Direction: {direction_desc} ({anomaly.direction})\n"
            f"- Magnitude: {pct:.0f}% change\n"
            f"- Timeframe: {anomaly.timeframe}\n"
            f"- Severity: {anomaly.severity}\n"
        )

        if live_context:
            prompt += (
                f"\nLive performance data (last 30 days across all channels):\n"
                f"{live_context}\n"
            )

        prompt += (
            "\nGenerate a recommendation with:\n"
            "1. what_to_do: A specific, actionable next step (1-2 sentences).\n"
            "2. why: The reasoning behind this recommendation. Reference the "
            "live performance data above when relevant (2-3 sentences).\n"
            "3. creative_directions: Exactly 3 distinct creative direction "
            "ideas to address this anomaly, each a short phrase.\n"
            "4. expected_impact: What the user can expect if they follow this "
            "recommendation (1-2 sentences).\n\n"
            "Respond as JSON only, no markdown:\n"
            "{\n"
            '  "what_to_do": "...",\n'
            '  "why": "...",\n'
            '  "creative_directions": ["...", "...", "..."],\n'
            '  "expected_impact": "..."\n'
            "}"
        )
        return prompt

    @staticmethod
    def _parse_recommendation(raw: Any) -> dict[str, Any]:
        """Normalise the parsed JSON into a recommendation dict."""
        if not isinstance(raw, dict):
            return {}

        directions = raw.get("creative_directions")
        if not isinstance(directions, list):
            directions = []
        directions = [str(d) for d in directions if d]

        return {
            "what_to_do": str(raw.get("what_to_do", "")),
            "why": str(raw.get("why", "")),
            "creative_directions": directions,
            "expected_impact": str(raw.get("expected_impact", "")),
        }

    # ── data loading ─────────────────────────────────────────────────────────

    async def _load_campaigns(self, brand_id: str) -> list[Any]:
        """Query all campaigns for a brand."""
        from prachar_api.models.tables import Campaign

        session = self.session_factory()
        stmt = select(Campaign).where(Campaign.brand_id == brand_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _load_performance(self, campaign_id: str, days: int) -> list[Any]:
        """Query the ``CampaignPerformance`` table for the last ``days`` days.

        Returns a list of ORM rows ordered by date ascending.
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
    def _daily_totals(data: list[Any]) -> dict[date, dict[str, float]]:
        """Aggregate rows into per-day metric totals.

        Multiple rows on the same day (different channels) are summed.
        """
        daily: dict[date, dict[str, float]] = {}
        for row in data:
            d = getattr(row, "date", None)
            if d is None:
                continue
            if d not in daily:
                daily[d] = {m: 0.0 for m in _METRICS}
            for m in _METRICS:
                daily[d][m] += float(getattr(row, m, 0) or 0)
        return daily


# ─── PRACHAR AI message formatting (P5.3) ──────────────────────────────────────


# Human-friendly labels for the metrics we track.
_METRIC_LABELS = {
    "impressions": "impressions",
    "clicks": "clicks",
    "conversions": "conversions",
    "spend": "ad spend",
    "revenue": "revenue",
}

_DIRECTION_VERBS = {
    "drop": "dropped",
    "spike": "jumped",
    "plateau": "flatlined",
}


def format_as_prachar_message(
    anomaly: Anomaly,
    recommendation: dict[str, Any] | None = None,
    *,
    live_context: str = "",
) -> str:
    """Format an anomaly (+ optional recommendation) into a PRACHAR AI message.

    PRACHAR AI voice characteristics:
      * Friendly, direct, conversational — like a knowledgeable friend.
      * No marketing jargon (no "ROAS", "CPA", "funnel optimisation").
      * Uses "I noticed", "I recommend", "Here's what I'd do".
      * References live performance data when available.
      * Ends with the three creative directions when available.

    When ``live_context`` is provided, PRACHAR AI references the live data in
    its message — e.g. "Your Instagram reached 12K people last week with 3%
    engagement. I recommend doubling down on Reels."

    Example output::

        Hey, I noticed your conversions dropped 35% this week compared to
        last week. I recommend refreshing your ad creative — the current
        ones have likely fatigued. Here are three creative directions to
        try: 1) Bold new hook, 2) Customer testimonial angle, 3) Limited-
        time urgency. This should help you recover most of the lost
        conversions over the next couple of weeks.
    """
    metric_label = _METRIC_LABELS.get(anomaly.metric, anomaly.metric)
    verb = _DIRECTION_VERBS.get(anomaly.direction, "changed")
    pct = abs(anomaly.magnitude) * 100

    # Opening — what I noticed.
    if anomaly.direction == "plateau":
        noticed = (
            f"Hey, I noticed your {metric_label} have been flat for "
            f"{anomaly.timeframe}."
        )
    else:
        noticed = (
            f"Hey, I noticed your {metric_label} {verb} {pct:.0f}% "
            f"this week compared to last week."
        )

    parts: list[str] = [noticed]

    # Live performance data — reference it when available.
    if live_context:
        parts.append(f"Here's what I'm seeing across your channels: {live_context}")

    # Recommendation — what I'd do.
    rec = recommendation or {}
    what_to_do = str(rec.get("what_to_do", "")).strip()
    why = str(rec.get("why", "")).strip()
    expected_impact = str(rec.get("expected_impact", "")).strip()
    directions = rec.get("creative_directions")
    if not isinstance(directions, list):
        directions = []

    if what_to_do:
        parts.append(f"I recommend {what_to_do.lower().rstrip('.')}.")

    if why:
        parts.append(why.rstrip("."))

    if directions:
        dirs = [str(d).strip() for d in directions if str(d).strip()]
        if dirs:
            numbered = ", ".join(f"{i}) {d}" for i, d in enumerate(dirs, 1))
            parts.append(f"Here are three creative directions to try: {numbered}.")

    if expected_impact:
        parts.append(expected_impact.rstrip("."))

    # If we have no recommendation at all, give a sensible fallback.
    if not what_to_do and not why and not directions:
        if anomaly.direction == "drop":
            parts.append(
                "Here's what I'd do: refresh your ad creative and test a "
                "new hook — fatigue is the most common cause of drops like this."
            )
        elif anomaly.direction == "spike":
            parts.append(
                "Here's what I'd do: lean into what's working — increase "
                "your budget on this campaign while the momentum lasts."
            )
        else:  # plateau
            parts.append(
                "Here's what I'd do: try a fresh creative angle or a small "
                "budget increase to break out of the plateau."
            )

    return " ".join(parts)
