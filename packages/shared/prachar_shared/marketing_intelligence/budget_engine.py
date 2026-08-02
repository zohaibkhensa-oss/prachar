"""Budget Intelligence Engine.

Estimates creative cost, AI cost, advertising cost, agency cost, ROI,
CAC, expected reach, expected engagement, and expected conversion.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class BudgetEstimate(DomainModel):
    """Comprehensive budget estimate with ROI projections.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by BudgetIntelligenceEngine.
    """

    creative_cost: dict[str, Any] = field(default_factory=dict)
    ai_cost: dict[str, Any] = field(default_factory=dict)
    advertising_cost: dict[str, Any] = field(default_factory=dict)
    agency_cost: dict[str, Any] = field(default_factory=dict)
    total_cost: dict[str, Any] = field(default_factory=dict)
    roi_projection: dict[str, Any] = field(default_factory=dict)
    cac_estimate: dict[str, Any] = field(default_factory=dict)
    expected_reach: str = ""
    expected_engagement: str = ""
    expected_conversion: str = ""
    break_even_analysis: str = ""
    cost_breakdown: list[dict[str, Any]] = field(default_factory=list)
    roi_per_channel: list[dict[str, Any]] = field(default_factory=list)
    cpa_estimate: dict[str, Any] = field(default_factory=dict)
    budget_contingency: dict[str, Any] = field(default_factory=dict)
    marginal_roi_analysis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_cost": self.creative_cost,
            "ai_cost": self.ai_cost,
            "advertising_cost": self.advertising_cost,
            "agency_cost": self.agency_cost,
            "total_cost": self.total_cost,
            "roi_projection": self.roi_projection,
            "cac_estimate": self.cac_estimate,
            "expected_reach": self.expected_reach,
            "expected_engagement": self.expected_engagement,
            "expected_conversion": self.expected_conversion,
            "break_even_analysis": self.break_even_analysis,
            "cost_breakdown": self.cost_breakdown,
            "roi_per_channel": self.roi_per_channel,
            "cpa_estimate": self.cpa_estimate,
            "budget_contingency": self.budget_contingency,
            "marginal_roi_analysis": self.marginal_roi_analysis,
        }


class BudgetIntelligenceEngine(IntelligenceEngine):
    """Estimates comprehensive campaign costs and ROI projections."""

    ENGINE_NAME = "budget_intelligence"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 3000
    TEMPERATURE = 0.2  # Lower temperature for financial estimates

    def _build_prompt(self, **kwargs: Any) -> str:
        business_profile = kwargs.get("business_profile", {})
        audience_profile = kwargs.get("audience_profile", {})
        objective = kwargs.get("objective", {})
        campaign_strategy = kwargs.get("campaign_strategy", {})
        media_plan = kwargs.get("media_plan", {})
        budget = kwargs.get("budget", "")
        currency = kwargs.get("currency", "INR")
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a CFO + Media Finance Director at a top agency. You estimate
campaign costs with the precision of an accountant and the strategic insight of a
CFO. Every number must be defensible. You project ROI per channel, estimate
cost-per-acquisition, set aside budget contingency for optimisation, and identify
the diminishing returns threshold where marginal ROI drops below 1.

TASK: Create a comprehensive budget estimate with ROI projections, per-channel
ROI analysis, CPA estimates, budget contingency, and marginal ROI analysis.

INPUTS:
- Business Profile: {business_profile}
- Audience Profile: {audience_profile}
- Marketing Objective: {objective}
- Campaign Strategy: {campaign_strategy}
- Media Plan: {media_plan}
- Budget: {budget}
- Currency: {currency}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — COST STACK: Break down all costs: creative, AI, advertising, agency.
  Estimate each with market rates. Show the unit economics (cost per asset, cost per token, CPM).
Step 2 — CHANNEL ROI: For each channel in the media plan, project the ROI.
  Which channels will deliver the best return? Where should we concentrate spend?
Step 3 — CPA: Estimate the cost per acquisition for the campaign.
  Is it viable given the customer LTV? What is the LTV:CAC ratio?
Step 4 — CONTINGENCY: Set aside 10-20% of budget as contingency for optimisation.
  What will this contingency fund? (scaling winners, testing new creatives, responding to competitor moves)
Step 5 — MARGINAL ROI: At what spend level does marginal ROI drop below 1?
  Where is the diminishing returns threshold? How do we know when to stop scaling a channel?
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

BUDGET REQUIREMENTS:
1. Creative Cost: AI-generated content (images, videos, copy) + custom design
   - Estimate per-asset cost and total
2. AI Cost: Token usage estimates for the campaign
   - Content generation, optimization, analysis
3. Advertising Cost: Media buying budget per channel
   - Include CPM/CPC estimates per channel
4. Agency Cost: If external agency support is needed
   - Strategy, creative direction, management
5. Total Cost: Sum of all categories
6. ROI Projection:
   - Expected revenue impact
   - ROAS (Return on Ad Spend)
   - Payback period
7. CAC Estimate: Customer Acquisition Cost
8. Expected Reach/Engagement/Conversion: Realistic estimates
9. Break-Even Analysis: What results are needed to break even
10. Cost Breakdown: Itemized list of all costs
11. ROI Projection Per Channel: For each channel in the media plan:
    - channel: Name
    - spend: Estimated spend amount
    - expected_revenue: Revenue expected from this channel
    - expected_roas: ROAS for this channel (e.g., "4.2x")
    - expected_cpa: Cost per acquisition from this channel
    - roi_justification: Why this ROI is realistic (audience intent, creative fit, historical data)
    - confidence: How confident are we in this projection? (low/medium/high)
12. Cost-Per-Acquisition Estimate:
    - blended_cpa: Weighted average CPA across all channels
    - best_cpa_channel: Which channel has the lowest CPA?
    - worst_cpa_channel: Which channel has the highest CPA?
    - ltv_cac_ratio: Customer LTV divided by CAC (must be > 3 for healthy unit economics)
    - viability_assessment: Is this CPA viable? What LTV is needed to break even?
13. Budget Contingency:
    - contingency_percentage: 10-20% of total budget reserved
    - contingency_amount: The actual amount reserved
    - purpose: What will this fund? (scaling winners, testing new creatives,
      responding to competitor moves, fixing underperforming channels)
    - release_criteria: When can contingency be released? (e.g., "After week 4,
      if ROAS > 3x, release 50% to scale best channel")
    - trigger_conditions: What triggers contingency deployment?
      (e.g., "If CTR < 1% in week 2, deploy contingency for creative refresh")
14. Marginal ROI Analysis:
    - diminishing_returns_threshold: At what spend level does marginal ROI drop below 1?
      (e.g., "Instagram: marginal ROI drops below 1 at ₹2.5L/month — beyond this,
      each additional ₹1 generates less than ₹1 in revenue")
    - per_channel_thresholds: For each major channel, the spend level where returns diminish
    - scaling_recommendation: Where should we scale? Where should we stop?
    - monitoring_metrics: What metrics tell us we're approaching the threshold?
      (e.g., "CPM rising > 20% week-over-week, CTR declining > 15% week-over-week")

FEW-SHOT EXAMPLE (D2C Coffee, ₹5L budget, INR — use as quality benchmark, do NOT copy):
- ROI Per Channel:
  - channel: "Instagram", spend: "₹2,00,000", expected_revenue: "₹8,50,000",
    expected_roas: "4.25x", expected_cpa: "₹650",
    roi_justification: "Visual product, high-intent lifestyle audience, retargeting layer
      improves CPA by 40%. Historical D2C coffee data: 4-4.5x ROAS on Instagram.",
    confidence: "high"
  - channel: "YouTube", spend: "₹1,00,000", expected_revenue: "₹3,20,000",
    expected_roas: "3.2x", expected_cpa: "₹900",
    roi_justification: "Long-form builds trust but lower direct-response efficiency.
      YouTube is a consideration channel, not a conversion channel.",
    confidence: "medium"
- CPA Estimate:
  blended_cpa: "₹720 (weighted by channel spend)",
  best_cpa_channel: "Instagram at ₹650",
  worst_cpa_channel: "YouTube at ₹900",
  ltv_cac_ratio: "5.5x (LTV ₹4,000 / CAC ₹720 — healthy, above 3x threshold)",
  viability_assessment: "Viable. Even at worst-case CPA of ₹1,000, LTV:CAC is 4x.
    Subscription model improves LTV to ₹6,000, making CPA up to ₹2,000 viable."
- Budget Contingency:
  contingency_percentage: "15%",
  contingency_amount: "₹75,000",
  purpose: "Scale Instagram if ROAS > 4x by week 4. Test new creative angles if CTR < 1.5%.
    Counter Blue Tokai if they launch a competing campaign.",
  release_criteria: "After week 4: if ROAS > 4x, release 60% (₹45,000) to scale Instagram.
    If ROAS 3-4x, release 30% for creative refresh. If ROAS < 3x, hold for pivot.",
  trigger_conditions: "CTR < 1% in any week → deploy ₹20,000 for creative A/B test.
    Competitor launches aggressive campaign → deploy ₹25,000 for defensive retargeting."
- Marginal ROI Analysis:
  diminishing_returns_threshold: "Instagram: marginal ROI drops below 1 at ₹3L/month.
    YouTube: marginal ROI drops below 1 at ₹1.5L/month.",
  per_channel_thresholds: [
    "Instagram: ₹0-2L = 4-5x ROAS, ₹2-3L = 3-4x, ₹3L+ = <2x (audience saturation)",
    "YouTube: ₹0-1L = 3-3.5x, ₹1-1.5L = 2-2.5x, ₹1.5L+ = <1.5x (limited inventory)"
  ],
  scaling_recommendation: "Scale Instagram up to ₹2.5L (sweet spot). Do not exceed ₹3L.
    Keep YouTube at ₹1L. If Instagram hits ₹2.5L with ROAS > 4x, test Google Search
    as a new channel rather than pushing Instagram further.",
  monitoring_metrics: "CPM rising > 20% WoW, CTR declining > 15% WoW, frequency > 5
    per user per week — all signal approaching saturation."

QUALITY RULES:
- All estimates must be in the specified currency ({currency})
- Use realistic market rates (India/global as appropriate)
- ROI projections must be conservative, not optimistic
- CAC must be lower than customer LTV for viability
- Per-channel ROI must cite justification — no numbers from thin air
- Budget contingency must be 10-20% — not 0%, not 50%
- Marginal ROI thresholds must be specific, not "eventually returns diminish"
- Confidence 0.3-0.7 (financial projections have inherent uncertainty)
- 3-5 budget optimization recommendations

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "creative_cost": {
                    "type": "object",
                    "properties": {
                        "ai_generated": {"type": "string"},
                        "custom_design": {"type": "string"},
                        "total": {"type": "string"},
                    },
                },
                "ai_cost": {
                    "type": "object",
                    "properties": {
                        "content_generation": {"type": "string"},
                        "optimization": {"type": "string"},
                        "analysis": {"type": "string"},
                        "total": {"type": "string"},
                    },
                },
                "advertising_cost": {
                    "type": "object",
                    "properties": {
                        "total": {"type": "string"},
                        "per_channel": {"type": "array", "items": {"type": "object"}},
                    },
                },
                "agency_cost": {
                    "type": "object",
                    "properties": {
                        "strategy": {"type": "string"},
                        "creative_direction": {"type": "string"},
                        "management": {"type": "string"},
                        "total": {"type": "string"},
                    },
                },
                "total_cost": {
                    "type": "object",
                    "properties": {
                        "amount": {"type": "string"},
                        "currency": {"type": "string"},
                        "breakdown_percentage": {"type": "object"},
                    },
                },
                "roi_projection": {
                    "type": "object",
                    "properties": {
                        "expected_revenue": {"type": "string"},
                        "expected_roas": {"type": "string"},
                        "payback_period": {"type": "string"},
                        "profit_margin": {"type": "string"},
                    },
                },
                "cac_estimate": {
                    "type": "object",
                    "properties": {
                        "estimated_cac": {"type": "string"},
                        "ltv_comparison": {"type": "string"},
                        "viability": {"type": "string"},
                    },
                },
                "expected_reach": {"type": "string"},
                "expected_engagement": {"type": "string"},
                "expected_conversion": {"type": "string"},
                "break_even_analysis": {"type": "string"},
                "cost_breakdown": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "cost": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                    },
                },
                "roi_per_channel": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "spend": {"type": "string"},
                            "expected_revenue": {"type": "string"},
                            "expected_roas": {"type": "string"},
                            "expected_cpa": {"type": "string"},
                            "roi_justification": {"type": "string"},
                            "confidence": {"type": "string"},
                        },
                    },
                },
                "cpa_estimate": {
                    "type": "object",
                    "properties": {
                        "blended_cpa": {"type": "string"},
                        "best_cpa_channel": {"type": "string"},
                        "worst_cpa_channel": {"type": "string"},
                        "ltv_cac_ratio": {"type": "string"},
                        "viability_assessment": {"type": "string"},
                    },
                },
                "budget_contingency": {
                    "type": "object",
                    "properties": {
                        "contingency_percentage": {"type": "string"},
                        "contingency_amount": {"type": "string"},
                        "purpose": {"type": "string"},
                        "release_criteria": {"type": "string"},
                        "trigger_conditions": {"type": "string"},
                    },
                },
                "marginal_roi_analysis": {
                    "type": "object",
                    "properties": {
                        "diminishing_returns_threshold": {"type": "string"},
                        "per_channel_thresholds": {"type": "array", "items": {"type": "string"}},
                        "scaling_recommendation": {"type": "string"},
                        "monitoring_metrics": {"type": "string"},
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
            "required": ["total_cost", "roi_projection", "reasoning", "confidence"],
        }

    def to_estimate(self, output: EngineOutput) -> BudgetEstimate:
        """Convert an EngineOutput to a typed BudgetEstimate.

        Delegates to BudgetEstimate.from_dict() — the model owns parsing.
        """
        return BudgetEstimate.from_dict(output.result)  # type: ignore[return-value]
