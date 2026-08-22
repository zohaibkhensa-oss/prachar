"""Campaign Strategy Engine.

Owns: business strategy, core message, campaign direction, customer journey,
marketing funnel, communication intent, content pillars, campaign duration,
key insights.

Does NOT own (removed in Architecture Stabilisation Sprint):
- budget split → Budget Intelligence Engine
- channel allocation → Media Planning Engine
- media schedule → Media Planning Engine
- success metrics / KPIs → Marketing Objective Engine

The strategy outputs *strategic intent* (e.g., "lead with Instagram, video-first"),
not *tactical allocation* (e.g., "Instagram 40%, YouTube 25%"). Tactical
allocation is owned by the Media Planning Engine.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from prachar_shared.ai_gateway import AIGateway, BudgetExceeded, Completion, Tier
from prachar_shared.ai_gateway.json_utils import extract_json

from .base import EngineOutput, IntelligenceEngine
from .domain_base import DomainModel

logger = logging.getLogger(__name__)


@dataclass
class CampaignStrategy(DomainModel):
    """Complete campaign strategy — strategic intent only, no tactical allocation.

    Owned by CampaignStrategyEngine. Versioned for forward compatibility.
    Inherits from_dict()/validate()/schema_version() from DomainModel.
    """

    SCHEMA_VERSION = "2.0.0"  # Phase 1 removed media_mix, budget_allocation, success_metrics

    core_message: str = ""
    communication_theme: str = ""
    emotional_angle: str = ""
    marketing_funnel: list[dict[str, Any]] = field(default_factory=list)
    customer_journey: list[dict[str, Any]] = field(default_factory=list)
    content_pillars: list[dict[str, Any]] = field(default_factory=list)
    channel_intent: str = ""  # Strategic intent: "lead with Instagram, video-first"
    budget_philosophy: str = ""  # Strategic guidance: "concentrate spend on 2 channels"
    campaign_duration: str = ""
    key_insights: list[str] = field(default_factory=list)
    funnel_design: list[dict[str, Any]] = field(default_factory=list)
    channel_selection_rationale: list[dict[str, Any]] = field(default_factory=list)
    kpi_forecasting: dict[str, Any] = field(default_factory=dict)
    seasonality_considerations: dict[str, Any] = field(default_factory=dict)
    localisation_notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_message": self.core_message,
            "communication_theme": self.communication_theme,
            "emotional_angle": self.emotional_angle,
            "marketing_funnel": self.marketing_funnel,
            "customer_journey": self.customer_journey,
            "content_pillars": self.content_pillars,
            "channel_intent": self.channel_intent,
            "budget_philosophy": self.budget_philosophy,
            "campaign_duration": self.campaign_duration,
            "key_insights": self.key_insights,
            "funnel_design": self.funnel_design,
            "channel_selection_rationale": self.channel_selection_rationale,
            "kpi_forecasting": self.kpi_forecasting,
            "seasonality_considerations": self.seasonality_considerations,
            "localisation_notes": self.localisation_notes,
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.core_message:
            errors.append("core_message is required")
        if not self.communication_theme:
            errors.append("communication_theme is required")
        return errors


class CampaignStrategyEngine(IntelligenceEngine):
    """Creates campaign strategy from business + audience + competitor intel.

    Owns strategic intent. Does NOT own tactical allocation — that belongs
    to MediaPlanningEngine (channels) and BudgetIntelligenceEngine (costs).
    """

    ENGINE_NAME = "campaign_strategy"
    ENGINE_VERSION = "2.1.0"  # Bumped: removed media_mix, budget_allocation, success_metrics
    PROMPT_VERSION = "3.0.0"  # Bumped: added funnel design, channel rationale, KPI forecasting, seasonality, localisation
    SCHEMA_VERSION = "2.1.0"  # Bumped: schema changed (removed fields, added channel_intent, budget_philosophy)
    TIER = Tier.large
    MAX_TOKENS = 4000
    TEMPERATURE = 0.4

    def _build_prompt(self, **kwargs: Any) -> str:
        business_profile = kwargs.get("business_profile", {})
        audience_profile = kwargs.get("audience_profile", {})
        competitor_profile = kwargs.get("competitor_profile", {})
        objective = kwargs.get("objective", {})
        budget = kwargs.get("budget", "")
        locale = kwargs.get("locale", "en-IN")
        additional_context = kwargs.get("additional_context", "")

        return f"""ROLE: You are a Chief Strategy Officer at a top global advertising agency
