"""Marketing Objective Engine.

Converts a user request into measurable marketing objectives with KPIs.
Examples: increase leads, increase sales, launch product, increase footfall,
build awareness, customer retention, recruitment, investor outreach.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class MarketingObjective(DomainModel):
    """A measurable marketing objective with KPIs.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by MarketingObjectiveEngine.
    """

    objective_type: str = ""  # leads, sales, awareness, retention, launch, etc.
    description: str = ""
    kpis: list[dict[str, Any]] = field(default_factory=list)
    target_metrics: dict[str, Any] = field(default_factory=dict)
    timeline: str = ""
    success_criteria: str = ""
    funnel_stage: str = ""  # awareness, consideration, conversion, retention
    smart_objective: dict[str, Any] = field(default_factory=dict)
    primary_kpi: dict[str, Any] = field(default_factory=dict)
    secondary_kpis: list[dict[str, Any]] = field(default_factory=list)
    success_criteria_definition: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective_type": self.objective_type,
            "description": self.description,
            "kpis": self.kpis,
            "target_metrics": self.target_metrics,
            "timeline": self.timeline,
            "success_criteria": self.success_criteria,
            "funnel_stage": self.funnel_stage,
            "smart_objective": self.smart_objective,
            "primary_kpi": self.primary_kpi,
            "secondary_kpis": self.secondary_kpis,
            "success_criteria_definition": self.success_criteria_definition,
        }


class MarketingObjectiveEngine(IntelligenceEngine):
    """Converts user goals into measurable marketing objectives."""

    ENGINE_NAME = "marketing_objective"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 2500
    TEMPERATURE = 0.3

    def _build_prompt(self, **kwargs: Any) -> str:
        user_request = kwargs.get("user_request", "")
        business_profile = kwargs.get("business_profile", {})
        audience_profile = kwargs.get("audience_profile", {})
        budget = kwargs.get("budget", "")
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a senior marketing strategist. You convert vague user requests
into precise, measurable marketing objectives with KPIs — like a McKinsey consultant
writing a campaign brief. You think in SMART objectives, primary vs secondary KPIs,
and clear success criteria that leave no ambiguity about whether the campaign won or lost.

TASK: Convert the user's request into structured marketing objectives with a
formal SMART framework, primary and secondary KPIs with target values, and
explicit success criteria.

USER REQUEST: "{user_request}"

BUSINESS CONTEXT:
- Business Profile: {business_profile}
- Audience Profile: {audience_profile}
- Budget: {budget}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — CLASSIFY: What type of objective is this? (increase_leads, increase_sales, etc.)
  What is the user REALLY asking for? Read between the lines — "get more customers" might mean
  "increase leads" or "increase sales" depending on the business model.
Step 2 — SMART: Formulate the objective as SMART:
  - Specific: What exactly will be achieved? (not "increase sales" but "increase online sales by 30%")
  - Measurable: How will we measure it? (revenue, units, leads, signups, etc.)
  - Achievable: Is this realistic given the budget, business maturity, and market conditions?
  - Relevant: Does this align with the business's growth stage and competitive position?
  - Time-bound: By when? (specific timeframe, not "soon")
Step 3 — KPIs: What is the PRIMARY KPI (the one number that defines success)?
  What are the SECONDARY KPIs (supporting metrics that indicate progress)?
  For each, set a target value with reasoning and an industry benchmark.
Step 4 — SUCCESS: What constitutes a win? Define explicit success criteria —
  not just "good ROAS" but "ROAS ≥ 3x AND CAC ≤ ₹800 AND ≥ 500 conversions".
  Also define a "stretch goal" (what would make this exceptional) and a
  "minimum viable result" (below which the campaign should be paused).
Step 5 — FUNNEL: Where in the funnel does this objective sit?
  (awareness/consideration/conversion/retention)
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

ANALYSIS REQUIREMENTS:
1. Identify the primary objective type from:
   - increase_leads, increase_sales, launch_product, increase_footfall
   - build_awareness, customer_retention, recruitment, investor_outreach
   - brand_repositioning, market_expansion, crisis_communication
2. Define 3-5 specific KPIs with:
   - Metric name (e.g., "Cost per Lead")
   - Target value (e.g., "₹50-150")
   - Measurement method
   - Benchmark (industry standard if known)
3. Set target metrics for the campaign:
   - Expected reach, engagement rate, CTR, conversions, ROAS
4. Define timeline (short-term/medium-term/long-term)
5. Define success criteria (what constitutes a win)
6. Map to funnel stage (awareness/consideration/conversion/retention)
7. SMART Objective: Formal SMART breakdown:
   - specific: The precise outcome (e.g., "Increase online sales from ₹38L to ₹50L")
   - measurable: How it will be measured (e.g., "GA4 revenue tracking + Razorpay reconciliation")
   - achievable: Why this is realistic (e.g., "30% growth is achievable with ₹5L ad spend at 4x ROAS
     and 2.5% conversion rate — historical data supports this")
   - relevant: Why it matters to the business (e.g., "Business is in growth stage — revenue acceleration
     is the #1 priority for investor readiness")
   - time_bound: The deadline (e.g., "Within 90 days from campaign launch")
8. Primary KPI: The single most important metric:
   - metric: Name (e.g., "Revenue")
   - target_value: The target (e.g., "₹50L")
   - current_baseline: Where are we now? (e.g., "₹38L/month")
   - measurement_method: How we track it
   - benchmark: Industry benchmark for context
   - why_primary: Why this is THE metric that defines success
9. Secondary KPIs: 2-4 supporting metrics, each with:
   - metric, target_value, measurement_method, benchmark
   - role: What does this KPI tell us? (leading indicator, diagnostic, guardrail)
   Examples: CTR (leading indicator), CAC (guardrail — must not exceed ₹800),
   engagement rate (diagnostic — tells us if creative is working)
10. Success Criteria Definition: Explicit pass/fail thresholds:
   - criterion: The condition (e.g., "ROAS ≥ 3x")
   - threshold: The specific value
   - measurement_window: When is this evaluated? (e.g., "end of campaign", "weekly")
   - status_on_met: "success" / "stretch" / "minimum_viable"
   Define at least: 1 success criterion, 1 stretch goal, 1 minimum viable result.

FEW-SHOT EXAMPLE (D2C Coffee, "increase sales by 30%" — use as quality benchmark, do NOT copy):
- SMART Objective:
  specific: "Increase online D2C sales from ₹38L/month to ₹50L/month (₹12L incremental)"
  measurable: "GA4 revenue + Razorpay payment reconciliation, weekly tracking"
  achievable: "₹5L ad spend at 4x ROAS = ₹20L ad-driven revenue + ₹8L organic uplift = ₹28L total
    incremental potential. 30% growth (₹12L) is within this range with conservative assumptions."
  relevant: "Business is in growth stage with subscription model launching — revenue acceleration
    is critical for Series A readiness."
  time_bound: "90 days from campaign launch (Oct 1 – Dec 31)"
- Primary KPI:
  metric: "Monthly Revenue"
  target_value: "₹50L/month"
  current_baseline: "₹38L/month"
  measurement_method: "Razorpay total + COD collections, reconciled weekly"
  benchmark: "D2C F&B benchmark: ₹40-60L/month for brands at this stage"
  why_primary: "Revenue is the ultimate business outcome — all other KPIs serve this"
- Secondary KPIs:
  - metric: "ROAS", target_value: "≥ 4x", role: "guardrail — below 3x, pause and optimise"
  - metric: "CAC", target_value: "≤ ₹800", role: "guardrail — above ₹1,000, reduce spend"
  - metric: "CTR", target_value: "≥ 1.8%", role: "leading indicator — tells us creative is working"
  - metric: "Conversion Rate", target_value: "≥ 2.5%", role: "diagnostic — tells us landing page works"
- Success Criteria:
  - criterion: "Monthly Revenue ≥ ₹50L", threshold: "₹50L", status_on_met: "success"
  - criterion: "Monthly Revenue ≥ ₹55L", threshold: "₹55L", status_on_met: "stretch"
  - criterion: "ROAS ≥ 3x AND Revenue ≥ ₹44L", threshold: "3x + ₹44L",
    status_on_met: "minimum_viable" (below this, campaign is not working)

QUALITY RULES:
- KPIs must be SMART (Specific, Measurable, Achievable, Relevant, Time-bound)
- The SMART objective must be a complete sentence, not a fragment
- Primary KPI must be a single metric — not a composite
- Secondary KPIs must each have a clear role (leading indicator, diagnostic, guardrail)
- Success criteria must include a minimum viable result — not just the target
- Targets must be realistic given the budget and business maturity
- Every target must reference a benchmark or baseline
- Confidence 0.4-0.9
- 3-5 recommendations for achieving the objective

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "objective_type": {"type": "string"},
                "description": {"type": "string"},
                "kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "target": {"type": "string"},
                            "measurement_method": {"type": "string"},
                            "benchmark": {"type": "string"},
                        },
                    },
                },
                "target_metrics": {
                    "type": "object",
                    "properties": {
                        "expected_reach": {"type": "string"},
                        "expected_engagement_rate": {"type": "string"},
                        "expected_ctr": {"type": "string"},
                        "expected_conversions": {"type": "string"},
                        "expected_roas": {"type": "string"},
                    },
                },
                "timeline": {"type": "string"},
                "success_criteria": {"type": "string"},
                "funnel_stage": {"type": "string"},
                "smart_objective": {
                    "type": "object",
                    "properties": {
                        "specific": {"type": "string"},
                        "measurable": {"type": "string"},
                        "achievable": {"type": "string"},
                        "relevant": {"type": "string"},
                        "time_bound": {"type": "string"},
                    },
                },
                "primary_kpi": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string"},
                        "target_value": {"type": "string"},
                        "current_baseline": {"type": "string"},
                        "measurement_method": {"type": "string"},
                        "benchmark": {"type": "string"},
                        "why_primary": {"type": "string"},
                    },
                },
                "secondary_kpis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string"},
                            "target_value": {"type": "string"},
                            "measurement_method": {"type": "string"},
                            "benchmark": {"type": "string"},
                            "role": {"type": "string"},
                        },
                    },
                },
                "success_criteria_definition": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "criterion": {"type": "string"},
                            "threshold": {"type": "string"},
                            "measurement_window": {"type": "string"},
                            "status_on_met": {"type": "string"},
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
            "required": ["objective_type", "description", "kpis", "reasoning", "confidence"],
        }

    def to_objective(self, output: EngineOutput) -> MarketingObjective:
        """Convert an EngineOutput to a typed MarketingObjective.

        Delegates to MarketingObjective.from_dict() — the model owns parsing.
        """
        return MarketingObjective.from_dict(output.result)  # type: ignore[return-value]
