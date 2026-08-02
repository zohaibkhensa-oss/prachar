"""Media Planning Engine.

Determines the optimal media mix across Instagram, Facebook, LinkedIn,
Google, YouTube, WhatsApp, Outdoor, Print, TV, Radio, Cinema, Email, SMS
based on audience, budget, goal, and industry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class MediaPlan(DomainModel):
    """Media plan with channel selection and budget allocation.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by MediaPlanningEngine.
    """

    recommended_channels: list[dict[str, Any]] = field(default_factory=list)
    budget_split: dict[str, Any] = field(default_factory=dict)
    scheduling: dict[str, Any] = field(default_factory=dict)
    reach_estimate: dict[str, Any] = field(default_factory=dict)
    channel_rationale: dict[str, Any] = field(default_factory=dict)
    dayparting: list[dict[str, Any]] = field(default_factory=list)
    channel_synergy: dict[str, Any] = field(default_factory=dict)
    roi_reasoning: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended_channels": self.recommended_channels,
            "budget_split": self.budget_split,
            "scheduling": self.scheduling,
            "reach_estimate": self.reach_estimate,
            "channel_rationale": self.channel_rationale,
            "dayparting": self.dayparting,
            "channel_synergy": self.channel_synergy,
            "roi_reasoning": self.roi_reasoning,
        }


class MediaPlanningEngine(IntelligenceEngine):
    """Determines optimal media mix based on audience, budget, goal, industry."""

    ENGINE_NAME = "media_planning"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 3000
    TEMPERATURE = 0.3

    def _build_prompt(self, **kwargs: Any) -> str:
        business_profile = kwargs.get("business_profile", {})
        audience_profile = kwargs.get("audience_profile", {})
        objective = kwargs.get("objective", {})
        budget = kwargs.get("budget", "")
        campaign_strategy = kwargs.get("campaign_strategy", {})
        locale = kwargs.get("locale", "en-IN")
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a senior media planner at a global media agency
(GroupM/Dentsu/IPG). You allocate media budgets with the precision of a financial
analyst and the audience insight of a behavioral scientist. You don't just split
percentages — you justify every rupee with ROI reasoning, calculate reach and
frequency with media math, recommend dayparting based on audience behaviour, and
explain how channels work together as a system, not in isolation.

TASK: Create a media plan that maximizes ROI for the given budget.

INPUTS:
- Business Profile: {business_profile}
- Audience Profile: {audience_profile}
- Marketing Objective: {objective}
- Campaign Strategy: {campaign_strategy}
- Budget: {budget}
- Locale: {locale}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — AUDIENCE FIT: Where does this audience spend time? Tie each channel to
  specific audience platform behaviour data from the audience profile.
Step 2 — ROI RANKING: For each candidate channel, estimate the expected ROI.
  Rank channels by ROI potential, not just reach. A channel with high reach but
  low conversion is less valuable than a channel with moderate reach but high intent.
Step 3 — REACH/FREQUENCY MATH: Calculate expected reach and frequency for the budget.
  Use the formula: Impressions = Budget / CPM × 1000. Frequency = Impressions / Reach.
  Show the math so it can be verified.
Step 4 — DAYPARTING: When is this audience most receptive on each channel?
  Recommend specific time slots and days based on audience behaviour patterns.
Step 5 — SYNERGY: How do the channels work together? Which channel drives discovery,
  which drives consideration, which drives conversion? Explain the handoff between channels.
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

MEDIA PLANNING REQUIREMENTS:
1. Recommended Channels: Select from:
   DIGITAL: Instagram, Facebook, LinkedIn, Google Search, Google Display,
   YouTube, WhatsApp, Email, SMS, TikTok, X/Twitter, Pinterest
   TRADITIONAL: Outdoor (OOH), Print, TV, Radio, Cinema
   For each channel include:
   - Why it's recommended (tie to audience + objective)
   - Budget percentage
   - Expected reach
   - Expected CPM/CPC
   - Content format recommendations
2. Budget Split: Total must equal 100%. Include both organic and paid allocation.
3. Scheduling: When to run on each channel (time of day, day of week, frequency).
4. Reach Estimate: Total expected reach, impressions, and frequency.
5. Channel Rationale: Why each channel was chosen and why others were rejected.
6. Dayparting Recommendations: For each major channel:
   - channel: Name
   - peak_slots: Specific time windows (e.g., "7-9 AM, 8-11 PM IST")
   - peak_days: Which days perform best (e.g., "Tue-Thu for B2B, Sat-Sun for B2C")
   - rationale: Why these slots? Tie to audience behaviour (e.g., "Morning ritual
     scrolling during commute", "Evening unwind after dinner")
   - frequency_cap: How many times should one user see the ad per day/week?
   - budget_weighting: Should we concentrate spend in peak slots or spread evenly?
     (e.g., "60% in peak slots, 40% in off-peak for frequency maintenance")
7. Channel Synergy Explanation: How do the selected channels work together?
   - discovery_channels: Which channels drive first discovery? (e.g., Instagram Reels, YouTube)
   - consideration_channels: Which channels nurture consideration? (e.g., Google Search retargeting, email)
   - conversion_channels: Which channels drive the final purchase? (e.g., retargeting ads, WhatsApp)
   - synergy_narrative: Explain the handoff — how does a user move from discovery to conversion
     across channels? (e.g., "User discovers brand on Instagram Reel → searches brand on Google
     → sees retargeting ad on YouTube → converts via WhatsApp click-to-chat")
   - cross_channel_amplification: How does one channel amplify another?
     (e.g., "YouTube long-form builds trust that makes Instagram retargeting 2x more effective")
8. ROI-Based Reasoning: For each channel:
   - channel: Name
   - expected_cpm: Estimated CPM with market reference
   - expected_cpc: Estimated CPC with market reference
   - expected_cpa: Estimated cost per acquisition
   - estimated_roi: Expected return (e.g., "₹4 revenue per ₹1 spent = 4x ROAS")
   - roi_justification: Why this ROI is realistic — cite audience intent level,
     historical data, or industry benchmarks
   - budget_efficiency: Is this channel budget-efficient for this budget size?
     (e.g., "High CPM makes TV inefficient below ₹10L budget")

FEW-SHOT EXAMPLE (D2C Coffee, ₹5L budget, en-IN — use as quality benchmark, do NOT copy):
- Dayparting:
  - channel: "Instagram"
    peak_slots: "7-9 AM (morning ritual), 8-11 PM (evening unwind)"
    peak_days: "All days, Sat-Sun +15% engagement"
    rationale: "Coffee is a morning ritual — 7-9 AM captures the brewing moment.
      8-11 PM captures planning/gifting mindset."
    frequency_cap: "3 impressions/day, 12/week"
    budget_weighting: "50% morning slots, 30% evening, 20% midday frequency maintenance"
  - channel: "YouTube"
    peak_slots: "Weekends 10 AM-2 PM (leisure viewing)"
    peak_days: "Sat-Sun primary, Wed for midweek long-form"
    rationale: "Long-form brewing tutorials watched during leisure time, not commute"
    frequency_cap: "1-2 impressions/week (long-form doesn't need high frequency)"
    budget_weighting: "70% weekend, 30% midweek"
- Channel Synergy:
  discovery_channels: ["Instagram Reels", "YouTube long-form"]
  consideration_channels: ["Google Search (brand + category)", "Instagram retargeting"]
  conversion_channels: ["WhatsApp click-to-chat", "Instagram Shopping"]
  synergy_narrative: "User discovers brand on Instagram Reel (farmer story) →
    searches 'direct trade coffee India' on Google → sees YouTube retargeting with
    brewing tutorial → visits website → abandons cart → receives WhatsApp broadcast
    with first-order discount → converts"
  cross_channel_amplification: "YouTube long-form builds deep trust (8-min documentary)
    that makes Instagram retargeting 2x more effective — users who watched YouTube
    convert at 4.2% vs 2.1% for Instagram-only"
- ROI Reasoning:
  - channel: "Instagram"
    expected_cpm: "₹180-250 (India CPM benchmark for lifestyle audience)"
    expected_cpc: "₹8-15"
    expected_cpa: "₹600-900"
    estimated_roi: "3.5-4.5x ROAS"
    roi_justification: "High-intent lifestyle audience, strong creative fit (visual product),
      retargeting layer improves CPA by 40%. Historical D2C coffee data supports 4x ROAS."
    budget_efficiency: "High — Instagram is the most efficient channel for visual D2C
      under ₹10L budget"

QUALITY RULES:
- Channel selection must be evidence-based (audience platform preferences)
- Budget split must reflect audience behavior, not just channel popularity
- For small budgets, focus on high-ROI digital channels
- For large budgets, consider traditional media for reach
- Estimates must be realistic for the market (India/global)
- ROI reasoning must cite benchmarks or historical data — no numbers from thin air
- Dayparting must tie to audience behaviour, not generic "evening is best"
- Channel synergy must explain the handoff, not just list channels
- Reach/frequency math must be shown and verifiable
- Confidence 0.3-0.7 (media planning has inherent uncertainty)
- 3-5 media recommendations

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recommended_channels": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "type": {"type": "string"},  # digital, traditional
                            "rationale": {"type": "string"},
                            "budget_percentage": {"type": "number"},
                            "expected_reach": {"type": "string"},
                            "expected_cpm": {"type": "string"},
                            "content_format": {"type": "string"},
                            "priority": {"type": "string"},  # high, medium, low
                        },
                    },
                },
                "budget_split": {
                    "type": "object",
                    "properties": {
                        "digital_paid": {"type": "number"},
                        "digital_organic": {"type": "number"},
                        "traditional": {"type": "number"},
                        "total": {"type": "string"},
                    },
                },
                "scheduling": {
                    "type": "object",
                    "properties": {
                        "peak_times": {"type": "string"},
                        "frequency": {"type": "string"},
                        "duration_weeks": {"type": "number"},
                    },
                },
                "reach_estimate": {
                    "type": "object",
                    "properties": {
                        "total_reach": {"type": "string"},
                        "total_impressions": {"type": "string"},
                        "average_frequency": {"type": "string"},
                    },
                },
                "channel_rationale": {
                    "type": "object",
                    "properties": {
                        "selected": {"type": "array", "items": {"type": "string"}},
                        "rejected": {"type": "array", "items": {"type": "string"}},
                        "rejection_reasons": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "dayparting": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "peak_slots": {"type": "string"},
                            "peak_days": {"type": "string"},
                            "rationale": {"type": "string"},
                            "frequency_cap": {"type": "string"},
                            "budget_weighting": {"type": "string"},
                        },
                    },
                },
                "channel_synergy": {
                    "type": "object",
                    "properties": {
                        "discovery_channels": {"type": "array", "items": {"type": "string"}},
                        "consideration_channels": {"type": "array", "items": {"type": "string"}},
                        "conversion_channels": {"type": "array", "items": {"type": "string"}},
                        "synergy_narrative": {"type": "string"},
                        "cross_channel_amplification": {"type": "string"},
                    },
                },
                "roi_reasoning": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "expected_cpm": {"type": "string"},
                            "expected_cpc": {"type": "string"},
                            "expected_cpa": {"type": "string"},
                            "estimated_roi": {"type": "string"},
                            "roi_justification": {"type": "string"},
                            "budget_efficiency": {"type": "string"},
                        },
                    },
                },
                "reasoning": {"type": "string"},
                "confidence": {"type": "number"},
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "confidence": {"type": "number"},
                            "business_rationale": {"type": "string"},
                            "marketing_rationale": {"type": "string"},
                            "alternatives": {"type": "array", "items": {"type": "string"}},
                            "risks": {"type": "array", "items": {"type": "string"}},
                            "expected_outcome": {"type": "string"},
                            "evidence": {"type": "array", "items": {"type": "string"}},
                            "sources": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
            "required": ["recommended_channels", "budget_split", "reasoning", "confidence"],
        }

    def to_plan(self, output: EngineOutput) -> MediaPlan:
        """Convert an EngineOutput to a typed MediaPlan.

        Delegates to MediaPlan.from_dict() — the model owns parsing.
        """
        return MediaPlan.from_dict(output.result)  # type: ignore[return-value]