(Ogilvy/BBDO/Wieden+Kennedy). You create campaign strategies that win Cannes Lions
and drive measurable business results. You design funnels with surgical precision,
choose channels with evidence-based rationale, forecast KPIs against industry
benchmarks, and adapt to seasonal and cultural realities of the target market.

TASK: Create a campaign strategy. You own STRATEGIC INTENT — not tactical allocation.
A separate Media Planning Engine will handle channel selection and budget split.
A separate Budget Engine will handle cost estimation. Focus on strategy.

INPUTS:
- Business Profile: {business_profile}
- Audience Profile: {audience_profile}
- Competitor Profile: {competitor_profile}
- Marketing Objective: {objective}
- Budget: {budget}
- Locale: {locale}
{f"- Additional Context: {additional_context}" if additional_context else ""}

REASONING PROCESS (follow this chain-of-thought before producing your answer):
Step 1 — MESSAGE: What is the ONE thing the audience must remember? Craft a core message
  that is memorable, differentiated from competitors, and emotionally resonant.
Step 2 — FUNNEL: Design the full funnel: TOFU (awareness) → MOFU (consideration) → BOFU (conversion).
  For each stage, specify the goal, content intent, specific tactics, and the emotional shift
  you want to create in the audience.
Step 3 — CHANNELS: Which channels should lead and why? Tie each channel to a specific audience
  segment and journey stage. Explain why this channel for this audience — not just "Instagram is popular."
Step 4 — FORECAST: What KPIs can we expect? Forecast reach, engagement, and conversion rates
  against industry benchmarks. Be conservative — over-promising destroys trust.
Step 5 — ADAPT: What seasonal and cultural factors affect this campaign? When should we launch?
  What localisation nuances matter for this locale?
Write your reasoning in the "reasoning" field showing this step-by-step analysis.

STRATEGY REQUIREMENTS (you own these):
1. Core Message: The ONE thing the audience must remember (max 15 words).
2. Communication Theme: The overarching narrative thread.
3. Emotional Angle: The primary emotion to evoke (aspiration, fear, joy, trust, etc.)
4. Marketing Funnel: Map TOFU → MOFU → BOFU with content intent at each stage.
5. Customer Journey: Step-by-step from first touch to conversion to advocacy.
6. Content Pillars: 3-5 thematic pillars that all content maps to.
7. Channel Intent: Strategic guidance on which channels to prioritize and why
   (e.g., "Lead with Instagram for visual storytelling, YouTube for long-form education").
   Do NOT allocate percentages or budgets — that is the Media Planning Engine's job.
8. Budget Philosophy: Strategic guidance on how to approach budget
   (e.g., "Concentrate spend on 2 high-ROI channels rather than spreading thin").
   Do NOT produce cost numbers — that is the Budget Engine's job.
9. Campaign Duration: Recommended timeline with phases.
10. Key Insights: 3-5 strategic insights that inform the strategy.
11. Funnel Design: Detailed TOFU/MOFU/BOFU design. For each stage:
    - stage: "TOFU" / "MOFU" / "BOFU"
    - goal: What we want the audience to do/feel at this stage
    - tactics: 2-4 specific tactics for this stage (e.g., "Reels with trending audio",
      "Carousel educating on direct trade", "Retargeting with subscription offer")
    - content_intent: The purpose of content at this stage
    - audience_segment: Which psychographic segment this targets
    - emotional_shift: How the audience's emotional state should change
    - success_indicator: What tells us this stage is working
