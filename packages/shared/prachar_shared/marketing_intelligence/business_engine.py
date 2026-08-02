"""Business Intelligence Engine.

Understands the business before any creative work begins. Produces a
structured BusinessProfile covering industry, business model, USP, pricing,
customer type, maturity, market position, seasonality, SWOT, and risks.

This is ALWAYS the first step. No creative assets are generated until
the business is understood.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prachar_shared.ai_gateway import Completion, Tier

from .base import EngineOutput, IntelligenceEngine, Recommendation
from .domain_base import DomainModel


@dataclass
class BusinessProfile(DomainModel):
    """Structured understanding of a business.

    Inherits from_dict()/validate()/schema_version() from DomainModel.
    Owned by BusinessIntelligenceEngine.
    """

    industry: str = ""
    sub_industry: str = ""
    business_model: str = ""  # B2B, B2C, D2C, B2B2C, marketplace, SaaS, etc.
    products_services: list[dict[str, Any]] = field(default_factory=list)
    usp: str = ""  # Unique Selling Proposition
    pricing_model: str = ""  # premium, mid-market, budget, freemium, etc.
    price_range: str = ""
    customer_type: str = ""  # demographics summary
    business_maturity: str = ""  # startup, growth, mature, declining
    market_position: str = ""  # leader, challenger, follower, nicher
    seasonality: dict[str, Any] = field(default_factory=dict)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    threats: list[str] = field(default_factory=list)
    target_market_size: str = ""
    competitive_landscape: str = ""
    regulatory_considerations: list[str] = field(default_factory=list)
    market_analysis: dict[str, Any] = field(default_factory=dict)
    industry_trends: list[str] = field(default_factory=list)
    barriers_to_entry: list[str] = field(default_factory=list)
    growth_stage: str = ""  # embryonic, growth, mature, declining
    key_vulnerabilities: list[str] = field(default_factory=list)
    differentiation_strategy: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "industry": self.industry,
            "sub_industry": self.sub_industry,
            "business_model": self.business_model,
            "products_services": self.products_services,
            "usp": self.usp,
            "pricing_model": self.pricing_model,
            "price_range": self.price_range,
            "customer_type": self.customer_type,
            "business_maturity": self.business_maturity,
            "market_position": self.market_position,
            "seasonality": self.seasonality,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "opportunities": self.opportunities,
            "threats": self.threats,
            "target_market_size": self.target_market_size,
            "competitive_landscape": self.competitive_landscape,
            "regulatory_considerations": self.regulatory_considerations,
            "market_analysis": self.market_analysis,
            "industry_trends": self.industry_trends,
            "barriers_to_entry": self.barriers_to_entry,
            "growth_stage": self.growth_stage,
            "key_vulnerabilities": self.key_vulnerabilities,
            "differentiation_strategy": self.differentiation_strategy,
        }


class BusinessIntelligenceEngine(IntelligenceEngine):
    """Analyzes a business and produces a structured BusinessProfile.

    This engine reasons like a McKinsey consultant + WPP strategist.
    It does NOT generate creative assets — it understands the business.
    """

    ENGINE_NAME = "business_intelligence"
    ENGINE_VERSION = "1.1.0"
    PROMPT_VERSION = "3.0.0"
    SCHEMA_VERSION = "1.2.0"
    TIER = Tier.large
    MAX_TOKENS = 4000
    TEMPERATURE = 0.3

    def _build_prompt(self, **kwargs: Any) -> str:
        business_name = kwargs.get("business_name", "")
        website = kwargs.get("website", "")
        category = kwargs.get("category", "")
        description = kwargs.get("description", "")
        brand_graph = kwargs.get("brand_graph", {})
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a senior business strategist at McKinsey & Company combined with a
WPP Group strategy director. You analyze businesses with the rigor of a management
consultant and the creative insight of an advertising agency leader. You think in
market sizes, growth curves, competitive moats, and strategic vulnerabilities.

TASK: Analyze the following business and produce a comprehensive Business Profile.
Your analysis must be evidence-based, specific, and actionable. No generic statements.
Think like you are preparing a board-level strategy memo — every claim must be defensible.

BUSINESS INFORMATION:
- Name: {business_name}
- Website: {website}
- Category: {category}
- Description: {description}
- Brand Graph: {brand_graph}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — IDENTIFY: What industry, sub-industry, and business model is this? What evidence supports this?
Step 2 — MARKET SIZING: Estimate the total addressable market (TAM), serviceable addressable market (SAM),
  and serviceable obtainable market (SOM). What is the annual growth rate? Is the market expanding,
  contracting, or maturing? What stage of the industry lifecycle is this (embryonic, growth, mature, declining)?
Step 3 — COMPETITIVE INTENSITY: How crowded is this market? Name 2-3 competitor archetypes.
  What are the barriers to entry (capital requirements, regulatory, brand equity, technology, network effects,
  switching costs)? Rate intensity as low/medium/high with justification.
Step 4 — POSITION & SWOT: Where does this business sit relative to competitors? What is its USP?
  Conduct a rigorous SWOT — each item must reference the actual business, not generic platitudes.
  Identify 3-5 key vulnerabilities that could derail growth (single-customer dependency, regulatory risk,
  margin compression, talent flight, supply chain fragility, etc.).
Step 5 — STRATEGIZE: What 3-5 strategic recommendations would drive the most growth?
  For each, specify the differentiation angle the business should own in the market.
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

INDUSTRY-SPECIFIC GUIDANCE:
- Restaurants/F&B: Focus on footfall drivers, cuisine positioning, delivery vs dine-in mix, local competition density, food cost margins, hygiene ratings, cloud-kitchen economics, Zomato/Swiggy commission impact.
- SaaS/Software: Focus on ARR/MRR metrics, CAC:LTV ratio, churn drivers, feature differentiation, integration ecosystem, sales cycle length, NRR expansion, competitive moats (data, network effects, switching costs).
- E-commerce/D2C: Focus on unit economics, return rates, ad-to-revenue ratio, supply chain reliability, brand moat, repeat purchase rate, contribution margin per order, customer cohort retention curves.
- Services/Professional: Focus on billable utilization, referral pipeline, credentialing, client retention, project margin, talent leverage, scalability constraints.
- Retail: Focus on inventory turnover, store catchment area, omnichannel readiness, private label potential, shrinkage, footfall-to-conversion ratio.
- Healthcare/Wellness: Focus on regulatory compliance, patient acquisition cost, trust signals, practitioner credibility, insurance integration, telehealth readiness.
- Real Estate: Focus on location analytics, price/sqft benchmarks, RERA compliance, lead-to-site-visit ratio, inventory absorption rate, project IRR.
- Education/EdTech: Focus on enrollment funnel, completion rates, instructor credibility, accreditation, unit economics per student, content moat.

LOCALE-AWARE GUIDANCE:
- India (en-IN/hi-IN): Consider UPI adoption, WhatsApp-first communication, Tier-2/3 city expansion, festive season spikes, price sensitivity, Jio-driven mobile penetration. Currency in INR (₹). Use lakhs/crores notation. Consider ONDC impact for e-commerce, quick-commerce (Blinkit/Zepto) for F&B.
- US (en-US): Consider credit-card penetration, Amazon Prime effect, suburban vs urban split, holiday season (Nov-Dec). Currency in USD ($). Consider Shopify ecosystem, retail media networks.
- Global/Multi-market: Consider local payment preferences, regulatory differences, cultural nuances, language localization needs, GDPR/data compliance, cross-border logistics.

ANALYSIS REQUIREMENTS:
1. Industry & Sub-Industry: Be specific (e.g., "D2C premium coffee" not just "F&B")
2. Business Model: B2B/B2C/D2C/marketplace/SaaS/etc. with revenue model
3. Products/Services: List key offerings with positioning
4. USP: The single most compelling reason customers choose this business
5. Pricing Model: premium/mid-market/budget/freemium + price range estimate
6. Customer Type: Who buys and why
7. Business Maturity: startup/growth/mature/declining with evidence
8. Market Position: leader/challenger/follower/nicher
9. Seasonality: Peak/off periods with reasoning
10. SWOT: Specific, not generic. Each item must reference the actual business.
11. Target Market Size: Estimate TAM/SAM/SOM with reasoning and currency
12. Competitive Landscape: Name 2-3 competitor archetypes with estimated market share
13. Regulatory: Any industry-specific regulations to consider
14. Market Analysis: Assess market_size, growth_rate, competition_intensity, and barriers_to_entry.
    - market_size: Estimated total addressable market with reasoning (TAM/SAM/SOM if possible)
    - growth_rate: Is the market growing, stable, or declining? Percentage estimate with timeframe.
    - competition_intensity: low/medium/high — how crowded is this space? Justify with competitor count and concentration.
    - barriers_to_entry: What stops new entrants? (capital, regulation, brand, tech, network effects, switching costs)
15. Industry Trends: 3-5 current trends shaping this industry (technology shifts, consumer behaviour changes,
    regulatory developments, M&A activity, emerging business models). Each trend must note whether it is an
    opportunity or threat for this business.
16. Growth Stage: Classify the industry lifecycle stage (embryonic, growth, mature, declining) with evidence.
17. Key Vulnerabilities: 3-5 specific risks that could derail this business (not generic "competition" —
    name the actual vulnerability: e.g., "Single-supplier dependency on Coorg coffee estates" or
    "70% revenue from Instagram ads — algorithm change risk").
18. Differentiation Strategy: How should this business differentiate from competitors?
    What unique angle or positioning should they own? Specify the "only X does Y" statement.

FEW-SHOT EXAMPLE (D2C Coffee — use as quality benchmark, do NOT copy):
- Industry: "D2C Premium Specialty Coffee"
- Market Analysis: market_size="₹2,000 Cr premium coffee (TAM), ₹500 Cr D2C segment (SAM), ₹20 Cr obtainable (SOM)",
  growth_rate="18% CAGR (2024-2027), driven by premiumisation and home-brewing culture",
  competition_intensity="high — 15+ D2C brands in metro markets, but Tier-2/3 is underserved",
  barriers_to_entry=["Roasting equipment capex (₹15-40L)", "Direct trade relationships (3-5 years to build)",
    "Brand storytelling capability", "Cold-chain logistics for freshness"]
- Industry Trends: ["Quick-commerce partnerships expanding reach (opportunity)",
    "Single-origin transparency becoming table-stakes (threat — commoditises USP)",
    "Subscription models driving 40%+ of D2C revenue (opportunity)"]
- Growth Stage: "growth — market doubling every 4 years, but early leaders emerging"
- Key Vulnerabilities: ["Coffee bean price volatility (40% YoY swings possible)",
    "Blue Tokai/Sleepy Owl could enter subscription space with deeper pockets",
    "Single-origin sourcing concentrated in 2 estates — climate risk"]
- Differentiation Strategy: "Own 'farm-to-cup traceability' — the only Indian coffee brand that names every farmer.

QUALITY RULES:
- Every claim must have reasoning in the "reasoning" field
- Confidence scores must reflect actual certainty (0.3-0.9 range typical)
- If information is insufficient, set confidence low and note it
- Provide 3-5 key strategic recommendations
- Each recommendation must include business_rationale and marketing_rationale
- Market analysis must be specific to the industry and locale, not generic
- Industry trends must be current (2024-2025), not stale
- Key vulnerabilities must be specific to THIS business, not industry-wide platitudes
- Growth stage must be justified with market evidence

OUTPUT SCHEMA: Return JSON matching the provided schema. Include a "reasoning" field
explaining your analysis approach (show the 5-step reasoning chain), a "confidence"
field (0.0-1.0), and a "recommendations" array with full rationale for each.
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "industry": {"type": "string"},
                "sub_industry": {"type": "string"},
                "business_model": {"type": "string"},
                "products_services": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "positioning": {"type": "string"},
                            "price_point": {"type": "string"},
                        },
                    },
                },
                "usp": {"type": "string"},
                "pricing_model": {"type": "string"},
                "price_range": {"type": "string"},
                "customer_type": {"type": "string"},
                "business_maturity": {"type": "string"},
                "market_position": {"type": "string"},
                "seasonality": {
                    "type": "object",
                    "properties": {
                        "peak_periods": {"type": "array", "items": {"type": "string"}},
                        "off_periods": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "string"},
                    },
                },
                "strengths": {"type": "array", "items": {"type": "string"}},
                "weaknesses": {"type": "array", "items": {"type": "string"}},
                "opportunities": {"type": "array", "items": {"type": "string"}},
                "threats": {"type": "array", "items": {"type": "string"}},
                "target_market_size": {"type": "string"},
                "competitive_landscape": {"type": "string"},
                "regulatory_considerations": {"type": "array", "items": {"type": "string"}},
                "market_analysis": {
                    "type": "object",
                    "properties": {
                        "market_size": {"type": "string"},
                        "growth_rate": {"type": "string"},
                        "competition_intensity": {"type": "string"},
                        "barriers_to_entry": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "industry_trends": {"type": "array", "items": {"type": "string"}},
                "growth_stage": {"type": "string"},
                "key_vulnerabilities": {"type": "array", "items": {"type": "string"}},
                "differentiation_strategy": {"type": "string"},
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
            "required": ["industry", "business_model", "usp", "reasoning", "confidence"],
        }

    def _parse_result(self, comp: Completion) -> EngineOutput:
        result = comp.json_value or {}
        recommendations = self._extract_recommendations(result)
        confidence = float(result.get("confidence", comp.confidence or 0.5))
        reasoning = result.get("reasoning", "")

        return EngineOutput(
            result=result,
            confidence=confidence,
            reasoning=reasoning,
            recommendations=recommendations,
        )

    def to_profile(self, output: EngineOutput) -> BusinessProfile:
        """Convert an EngineOutput to a typed BusinessProfile.

        Delegates to BusinessProfile.from_dict() — the model owns parsing.
        """
        return BusinessProfile.from_dict(output.result)  # type: ignore[return-value]
