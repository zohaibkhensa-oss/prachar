"""Competitor Intelligence Engine.

Analyzes top competitors: market messaging, creative positioning, offer
strategy, pricing, communication style, and market gaps. Produces a
SWOT comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel


@dataclass
class CompetitorProfile(DomainModel):
    """Structured competitor analysis.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by CompetitorIntelligenceEngine.
    """

    competitors: list[dict[str, Any]] = field(default_factory=list)
    market_gaps: list[str] = field(default_factory=list)
    swot_comparison: dict[str, Any] = field(default_factory=dict)
    positioning_map: dict[str, Any] = field(default_factory=dict)
    messaging_analysis: dict[str, Any] = field(default_factory=dict)
    pricing_comparison: dict[str, Any] = field(default_factory=dict)
    differentiation_strategy: str = ""
    competitive_positioning: list[dict[str, Any]] = field(default_factory=list)
    competitor_response_predictions: list[dict[str, Any]] = field(default_factory=list)
    market_gap_analysis: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "competitors": self.competitors,
            "market_gaps": self.market_gaps,
            "swot_comparison": self.swot_comparison,
            "positioning_map": self.positioning_map,
            "messaging_analysis": self.messaging_analysis,
            "pricing_comparison": self.pricing_comparison,
            "differentiation_strategy": self.differentiation_strategy,
            "competitive_positioning": self.competitive_positioning,
            "competitor_response_predictions": self.competitor_response_predictions,
            "market_gap_analysis": self.market_gap_analysis,
        }


class CompetitorIntelligenceEngine(IntelligenceEngine):
    """Analyzes competitors with the rigor of a competitive intelligence firm."""

    ENGINE_NAME = "competitor_intelligence"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "2.0.0"
    SCHEMA_VERSION = "1.1.0"
    TIER = Tier.large
    MAX_TOKENS = 3500
    TEMPERATURE = 0.3

    def _build_prompt(self, **kwargs: Any) -> str:
        business_profile = kwargs.get("business_profile", {})
        business_name = kwargs.get("business_name", "")
        industry = kwargs.get("industry", "")
        known_competitors = kwargs.get("known_competitors", [])
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a competitive intelligence analyst at a top strategy consulting firm.
You analyze competitors with the depth of a market researcher and the strategic
insight of a brand consultant. You don't just LIST competitors — you predict how
they will react, identify exploitable gaps, and craft a differentiation strategy
that creates defensible market space.

TASK: Analyze the competitive landscape for this business and produce a
differentiation strategy, not just a competitor list.

BUSINESS CONTEXT:
- Name: {business_name}
- Industry: {industry}
- Business Profile: {business_profile}
- Known Competitors: {known_competitors}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — MAP: Who are the top 3-5 competitors? What is each one's market position,
  messaging, pricing, strengths, and weaknesses?
Step 2 — POSITION: Place each competitor on a positioning map (2 key dimensions).
  Where is the business vs. where should it be? Identify white-space.
Step 3 — CLASSIFY: Assign each competitor a role: leader, challenger, follower, nicher.
  What does their role tell you about their likely behaviour?
Step 4 — PREDICT: If this business launches its campaign, how will each competitor
  react? Will they ignore, copy, counter-attack, or retreat? What is the timing?
Step 5 — DIFFERENTIATE: What is the defensible differentiation strategy? What gap
  can this business own that competitors cannot easily copy?
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

ANALYSIS REQUIREMENTS:
1. Top 3-5 Competitors: For each, analyze:
   - Name and market position
   - Messaging strategy (what they say)
   - Creative positioning (how they look/feel)
   - Offer strategy (what they promote)
   - Pricing approach
   - Communication style/tone
   - Strengths and weaknesses
   - Estimated market share (if known)
2. Market Gaps: 3-5 underserved areas or unmet needs in the market.
3. SWOT Comparison: Compare the business vs. the competitive field.
4. Positioning Map: Where each competitor sits on key dimensions
   (e.g., price vs. quality, traditional vs. modern).
5. Messaging Analysis: Common themes and white-space opportunities.
6. Pricing Comparison: How the business's pricing compares.
7. Differentiation Strategy: The defensible angle this business should own.
   Not just "be different" — specify the exact positioning, the "only X does Y" statement,
   and why competitors cannot easily copy it (what is their constraint?).
8. Competitive Positioning: Classify each competitor (and the business) as:
   - leader: Dominant market share, sets the agenda
   - challenger: Significant player attacking the leader
   - follower: Copies/adapts rather than innovates
   - nicher: Serves a specific segment exceptionally well
   For each, note their strategic posture (aggressive, defensive, passive, opportunistic).
9. Competitor Response Predictions: For each major competitor, predict:
   - competitor: Name
   - likely_response: ignore / copy / counter-attack / retreat / escalate
   - timing: immediate (within 2 weeks) / short-term (1-3 months) / long-term (3-6 months)
   - probable_tactic: What specific action will they take? (price cut, ad spend increase,
     new product launch, influencer push, SEO counter-attack)
   - our_counter: How should we pre-empt or respond?
10. Market Gap Analysis: For each gap identified:
    - gap: The unmet need or underserved area
    - why_it_exists: Why hasn't a competitor filled this yet? (blind spot, resource constraint,
      strategic choice, capability gap)
    - opportunity_size: Small / medium / large — how many customers does this represent?
    - exploitability: easy / moderate / hard — how quickly can we capture it?
    - first_mover_advantage: Will being first create a defensible position? yes / no / partial

FEW-SHOT EXAMPLE (D2C Coffee — use as quality benchmark, do NOT copy):
- Differentiation Strategy: "Own 'named-farm traceability' — the only Indian coffee brand
  that publishes every farmer's name, story, and payment on the pack. Competitors cannot
  copy this because Blue Tokai sources from estates (not individual farmers) and Sleepy Owl
  is built on blend consistency, not single-origin storytelling."
- Competitive Positioning:
  - competitor: "Blue Tokai" → role: "leader", posture: "defensive — protects premium positioning"
  - competitor: "Sleepy Owl" → role: "challenger", posture: "aggressive — pushing cold brew and convenience"
  - competitor: "Third Wave" → role: "nicher", posture: "opportunistic — cafe-led, not D2C"
  - our business → role: "challenger", posture: "aggressive — attacking the traceability gap"
- Competitor Response Predictions:
  - competitor: "Blue Tokai"
    likely_response: "counter-attack"
    timing: "short-term (1-3 months)"
    probable_tactic: "Launch a 'meet the farmer' content series to neutralise our traceability USP"
    our_counter: "Double down on pack-level traceability (QR codes linking to farmer profiles) —
      content is copyable, product-level proof is not"
- Market Gap Analysis:
  - gap: "Tier-2 city subscription delivery (no D2C coffee brand serves Indore, Jaipur, Coimbatore)"
    why_it_exists: "D2C brands focus on metro markets where cold-chain logistics are easier"
    opportunity_size: "medium — ~500K premium coffee drinkers in Tier-2 cities"
    exploitability: "moderate — requires logistics partner investment but no competitor presence"
    first_mover_advantage: "yes — establishing subscription in Tier-2 before competitors creates switching-cost moat"

QUALITY RULES:
- Name real competitor archetypes even if specific names are estimated
- Be specific about messaging patterns, not generic
- Market gaps must be actionable — each must explain WHY it exists and HOW to exploit it
- Competitor response predictions must be realistic — not every competitor will "counter-attack"
- Differentiation strategy must explain why competitors CANNOT easily copy it
- Confidence 0.3-0.8 (competitive intel has inherent uncertainty)
- 3-5 recommendations for competitive advantage

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "competitors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "market_position": {"type": "string"},
                            "messaging_strategy": {"type": "string"},
                            "creative_positioning": {"type": "string"},
                            "offer_strategy": {"type": "string"},
                            "pricing_approach": {"type": "string"},
                            "communication_style": {"type": "string"},
                            "strengths": {"type": "array", "items": {"type": "string"}},
                            "weaknesses": {"type": "array", "items": {"type": "string"}},
                            "estimated_market_share": {"type": "string"},
                        },
                    },
                },
                "market_gaps": {"type": "array", "items": {"type": "string"}},
                "swot_comparison": {
                    "type": "object",
                    "properties": {
                        "our_strengths": {"type": "array", "items": {"type": "string"}},
                        "our_weaknesses": {"type": "array", "items": {"type": "string"}},
                        "competitor_strengths": {"type": "array", "items": {"type": "string"}},
                        "competitor_weaknesses": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "positioning_map": {
                    "type": "object",
                    "properties": {
                        "x_axis": {"type": "string"},
                        "y_axis": {"type": "string"},
                        "positions": {"type": "array", "items": {"type": "object"}},
                    },
                },
                "messaging_analysis": {
                    "type": "object",
                    "properties": {
                        "common_themes": {"type": "array", "items": {"type": "string"}},
                        "white_space": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "pricing_comparison": {
                    "type": "object",
                    "properties": {
                        "our_position": {"type": "string"},
                        "market_range": {"type": "string"},
                        "analysis": {"type": "string"},
                    },
                },
                "differentiation_strategy": {"type": "string"},
                "competitive_positioning": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "role": {"type": "string"},
                            "strategic_posture": {"type": "string"},
                        },
                    },
                },
                "competitor_response_predictions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "competitor": {"type": "string"},
                            "likely_response": {"type": "string"},
                            "timing": {"type": "string"},
                            "probable_tactic": {"type": "string"},
                            "our_counter": {"type": "string"},
                        },
                    },
                },
                "market_gap_analysis": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "gap": {"type": "string"},
                            "why_it_exists": {"type": "string"},
                            "opportunity_size": {"type": "string"},
                            "exploitability": {"type": "string"},
                            "first_mover_advantage": {"type": "string"},
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
            "required": ["competitors", "market_gaps", "reasoning", "confidence"],
        }

    def to_profile(self, output: EngineOutput) -> CompetitorProfile:
        """Convert an EngineOutput to a typed CompetitorProfile.

        Delegates to CompetitorProfile.from_dict() — the model owns parsing.
        """
        return CompetitorProfile.from_dict(output.result)  # type: ignore[return-value]