12. Channel Selection Rationale: For each recommended channel:
    - channel: Name (Instagram, YouTube, LinkedIn, etc.)
    - why_this_channel: Why this channel for THIS audience (tie to audience platform behaviour)
    - funnel_stage: Which funnel stage this channel serves best (TOFU/MOFU/BOFU)
    - content_fit: Why the channel's native format fits our content
    - audience_evidence: What we know about the audience on this platform
    Do NOT allocate percentages — that is the Media Planning Engine's job.
13. KPI Forecasting: Forecast expected performance against benchmarks:
    - expected_reach: Estimated reach with reasoning
    - expected_engagement_rate: Estimated engagement rate with industry benchmark
    - expected_ctr: Estimated CTR with industry benchmark
    - expected_conversion_rate: Estimated conversion rate with industry benchmark
    - benchmark_source: Where do these benchmarks come from? (industry report, historical data, etc.)
    - assumptions: What assumptions underpin these forecasts?
14. Seasonality Considerations:
    - best_launch_window: When should this campaign launch? Why?
    - peak_periods: When is demand highest for this product/service?
    - off_periods: When should we reduce spend or pause?
    - seasonal_content_hooks: Festival/seasonal moments to leverage (Diwali, Christmas, summer, monsoon, etc.)
    - competitive_seasonality: When do competitors ramp up? Should we counter or avoid?
15. Localisation Notes:
    - cultural_nuances: Cultural factors that affect messaging (e.g., "In India, coffee is aspirational,
      not functional — lead with craft, not caffeine")
    - language_considerations: Which languages? Tone? Formality level?
    - visual_localisation: Visual elements that resonate locally (colours, imagery, people, settings)
    - platform_localisation: Platform preferences specific to this locale (e.g., "WhatsApp for India,
      LINE for Japan, WeChat for China")
    - taboo_avoidance: What to avoid in this culture (religious sensitivities, political topics, etc.)

DO NOT OUTPUT (owned by other engines):
- Channel budget percentages → Media Planning Engine
- Publishing frequency per channel → Media Planning Engine
- Cost estimates, ROI, CAC → Budget Intelligence Engine
- KPIs, targets, success metrics → Marketing Objective Engine

FEW-SHOT EXAMPLE (D2C Coffee, en-IN — use as quality benchmark, do NOT copy):
- Funnel Design:
  - TOFU: goal="Make coffee lovers discover the brand through craft storytelling",
    tactics=["Reels showing farmer interviews", "Carousel on 'what direct trade actually means'",
      "YouTube 8-min origin documentary"], audience_segment="The Ritualist",
    emotional_shift="From unaware → curious about the story behind their cup",
    success_indicator="3%+ save rate on Reels, 500+ YouTube subs in month 1"
  - MOFU: goal="Build trust through education and social proof",
    tactics=["Brewing tutorial carousels", "Customer review UGC reposts",
      "WhatsApp broadcast with exclusive roast dates"], audience_segment="The Ritualist + The Gifter",
    emotional_shift="From curious → convinced this is worth the premium price",
    success_indicator="5%+ CTR on retargeting, 2%+ email/WhatsApp signup from site"
  - BOFU: goal="Convert with urgency and risk-reversal",
    tactics=["First-order discount + free shipping", "Subscription trial (first month 50% off)",
      "Retargeting with 'named farmer' pack shots"], audience_segment="All segments",
    emotional_shift="From convinced → committed (first purchase)",
    success_indicator="2.5%+ conversion rate on landing page, ₹800 CAC target"
- KPI Forecasting: expected_reach="1.5M (Instagram 1M + YouTube 500K)",
  expected_engagement_rate="4.5% (benchmark: 3.2% for F&B D2C)",
  expected_ctr="1.8% (benchmark: 1.2% for Instagram retail)",
  expected_conversion_rate="2.5% (benchmark: 2.0% for D2C coffee)",
  benchmark_source="Meta F&B benchmarks 2024, historical D2C coffee data",
  assumptions="₹5L budget, 12-week campaign, no major competitor launch during period"
- Seasonality: best_launch_window="October (pre-Diwali — gifting season)",
  peak_periods="Oct-Dec (festive gifting), Jan (New Year resolutions)",
  off_periods="Jul-Aug (monsoon — lower discretionary spend)",
  seasonal_content_hooks=["Diwali gifting hampers", "New Year 'brew better' resolution content"],
  competitive_seasonality="Blue Tokai ramps up Oct-Nov — launch 2 weeks early to pre-empt"
- Localisation: cultural_nuances="In India, premium coffee is aspirational and gift-worthy,
  not a daily necessity — lead with craft and story, not caffeine stats",
  language_considerations="English for metro audience, Hinglish for broader reach",
  visual_localisation="Show Indian farmers, Indian kitchens, Indian settings — not stock Western imagery",
  platform_localisation="WhatsApp broadcast for subscription updates (India's #1 comms channel)",
  taboo_avoidance="Avoid religious imagery in Diwali campaigns — use cultural colours and motifs instead"

QUALITY RULES:
- The core message must be memorable and differentiated from competitors
- Content pillars must be specific to this business, not generic
- Channel intent must be strategic ("why") not tactical ("how much")
- Funnel design must have specific tactics, not vague "create awareness content"
- KPI forecasts must cite benchmarks — do not pull numbers from thin air
- Seasonality must be specific to the industry and locale
- Localisation must go beyond "use local language" — address cultural nuances
- Every choice must have reasoning
- Confidence 0.4-0.8
- 3-5 strategic recommendations

OUTPUT: JSON matching the schema. Include "reasoning", "confidence", "recommendations".
"""

    def _build_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "core_message": {"type": "string"},
                "communication_theme": {"type": "string"},
                "emotional_angle": {"type": "string"},
                "marketing_funnel": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stage": {"type": "string"},
                            "goal": {"type": "string"},
                            "content_intent": {"type": "string"},
                        },
                    },
                },
                "customer_journey": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "string"},
                            "action": {"type": "string"},
                            "touchpoint": {"type": "string"},
                            "content": {"type": "string"},
                        },
                    },
                },
                "content_pillars": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "pillar": {"type": "string"},
                            "description": {"type": "string"},
                            "content_types": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "channel_intent": {"type": "string"},
                "budget_philosophy": {"type": "string"},
                "campaign_duration": {"type": "string"},
                "key_insights": {"type": "array", "items": {"type": "string"}},
                "funnel_design": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "stage": {"type": "string"},
                            "goal": {"type": "string"},
                            "tactics": {"type": "array", "items": {"type": "string"}},
                            "content_intent": {"type": "string"},
                            "audience_segment": {"type": "string"},
                            "emotional_shift": {"type": "string"},
                            "success_indicator": {"type": "string"},
                        },
                    },
                },
                "channel_selection_rationale": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "channel": {"type": "string"},
                            "why_this_channel": {"type": "string"},
                            "funnel_stage": {"type": "string"},
                            "content_fit": {"type": "string"},
                            "audience_evidence": {"type": "string"},
                        },
                    },
                },
                "kpi_forecasting": {
                    "type": "object",
                    "properties": {
                        "expected_reach": {"type": "string"},
                        "expected_engagement_rate": {"type": "string"},
                        "expected_ctr": {"type": "string"},
                        "expected_conversion_rate": {"type": "string"},
                        "benchmark_source": {"type": "string"},
                        "assumptions": {"type": "string"},
                    },
                },
                "seasonality_considerations": {
                    "type": "object",
                    "properties": {
                        "best_launch_window": {"type": "string"},
                        "peak_periods": {"type": "array", "items": {"type": "string"}},
                        "off_periods": {"type": "array", "items": {"type": "string"}},
                        "seasonal_content_hooks": {"type": "array", "items": {"type": "string"}},
                        "competitive_seasonality": {"type": "string"},
                    },
                },
                "localisation_notes": {
                    "type": "object",
                    "properties": {
                        "cultural_nuances": {"type": "string"},
                        "language_considerations": {"type": "string"},
                        "visual_localisation": {"type": "string"},
                        "platform_localisation": {"type": "string"},
                        "taboo_avoidance": {"type": "string"},
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
            "required": ["core_message", "communication_theme", "channel_intent", "reasoning", "confidence"],
        }

    def to_strategy(self, output: EngineOutput) -> CampaignStrategy:
        """Parse engine output into a CampaignStrategy domain model.

        Delegates to CampaignStrategy.from_dict() — the model owns parsing.
        """
        return CampaignStrategy.from_dict(output.result)  # type: ignore[return-value]


# ─── Multi-Strategy Engine (B.1.1 + B.1.2) ────────────────────────────────────
#
# CURV AI thinks like a strategist: instead of generating ONE campaign per request,
# it generates 3 genuinely different strategies (primary, alternative, contrarian)
# and then explains WHY it chose the primary over the others.
#
# This is the core IP that makes CURV AI hard to copy — the "why A not B" layer.


# Valid strategy types — the 3 strategies must each be one of these.
_STRATEGY_TYPES = ("primary", "alternative", "contrarian")


@dataclass
class Strategy:
    """A single marketing strategy proposed by the StrategyEngine.

    One of three strategies generated per campaign:
      - primary:     the recommended approach (highest probability of success)
      - alternative: a different valid approach to the same goal
      - contrarian:  an unconventional approach that could work

    Attributes:
        name: A short, memorable name for the strategy (e.g. "Signature Dish Hero").
        approach: 2-3 sentences describing the strategic approach.
        why_it_works: 1-2 sentences explaining why this approach is effective
            for this business/audience/budget combination.
        risks: 2-3 specific risks of this approach.
        expected_outcome: 1 sentence on the expected result if executed well.
        strategy_type: "primary", "alternative", or "contrarian".
    """

    name: str = ""
    approach: str = ""
    why_it_works: str = ""
    risks: list[str] = field(default_factory=list)
    expected_outcome: str = ""
    strategy_type: str = "primary"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _default_strategies() -> list[Strategy]:
    """Return 3 fallback strategies used when AI generation fails.

    These are intentionally generic so the campaign preview still works
    without the strategy layer. The caller can proceed with these and the
    rest of the pipeline continues unaffected.
    """
    return [
        Strategy(
            name="Balanced Growth Approach",
            approach=(
                "A balanced mix of awareness and direct-response marketing "
                "across the most relevant channels for the audience."
            ),
            why_it_works=(
                "Balances reach with conversion, suitable for most budgets "
                "and goals without over-concentrating risk."
            ),
            risks=["May not stand out in a crowded market", "Slower initial traction"],
            expected_outcome="Steady growth in enquiries and brand awareness over 30 days.",
            strategy_type="primary",
        ),
        Strategy(
            name="Content-Led Authority Play",
            approach=(
                "Build trust and authority through educational content before "
                "pushing direct offers."
            ),
            why_it_works=(
                "Trust compounds over time and lowers acquisition cost for "
                "future campaigns."
            ),
            risks=["Longer time to first result", "Requires consistent content output"],
            expected_outcome="Gradual audience growth and warmer leads over 60-90 days.",
            strategy_type="alternative",
        ),
        Strategy(
            name="Community-First Pivot",
            approach=(
                "Invest in building a loyal community (WhatsApp, newsletter, "
                "or local group) before scaling paid acquisition."
            ),
            why_it_works=(
                "A loyal community provides repeat business and word-of-mouth "
                "at near-zero marginal cost."
            ),
            risks=["Hard to measure short-term ROI", "Requires dedicated community effort"],
            expected_outcome="A self-sustaining referral engine within 3-6 months.",
            strategy_type="contrarian",
        ),
    ]


def _parse_strategies(raw: Any) -> list[Strategy]:
    """Normalise parsed JSON into exactly 3 Strategy dataclasses.

    Ensures the 3 strategy types (primary, alternative, contrarian) are
    present and in order. Missing or malformed entries are filled from the
    default fallback set so the caller always receives 3 valid strategies.
    """
    if not isinstance(raw, dict):
        raw = {}
    raw_list = raw.get("strategies") or []
    if not isinstance(raw_list, list):
        raw_list = []

    parsed: dict[str, Strategy] = {}
    for item in raw_list[:3]:
        if not isinstance(item, dict):
            continue
        stype = str(item.get("strategy_type", "") or "").strip().lower()
        if stype not in _STRATEGY_TYPES:
            continue
        risks = item.get("risks") or []
        if not isinstance(risks, list):
            risks = [str(risks)] if risks else []
        parsed[stype] = Strategy(
            name=str(item.get("name", "") or "").strip(),
            approach=str(item.get("approach", "") or "").strip(),
            why_it_works=str(item.get("why_it_works", "") or "").strip(),
            risks=[str(r) for r in risks],
            expected_outcome=str(item.get("expected_outcome", "") or "").strip(),
            strategy_type=stype,
        )

    # Build the ordered result, falling back to defaults for missing types
    defaults = _default_strategies()
    result: list[Strategy] = []
    for i, stype in enumerate(_STRATEGY_TYPES):
        if stype in parsed and parsed[stype].name:
            result.append(parsed[stype])
        else:
            result.append(defaults[i])
    return result


class StrategyEngine:
    """Generates 3 distinct marketing strategies and explains the choice.

    CURV AI thinks like a strategist: instead of one campaign, it proposes three
    genuinely different approaches — a primary (recommended), an alternative
    (different valid lever), and a contrarian (unconventional but viable) —
    then explains why the primary was chosen over the others.

    Usage::

        engine = StrategyEngine(gateway=gw, tenant_id=user.tenant_id, plan="agency")
        strategies = await engine.generate_strategies(
            business_context={...}, audience_context={...},
            competitor_context={...}, budget="₹50,000", goal="get more customers",
        )
        explanation = await engine.explain_choice(
            strategies=strategies,
            business_context={...}, audience_context={...},
            budget="₹50,000", goal="get more customers",
        )
    """

    def __init__(self, gateway: AIGateway, tenant_id: Any, plan: str) -> None:
        self._gateway = gateway
        self._tenant_id = tenant_id
        self._plan = plan

    async def generate_strategies(
        self,
        business_context: dict[str, Any],
        audience_context: dict[str, Any],
        competitor_context: dict[str, Any],
        budget: str,
        goal: str,
    ) -> list[Strategy]:
        """Generate 3 distinct strategies: primary, alternative, contrarian.

        Each strategy is genuinely different in approach — not a variation of
        the same tactic. Uses AIGateway with Tier.large and extract_json.

        Falls back to 3 default strategies on any AI failure so the campaign
        preview still works. Re-raises BudgetExceeded.

        Args:
            business_context: business profile / brand context dict.
            audience_context: audience profile dict.
            competitor_context: competitor profile dict.
            budget: budget string (e.g. "₹50,000").
            goal: the marketing goal string.

        Returns:
            A list of 3 Strategy objects (primary, alternative, contrarian).
        """
        prompt = self._build_strategy_prompt(
            business_context=business_context,
            audience_context=audience_context,
            competitor_context=competitor_context,
            budget=budget,
            goal=goal,
        )
        try:
            comp = self._gateway.complete(
                prompt=prompt,
                tier=Tier.large,
                task="strategy_engine_generate",
                tenant_id=self._tenant_id,
                plan=self._plan,
                max_tokens=2500,
                temperature=0.7,
                user_input=goal,
                prompt_version="strategy_engine_generate_v1.0",
            )
            try:
                raw = extract_json(comp.text) or {}
            except Exception:
                raw = {}
            return _parse_strategies(raw)
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("strategy generation failed (continuing): %s", e)
            return _default_strategies()

    async def explain_choice(
        self,
        strategies: list[Strategy],
        business_context: dict[str, Any],
        audience_context: dict[str, Any],
        budget: str,
        goal: str,
        past_performance: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Explain why the primary strategy was chosen over the alternatives.

        The "Why A not B" layer — the core IP that makes CURV AI hard to copy.
        Considers brand context, audience, budget, and past campaign
        performance (from the P4.6 feedback loop / BusinessMemoryStore).

        Uses AIGateway with Tier.small and extract_json.

        Args:
            strategies: the 3 Strategy objects from generate_strategies().
            business_context: business profile / brand context dict.
            audience_context: audience profile dict.
            budget: budget string.
            goal: the marketing goal string.
            past_performance: optional list of past campaign performance
                learnings from BusinessMemoryStore.performance_learnings.

        Returns:
            A dict with keys: chosen_strategy (str), reasoning (str),
            why_not_alternative (str), why_not_contrarian (str),
            key_factors (list of str).
        """
        prompt = self._build_explanation_prompt(
            strategies=strategies,
            business_context=business_context,
            audience_context=audience_context,
            budget=budget,
            goal=goal,
            past_performance=past_performance,
        )
        try:
            comp = self._gateway.complete(
                prompt=prompt,
                tier=Tier.small,
                task="strategy_engine_explain",
                tenant_id=self._tenant_id,
                plan=self._plan,
                max_tokens=1200,
                temperature=0.3,
                user_input=goal,
                prompt_version="strategy_engine_explain_v1.0",
            )
            try:
                raw = extract_json(comp.text) or {}
            except Exception:
                raw = {}
            return self._normalise_explanation(raw, strategies)
        except BudgetExceeded:
            raise
        except Exception as e:
            logger.warning("strategy explanation failed (continuing): %s", e)
            return self._normalise_explanation({}, strategies)

    # ─── Prompt builders ───────────────────────────────────────────────

    def _build_strategy_prompt(
        self,
        *,
        business_context: dict[str, Any],
        audience_context: dict[str, Any],
        competitor_context: dict[str, Any],
        budget: str,
        goal: str,
    ) -> str:
        return f"""ROLE: You are a Chief Strategy Officer at a top global advertising agency. \
You think in options, not single answers. For every campaign you propose THREE \
genuinely different strategies and recommend one.

TASK: Generate 3 distinct marketing strategies for the following campaign. \
Each strategy must pursue the SAME goal but via a DIFFERENT strategic lever. \
Do NOT produce three variations of the same tactic — they must be fundamentally \
different approaches.

INPUTS:
- Business Context: {business_context}
- Audience Context: {audience_context}
- Competitor Context: {competitor_context}
- Budget: {budget}
- Goal: {goal}

THE THREE STRATEGIES:
1. PRIMARY (strategy_type: "primary") — The recommended approach. The highest-\
probability path to the goal given the budget, audience, and competitive landscape. \
This is what you would bet the client's money on.
2. ALTERNATIVE (strategy_type: "alternative") — A different valid approach to the \
same goal. A different lever (e.g. brand awareness instead of direct response, a \
different audience segment, or a different channel mix). Sound, but not the top pick.
3. CONTRARIAN (strategy_type: "contrarian") — An unconventional approach that most \
competitors would ignore but that could win big. Higher risk, higher reward. \
Think like a maverick — what would a challenger brand do?

For each strategy provide:
- name: A short, memorable name (e.g. "Signature Dish Hero", "Community-First Pivot")
- approach: 2-3 sentences describing the strategic approach
- why_it_works: 1-2 sentences explaining why this is effective for THIS business/audience/budget
- risks: 2-3 specific risks of this approach
- expected_outcome: 1 sentence on the expected result if executed well
- strategy_type: "primary", "alternative", or "contrarian"

QUALITY RULES:
- The 3 strategies must be genuinely different in approach, not 3 flavors of the same idea
- The primary must be the most defensible choice, not just the safest
- The contrarian must be unconventional but plausible — not absurd
- Every strategy must be actionable within the stated budget

OUTPUT: JSON only, no markdown:
{{
  "strategies": [
    {{"name": "...", "approach": "...", "why_it_works": "...", "risks": ["..."], "expected_outcome": "...", "strategy_type": "primary"}},
    {{"name": "...", "approach": "...", "why_it_works": "...", "risks": ["..."], "expected_outcome": "...", "strategy_type": "alternative"}},
    {{"name": "...", "approach": "...", "why_it_works": "...", "risks": ["..."], "expected_outcome": "...", "strategy_type": "contrarian"}}
  ]
}}
"""

    def _build_explanation_prompt(
        self,
        *,
        strategies: list[Strategy],
        business_context: dict[str, Any],
        audience_context: dict[str, Any],
        budget: str,
        goal: str,
        past_performance: list[dict[str, Any]] | None,
    ) -> str:
        strategies_text = "\n".join(
            f"  {i + 1}. [{s.strategy_type.upper()}] {s.name}: {s.approach}"
            for i, s in enumerate(strategies)
        )
        perf_text = ""
        if past_performance:
            perf_text = (
                "\nPAST CAMPAIGN PERFORMANCE (from feedback loop — use this to "
                "inform the choice):\n"
                + json.dumps(past_performance, default=str)[:2000]
            )
        return f"""ROLE: You are a Chief Strategy Officer explaining to the client why you \
chose the primary strategy over the two alternatives.

TASK: Explain WHY the primary strategy is the best choice for this business, \
audience, and budget — and why the alternative and contrarian were NOT chosen. \
Be specific and honest. The client should understand the trade-offs.

INPUTS:
- Business Context: {business_context}
- Audience Context: {audience_context}
- Budget: {budget}
- Goal: {goal}{perf_text}

THE THREE STRATEGIES:
{strategies_text}

OUTPUT: JSON only, no markdown:
{{
  "chosen_strategy": "the name of the primary strategy",
  "reasoning": "2-3 sentences explaining why this is the best choice for THIS business, audience, and budget",
  "why_not_alternative": "1-2 sentences explaining why the alternative was not chosen",
  "why_not_contrarian": "1-2 sentences explaining why the contrarian was not chosen",
  "key_factors": ["factor 1", "factor 2", "factor 3"]
}}

The key_factors should be the 3-5 specific factors that decided the choice \
(e.g. "budget too small for brand-awareness play", "audience responds to direct \
offers", "past campaigns showed short-form video outperforms").
"""

    # ─── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_explanation(
        raw: Any, strategies: list[Strategy],
    ) -> dict[str, Any]:
        """Normalise the parsed explanation JSON, with sensible fallbacks."""
        if not isinstance(raw, dict):
            raw = {}
        # Determine the chosen strategy name (default to the primary's name)
        primary_name = ""
        for s in strategies:
            if s.strategy_type == "primary":
                primary_name = s.name
                break
        chosen = str(raw.get("chosen_strategy", "") or "").strip() or primary_name
        key_factors = raw.get("key_factors") or []
        if not isinstance(key_factors, list):
            key_factors = [str(key_factors)] if key_factors else []
        return {
            "chosen_strategy": chosen,
            "reasoning": str(raw.get("reasoning", "") or "").strip(),
            "why_not_alternative": str(raw.get("why_not_alternative", "") or "").strip(),
            "why_not_contrarian": str(raw.get("why_not_contrarian", "") or "").strip(),
            "key_factors": [str(f) for f in key_factors],
        }
