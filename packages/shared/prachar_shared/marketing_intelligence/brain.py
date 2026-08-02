"""Campaign Brain — the orchestrator.

PRACHAR AI never directly answers marketing questions. It first asks the
Campaign Brain. The Campaign Brain runs all intelligence engines in
sequence and returns a structured strategy. PRACHAR AI converts it into
conversational language.

The Campaign Brain is the single entry point for full campaign generation.
It chains: Business → Audience → Competitor → Objective → Strategy →
Creative Direction → Media Plan → Budget → Execution Plan.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from prachar_shared.ai_gateway import AIGateway

from .audience_engine import AudienceIntelligenceEngine, AudienceProfile
from .base import EngineOutput
from .budget_engine import BudgetEstimate, BudgetIntelligenceEngine
from .business_engine import BusinessIntelligenceEngine, BusinessProfile
from .competitor_engine import CompetitorIntelligenceEngine, CompetitorProfile
from .creative_engine import CreativeDirection, CreativeDirectionEngine
from .events import (
    AudienceIdentified,
    BudgetCalculated,
    BusinessAnalysed,
    CampaignCompleted,
    CompetitorsAnalysed,
    CreativeDirectionReady,
    DomainEvent,
    EventBus,
    ExecutionPlanned,
    LearningStored,
    MediaPlanReady,
    ObjectiveDerived,
    StrategyGenerated,
)
from .execution_engine import ExecutionPlan, ExecutionPlanner
from .learning_engine import LearningReport, LearningEngine
from .media_engine import MediaPlan, MediaPlanningEngine
from .memory import BusinessMemory, BusinessMemoryStore
from .objective_engine import MarketingObjective, MarketingObjectiveEngine
from .strategy_engine import CampaignStrategy, CampaignStrategyEngine

logger = logging.getLogger(__name__)


@dataclass
class FullCampaign:
    """The complete output of a full campaign analysis.

    Contains every engine's structured output plus metadata.
    This is the "₹10 crore agency deliverable" — a complete campaign brief.
    """

    # The 9 structured analyses
    business_profile: BusinessProfile = field(default_factory=BusinessProfile)
    audience_profile: AudienceProfile = field(default_factory=AudienceProfile)
    competitor_profile: CompetitorProfile = field(default_factory=CompetitorProfile)
    marketing_objective: MarketingObjective = field(default_factory=MarketingObjective)
    campaign_strategy: CampaignStrategy = field(default_factory=CampaignStrategy)
    creative_direction: CreativeDirection = field(default_factory=CreativeDirection)
    media_plan: MediaPlan = field(default_factory=MediaPlan)
    budget_estimate: BudgetEstimate = field(default_factory=BudgetEstimate)
    execution_plan: ExecutionPlan = field(default_factory=ExecutionPlan)

    # Engine metadata (confidence, cost, latency per engine)
    engine_outputs: dict[str, EngineOutput] = field(default_factory=dict)

    # Overall metadata
    overall_confidence: float = 0.5
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    total_tokens: int = 0

    # Executive summary (generated last)
    executive_summary: str = ""
    risk_assessment: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "business_profile": self.business_profile.to_dict(),
            "audience_profile": self.audience_profile.to_dict(),
            "competitor_profile": self.competitor_profile.to_dict(),
            "marketing_objective": self.marketing_objective.to_dict(),
            "campaign_strategy": self.campaign_strategy.to_dict(),
            "creative_direction": self.creative_direction.to_dict(),
            "media_plan": self.media_plan.to_dict(),
            "budget_estimate": self.budget_estimate.to_dict(),
            "execution_plan": self.execution_plan.to_dict(),
            "engine_outputs": {k: v.to_dict() for k, v in self.engine_outputs.items()},
            "overall_confidence": self.overall_confidence,
            "total_cost_usd": self.total_cost_usd,
            "total_latency_ms": self.total_latency_ms,
            "total_tokens": self.total_tokens,
            "executive_summary": self.executive_summary,
            "risk_assessment": self.risk_assessment,
        }


class CampaignBrain:
    """The orchestrator that runs all intelligence engines.

    Usage:
        brain = CampaignBrain(gateway=gw)
        campaign = await brain.analyse_full(
            tenant_id=user.tenant_id,
            plan="agency",
            business_name="Acme",
            website="acme.com",
            goal="increase sales by 30%",
            budget="₹5,00,000",
        )

    The brain runs engines in dependency order:
    1. Business Intelligence (no deps)
    2. Audience Intelligence (needs business)
    3. Competitor Intelligence (needs business)
    4. Marketing Objective (needs business + audience)
    5. Campaign Strategy (needs business + audience + competitor + objective)
    6. Creative Direction (needs strategy + audience)
    7. Media Plan (needs strategy + audience + objective)
    8. Budget Intelligence (needs strategy + media plan)
    9. Execution Plan (needs strategy + creative + media + budget)
    """

    def __init__(
        self,
        gateway: AIGateway | None = None,
        memory_store: BusinessMemoryStore | None = None,
        event_bus: "EventBus | None" = None,
        council: "ConsensusEngine | None" = None,
        session_factory: "Callable[[], Any] | None" = None,
    ) -> None:
        self._gateway = gateway
        self._memory_store = memory_store or BusinessMemoryStore()
        self._event_bus = event_bus
        self._council = council
        # Optional session factory for querying live CampaignPerformance data.
        # When None, live data context is skipped gracefully.
        self._session_factory = session_factory
        # Lazy-init engines
        self._business_engine: BusinessIntelligenceEngine | None = None
        self._audience_engine: AudienceIntelligenceEngine | None = None
        self._competitor_engine: CompetitorIntelligenceEngine | None = None
        self._objective_engine: MarketingObjectiveEngine | None = None
        self._strategy_engine: CampaignStrategyEngine | None = None
        self._creative_engine: CreativeDirectionEngine | None = None
        self._media_engine: MediaPlanningEngine | None = None
        self._budget_engine: BudgetIntelligenceEngine | None = None
        self._execution_engine: ExecutionPlanner | None = None
        self._learning_engine: LearningEngine | None = None

    @property
    def gateway(self) -> AIGateway:
        if self._gateway is None:
            self._gateway = AIGateway()
        return self._gateway

    @property
    def council(self) -> "ConsensusEngine":
        """Get the Agency Council consensus engine.

        The brain depends on the council INTERFACE (ConsensusEngine), not on
        concrete director implementations. This allows the council to be
        swapped or mocked without modifying the brain.
        """
        if self._council is None:
            from ..agency_council import ConsensusEngine as _CE
            self._council = _CE(gateway=self.gateway)
        return self._council

    def _publish(self, event: DomainEvent) -> None:
        """Publish a domain event if an event bus is configured."""
        if self._event_bus is not None:
            self._event_bus.publish(event)

    # ─── Engine accessors (lazy init) ───────────────────────────────────────

    @property
    def business_engine(self) -> BusinessIntelligenceEngine:
        if self._business_engine is None:
            self._business_engine = BusinessIntelligenceEngine(self.gateway)
        return self._business_engine

    @property
    def audience_engine(self) -> AudienceIntelligenceEngine:
        if self._audience_engine is None:
            self._audience_engine = AudienceIntelligenceEngine(self.gateway)
        return self._audience_engine

    @property
    def competitor_engine(self) -> CompetitorIntelligenceEngine:
        if self._competitor_engine is None:
            self._competitor_engine = CompetitorIntelligenceEngine(self.gateway)
        return self._competitor_engine

    @property
    def objective_engine(self) -> MarketingObjectiveEngine:
        if self._objective_engine is None:
            self._objective_engine = MarketingObjectiveEngine(self.gateway)
        return self._objective_engine

    @property
    def strategy_engine(self) -> CampaignStrategyEngine:
        if self._strategy_engine is None:
            self._strategy_engine = CampaignStrategyEngine(self.gateway)
        return self._strategy_engine

    @property
    def creative_engine(self) -> CreativeDirectionEngine:
        if self._creative_engine is None:
            self._creative_engine = CreativeDirectionEngine(self.gateway)
        return self._creative_engine

    @property
    def media_engine(self) -> MediaPlanningEngine:
        if self._media_engine is None:
            self._media_engine = MediaPlanningEngine(self.gateway)
        return self._media_engine

    @property
    def budget_engine(self) -> BudgetIntelligenceEngine:
        if self._budget_engine is None:
            self._budget_engine = BudgetIntelligenceEngine(self.gateway)
        return self._budget_engine

    @property
    def execution_engine(self) -> ExecutionPlanner:
        if self._execution_engine is None:
            self._execution_engine = ExecutionPlanner(self.gateway)
        return self._execution_engine

    @property
    def learning_engine(self) -> LearningEngine:
        if self._learning_engine is None:
            self._learning_engine = LearningEngine(self.gateway)
        return self._learning_engine

    # ─── Public API (Phase 4: Architecture Stabilisation) ───────────────────
    #
    # These methods form the CANONICAL public API of CampaignBrain.
    # External callers (PRACHAR AI chat, API routers, workers, future services) MUST
    # use these methods — never the private engine runners below.
    #
    # The public API methods are:
    #   analyse()           — business + audience + competitor analysis
    #   consult()           — focused strategy for a specific question (PRACHAR AI)
    #   generate_strategy() — objective + campaign strategy
    #   generate_campaign() — full campaign (all 9 engines)
    #   generate_media_plan() — media plan only
    #   learn()             — post-campaign learning + memory update
    #
    # The private engine runners (analyse_business, analyse_audience, etc.)
    # are kept for backward compatibility but should not be called externally.

    async def analyse(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        business_name: str = "",
        website: str = "",
        category: str = "",
        description: str = "",
        goal: str = "",
        locale: str = "en-IN",
        brand_id: uuid.UUID | None = None,
        additional_context: str = "",
    ) -> dict[str, Any]:
        """Run business + audience + competitor analysis.

        Returns a dict with 'business_profile', 'audience_profile',
        'competitor_profile', and 'engine_outputs'.
        """
        memory = await self._load_memory(tenant_id, brand_id)
        ctx = self._merge_context(additional_context, memory)

        biz_out = self.analyse_business(
            tenant_id=tenant_id, plan=plan,
            business_name=business_name, website=website,
            category=category, description=description,
            brand_graph={}, additional_context=ctx,
        )
        business = self.business_engine.to_profile(biz_out)
        biz_dict = business.to_dict()

        aud_out = self.analyse_audience(
            tenant_id=tenant_id, plan=plan,
            business_profile=biz_dict, business_name=business_name,
            goal=goal, locale=locale, additional_context=ctx,
        )
        audience = self.audience_engine.to_profile(aud_out)
        aud_dict = audience.to_dict()

        comp_out = self.analyse_competitors(
            tenant_id=tenant_id, plan=plan,
            business_profile=biz_dict, business_name=business_name,
            industry=biz_dict.get("industry", category),
            known_competitors=[], additional_context=ctx,
        )
        competitor = self.competitor_engine.to_profile(comp_out)

        return {
            "business_profile": biz_dict,
            "audience_profile": aud_dict,
            "competitor_profile": competitor.to_dict(),
            "engine_outputs": {
                "business": biz_out.to_dict(),
                "audience": aud_out.to_dict(),
                "competitor": comp_out.to_dict(),
            },
        }

    async def consult(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        question: str,
        brand_id: uuid.UUID | None = None,
        business_name: str = "",
        website: str = "",
        locale: str = "en-IN",
    ) -> dict[str, Any]:
        """Answer a strategic question using focused analysis.

        This is the PRACHAR AI entry point. PRACHAR AI never directly answers marketing
        questions — it calls consult() and converts the structured strategy
        into conversational language.

        Runs: business → audience → objective → strategy (4 engines, focused).
        Does NOT run competitor/creative/media/budget/execution (too heavy for chat).

        Returns a dict with 'business_profile', 'audience_profile',
        'marketing_objective', 'campaign_strategy', and 'engine_outputs'.
        """
        memory = await self._load_memory(tenant_id, brand_id)
        ctx = self._merge_context(question, memory)

        biz_out = self.analyse_business(
            tenant_id=tenant_id, plan=plan,
            business_name=business_name, website=website,
            additional_context=ctx,
        )
        business = self.business_engine.to_profile(biz_out)
        biz_dict = business.to_dict()

        aud_out = self.analyse_audience(
            tenant_id=tenant_id, plan=plan,
            business_profile=biz_dict, business_name=business_name,
            goal=question, locale=locale, additional_context=ctx,
        )
        audience = self.audience_engine.to_profile(aud_out)
        aud_dict = audience.to_dict()

        obj_out = self.derive_objective(
            tenant_id=tenant_id, plan=plan,
            user_request=question,
            business_profile=biz_dict, audience_profile=aud_dict,
            additional_context=ctx,
        )
        objective = self.objective_engine.to_objective(obj_out)
        obj_dict = objective.to_dict()

        strat_out = self.create_strategy(
            tenant_id=tenant_id, plan=plan,
            business_profile=biz_dict, audience_profile=aud_dict,
            competitor_profile={}, objective=obj_dict,
            locale=locale, additional_context=ctx,
        )
        strategy = self.strategy_engine.to_strategy(strat_out)

        return {
            "business_profile": biz_dict,
            "audience_profile": aud_dict,
            "marketing_objective": obj_dict,
            "campaign_strategy": strategy.to_dict(),
            "engine_outputs": {
                "business": biz_out.to_dict(),
                "audience": aud_out.to_dict(),
                "objective": obj_out.to_dict(),
                "strategy": strat_out.to_dict(),
            },
        }

    async def generate_strategy(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        goal: str,
        business_name: str = "",
        website: str = "",
        category: str = "",
        budget: str = "",
        locale: str = "en-IN",
        brand_id: uuid.UUID | None = None,
        additional_context: str = "",
    ) -> dict[str, Any]:
        """Generate marketing objective + campaign strategy.

        Runs: business → audience → objective → strategy.
        Returns a dict with 'marketing_objective', 'campaign_strategy',
        'business_profile', 'audience_profile', and 'engine_outputs'.
        """
        memory = await self._load_memory(tenant_id, brand_id)
        ctx = self._merge_context(additional_context, memory)

        biz_out = self.analyse_business(
            tenant_id=tenant_id, plan=plan,
            business_name=business_name, website=website,
            category=category, additional_context=ctx,
        )
        business = self.business_engine.to_profile(biz_out)
        biz_dict = business.to_dict()

        aud_out = self.analyse_audience(
            tenant_id=tenant_id, plan=plan,
            business_profile=biz_dict, business_name=business_name,
            goal=goal, locale=locale, additional_context=ctx,
        )
        audience = self.audience_engine.to_profile(aud_out)
        aud_dict = audience.to_dict()

        obj_out = self.derive_objective(
            tenant_id=tenant_id, plan=plan,
            user_request=goal,
            business_profile=biz_dict, audience_profile=aud_dict,
            budget=budget, additional_context=ctx,
        )
        objective = self.objective_engine.to_objective(obj_out)
        obj_dict = objective.to_dict()

        strat_out = self.create_strategy(
            tenant_id=tenant_id, plan=plan,
            business_profile=biz_dict, audience_profile=aud_dict,
            competitor_profile={}, objective=obj_dict,
            budget=budget, locale=locale, additional_context=ctx,
        )
        strategy = self.strategy_engine.to_strategy(strat_out)

        return {
            "business_profile": biz_dict,
            "audience_profile": aud_dict,
            "marketing_objective": obj_dict,
            "campaign_strategy": strategy.to_dict(),
            "engine_outputs": {
                "business": biz_out.to_dict(),
                "audience": aud_out.to_dict(),
                "objective": obj_out.to_dict(),
                "strategy": strat_out.to_dict(),
            },
        }

    async def generate_campaign(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        business_name: str = "",
        website: str = "",
        category: str = "",
        description: str = "",
        goal: str = "",
        budget: str = "",
        locale: str = "en-IN",
        brand_id: uuid.UUID | None = None,
        brand_graph: dict[str, Any] | None = None,
        additional_context: str = "",
    ) -> FullCampaign:
        """Generate a complete campaign (all 9 engines).

        This is the canonical full-campaign entry point. Delegates to
        analyse_full() which chains all engines in dependency order.
        """
        return await self.analyse_full(
            tenant_id=tenant_id, plan=plan,
            business_name=business_name, website=website,
            category=category, description=description,
            goal=goal, budget=budget, locale=locale,
            brand_id=brand_id, brand_graph=brand_graph,
            additional_context=additional_context,
        )

    async def generate_media_plan(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        business_profile: dict[str, Any],
        audience_profile: dict[str, Any],
        objective: dict[str, Any],
        budget: str = "",
        campaign_strategy: dict[str, Any] | None = None,
        locale: str = "en-IN",
        brand_id: uuid.UUID | None = None,
        additional_context: str = "",
    ) -> dict[str, Any]:
        """Generate a media plan from existing profiles.

        Runs only the Media Planning Engine. Useful when profiles already
        exist (e.g., from a previous analyse() call).
        """
        memory = await self._load_memory(tenant_id, brand_id)
        ctx = self._merge_context(additional_context, memory)

        out = self.create_media_plan(
            tenant_id=tenant_id, plan=plan,
            business_profile=business_profile,
            audience_profile=audience_profile,
            objective=objective,
            budget=budget,
            campaign_strategy=campaign_strategy or {},
            locale=locale,
            additional_context=ctx,
        )
        media_plan = self.media_engine.to_plan(out)
        return {
            "media_plan": media_plan.to_dict(),
            "engine_outputs": {"media": out.to_dict()},
        }

    async def learn(
        self,
        *,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        campaign_plan: dict[str, Any],
        performance_data: dict[str, Any],
        plan: str = "agency",
    ) -> LearningReport:
        """Run the learning engine and update business memory.

        This is the canonical learning entry point. Delegates to
        learn_from_campaign(). Called after a campaign completes.
        """
        return await self.learn_from_campaign(
            tenant_id=tenant_id, brand_id=brand_id,
            campaign_plan=campaign_plan,
            performance_data=performance_data,
            plan=plan,
        )

    # ─── Private helpers ────────────────────────────────────────────────────

    async def _load_memory(self, tenant_id: uuid.UUID, brand_id: uuid.UUID | None) -> BusinessMemory:
        """Load business memory for a brand, returning empty memory on failure."""
        if brand_id is None:
            return BusinessMemory()
        try:
            return await self._memory_store.get(tenant_id, brand_id)
        except Exception as exc:
            logger.warning("failed to load business memory: %s", exc)
            return BusinessMemory()

    def _merge_context(self, additional_context: str, memory: BusinessMemory) -> str:
        """Merge additional context with business memory context."""
        memory_ctx = self._memory_store.to_prompt_context(memory)
        if additional_context and memory_ctx:
            return f"{additional_context}\n\nBUSINESS MEMORY:\n{memory_ctx}"
        if memory_ctx:
            return f"BUSINESS MEMORY:\n{memory_ctx}"
        return additional_context

    async def _load_performance_context(
        self, tenant_id: uuid.UUID, brand_id: uuid.UUID | None
    ) -> str:
        """Load past performance learnings for a brand and format as context.

        Queries the last 3 stored performance learnings for the brand and
        returns a concise prompt-context string. Returns "" when there is
        no past data (graceful — generation proceeds normally).
        """
        if brand_id is None:
            return ""
        try:
            learnings = await self._memory_store.get_performance_learnings(
                tenant_id, brand_id, limit=3
            )
            return self._memory_store.to_performance_context(learnings)
        except Exception as exc:
            logger.warning("failed to load performance context: %s", exc)
            return ""

    async def _load_live_performance_context(
        self, brand_id: uuid.UUID | None
    ) -> str:
        """Load RAW live performance data for a brand's recent campaigns.

        Queries the ``CampaignPerformance`` table for the last 30 days across
        all channels and formats a concise summary for the campaign generation
        prompt. This is SEPARATE from the P4.6 feedback loop (which uses
        summarized learnings from BusinessMemory). This is raw live data.

        Returns "" when there is no session factory, no brand_id, or no live
        data (graceful — generation proceeds normally).
        """
        if brand_id is None or self._session_factory is None:
            return ""
        try:
            return await _format_live_performance_summary(
                self._session_factory, str(brand_id), days=30
            )
        except Exception as exc:
            logger.warning("failed to load live performance context: %s", exc)
            return ""

    # ─── Individual engine runners (private — use public API above) ─────────

    def analyse_business(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.business_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def analyse_audience(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.audience_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def analyse_competitors(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.competitor_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def derive_objective(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.objective_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def create_strategy(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.strategy_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def create_creative_direction(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.creative_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def create_media_plan(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.media_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def estimate_budget(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.budget_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def create_execution_plan(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.execution_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    def generate_learning_report(self, *, tenant_id: uuid.UUID, plan: str = "agency", **kw: Any) -> EngineOutput:
        return self.learning_engine.run(tenant_id=tenant_id, plan=plan, **kw)

    # ─── Full campaign orchestration ────────────────────────────────────────

    async def analyse_full(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        business_name: str = "",
        website: str = "",
        category: str = "",
        description: str = "",
        goal: str = "",
        budget: str = "",
        locale: str = "en-IN",
        brand_id: uuid.UUID | None = None,
        brand_graph: dict[str, Any] | None = None,
        additional_context: str = "",
    ) -> FullCampaign:
        """Run the complete campaign analysis pipeline.

        This is the main entry point. It chains all 9 engines in
        dependency order and returns a FullCampaign with every analysis.

        Args:
            tenant_id: Workspace ID for budget tracking.
            plan: Tenant's plan for budget allocation.
            business_name: The brand/business name.
            website: Business website URL.
            category: Business category.
            description: What the business does.
            goal: The user's marketing goal (e.g., "increase sales by 30%").
            budget: Total campaign budget (e.g., "₹5,00,000").
            locale: Target locale (e.g., "en-IN").
            brand_id: Optional brand ID for memory lookup.
            brand_graph: Optional brand graph data.
            additional_context: Any extra context.

        Returns:
            FullCampaign with all 9 analyses + executive summary.
        """
        campaign = FullCampaign()

        # Load business memory and merge with additional context
        memory = await self._load_memory(tenant_id, brand_id)
        full_context = self._merge_context(additional_context, memory)

        # ─── P4.6: Performance feedback loop ─────────────────────────────
        # Load past performance learnings for this brand and inject them
        # into the generation context so future campaigns learn from past
        # results. Graceful — empty when no past data.
        perf_context = await self._load_performance_context(tenant_id, brand_id)
        if perf_context:
            full_context = (
                f"{full_context}\n\nPAST CAMPAIGN PERFORMANCE:\n{perf_context}"
                if full_context
                else f"PAST CAMPAIGN PERFORMANCE:\n{perf_context}"
            )

        # ─── C.2.1: Live performance data context ───────────────────────
        # Load RAW live performance data from CampaignPerformance for the
        # brand's recent campaigns (last 30 days, all channels). This is
        # SEPARATE from the P4.6 feedback loop above (which uses summarized
        # learnings). This gives PRACHAR AI real-time data to reason from.
        # Graceful — empty when no live data or no session factory.
        live_context = await self._load_live_performance_context(brand_id)
        if live_context:
            full_context = (
                f"{full_context}\n\nLIVE PERFORMANCE DATA:\n{live_context}"
                if full_context
                else f"LIVE PERFORMANCE DATA:\n{live_context}"
            )

        # ─── Step 1: Business Intelligence ──────────────────────────────
        out = self.analyse_business(
            tenant_id=tenant_id,
            plan=plan,
            business_name=business_name,
            website=website,
            category=category,
            description=description,
            brand_graph=brand_graph or {},
            additional_context=full_context,
        )
        campaign.engine_outputs["business"] = out
        campaign.business_profile = self.business_engine.to_profile(out)
        business_dict = campaign.business_profile.to_dict()
        self._publish(BusinessAnalysed(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            industry=business_dict.get("industry", ""),
            confidence=out.confidence,
        ))

        # ─── Step 2: Audience Intelligence ──────────────────────────────
        out = self.analyse_audience(
            tenant_id=tenant_id,
            plan=plan,
            business_profile=business_dict,
            business_name=business_name,
            goal=goal,
            locale=locale,
            additional_context=full_context,
        )
        campaign.engine_outputs["audience"] = out
        campaign.audience_profile = self.audience_engine.to_profile(out)
        audience_dict = campaign.audience_profile.to_dict()
        self._publish(AudienceIdentified(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            buying_intent=audience_dict.get("buying_intent", ""),
            confidence=out.confidence,
        ))

        # ─── Step 3: Competitor Intelligence ────────────────────────────
        out = self.analyse_competitors(
            tenant_id=tenant_id,
            plan=plan,
            business_profile=business_dict,
            business_name=business_name,
            industry=business_dict.get("industry", category),
            known_competitors=[],
            additional_context=full_context,
        )
        campaign.engine_outputs["competitor"] = out
        campaign.competitor_profile = self.competitor_engine.to_profile(out)
        competitor_dict = campaign.competitor_profile.to_dict()
        self._publish(CompetitorsAnalysed(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            competitor_count=len(competitor_dict.get("competitors", [])),
            confidence=out.confidence,
        ))

        # ─── Step 4: Marketing Objective ────────────────────────────────
        out = self.derive_objective(
            tenant_id=tenant_id,
            plan=plan,
            user_request=goal,
            business_profile=business_dict,
            audience_profile=audience_dict,
            budget=budget,
            additional_context=full_context,
        )
        campaign.engine_outputs["objective"] = out
        campaign.marketing_objective = self.objective_engine.to_objective(out)
        objective_dict = campaign.marketing_objective.to_dict()
        self._publish(ObjectiveDerived(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            objective_type=objective_dict.get("objective_type", ""),
            confidence=out.confidence,
        ))

        # ─── Step 5: Campaign Strategy ──────────────────────────────────
        out = self.create_strategy(
            tenant_id=tenant_id,
            plan=plan,
            business_profile=business_dict,
            audience_profile=audience_dict,
            competitor_profile=competitor_dict,
            objective=objective_dict,
            budget=budget,
            locale=locale,
            additional_context=full_context,
        )
        campaign.engine_outputs["strategy"] = out
        campaign.campaign_strategy = self.strategy_engine.to_strategy(out)
        strategy_dict = campaign.campaign_strategy.to_dict()
        self._publish(StrategyGenerated(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            core_message=strategy_dict.get("core_message", ""),
            confidence=out.confidence,
        ))

        # ─── Step 6: Creative Direction ─────────────────────────────────
        brand_colors = memory.colours if memory.colours else []
        brand_fonts = memory.fonts if memory.fonts else []
        out = self.create_creative_direction(
            tenant_id=tenant_id,
            plan=plan,
            business_profile=business_dict,
            audience_profile=audience_dict,
            campaign_strategy=strategy_dict,
            brand_colors=brand_colors,
            brand_logo_url=memory.logo_url,
            brand_fonts=brand_fonts,
            additional_context=full_context,
        )
        campaign.engine_outputs["creative"] = out
        campaign.creative_direction = self.creative_engine.to_direction(out)
        creative_dict = campaign.creative_direction.to_dict()
        self._publish(CreativeDirectionReady(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            visual_style=creative_dict.get("visual_style", ""),
            confidence=out.confidence,
        ))

        # ─── Step 7: Media Plan ─────────────────────────────────────────
        out = self.create_media_plan(
            tenant_id=tenant_id,
            plan=plan,
            business_profile=business_dict,
            audience_profile=audience_dict,
            objective=objective_dict,
            budget=budget,
            campaign_strategy=strategy_dict,
            locale=locale,
            additional_context=full_context,
        )
        campaign.engine_outputs["media"] = out
        campaign.media_plan = self.media_engine.to_plan(out)
        media_dict = campaign.media_plan.to_dict()
        self._publish(MediaPlanReady(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            channel_count=len(media_dict.get("recommended_channels", [])),
            confidence=out.confidence,
        ))

        # ─── Step 8: Budget Intelligence ────────────────────────────────
        out = self.estimate_budget(
            tenant_id=tenant_id,
            plan=plan,
            business_profile=business_dict,
            audience_profile=audience_dict,
            objective=objective_dict,
            campaign_strategy=strategy_dict,
            media_plan=media_dict,
            budget=budget,
            currency="INR",
            additional_context=full_context,
        )
        campaign.engine_outputs["budget"] = out
        campaign.budget_estimate = self.budget_engine.to_estimate(out)
        budget_dict = campaign.budget_estimate.to_dict()
        self._publish(BudgetCalculated(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            total_cost=budget_dict.get("total_cost", {}).get("amount", ""),
            confidence=out.confidence,
        ))

        # ─── Step 9: Execution Plan ─────────────────────────────────────
        out = self.create_execution_plan(
            tenant_id=tenant_id,
            plan=plan,
            campaign_strategy=strategy_dict,
            creative_direction=creative_dict,
            media_plan=media_dict,
            budget_estimate=budget_dict,
            objective=objective_dict,
            additional_context=full_context,
        )
        campaign.engine_outputs["execution"] = out
        campaign.execution_plan = self.execution_engine.to_plan(out)
        self._publish(ExecutionPlanned(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            phase_count=len(campaign.execution_plan.phases),
            confidence=out.confidence,
        ))

        # ─── Aggregate metadata ─────────────────────────────────────────
        confidences: list[float] = []
        for out in campaign.engine_outputs.values():
            if out.confidence > 0:
                confidences.append(out.confidence)
            campaign.total_cost_usd += out.cost_usd
            campaign.total_latency_ms += out.latency_ms
            campaign.total_tokens += out.tokens_used
        campaign.overall_confidence = (
            sum(confidences) / len(confidences) if confidences else 0.5
        )

        # ─── Generate executive summary & risk assessment ───────────────
        campaign.executive_summary = self._build_executive_summary(campaign)
        campaign.risk_assessment = self._build_risk_assessment(campaign)

        # ─── Publish CampaignCompleted event ────────────────────────────
        self._publish(CampaignCompleted(
            tenant_id=str(tenant_id), brand_id=str(brand_id or ""),
            overall_confidence=campaign.overall_confidence,
            total_cost_usd=campaign.total_cost_usd,
            total_tokens=campaign.total_tokens,
        ))

        return campaign

    def _build_executive_summary(self, campaign: FullCampaign) -> str:
        """Build a concise executive summary from the campaign analyses."""
        biz = campaign.business_profile
        obj = campaign.marketing_objective
        strat = campaign.campaign_strategy
        budget = campaign.budget_estimate
        parts: list[str] = []
        if biz.industry:
            parts.append(f"Industry: {biz.industry}")
        if biz.usp:
            parts.append(f"USP: {biz.usp}")
        if obj.objective_type:
            parts.append(f"Objective: {obj.objective_type}")
        if strat.core_message:
            parts.append(f"Core Message: {strat.core_message}")
        if strat.emotional_angle:
            parts.append(f"Emotional Angle: {strat.emotional_angle}")
        total = budget.total_cost.get("amount", "")
        if total:
            parts.append(f"Total Cost: {total}")
        roi = budget.roi_projection.get("expected_roas", "")
        if roi:
            parts.append(f"Expected ROAS: {roi}")
        parts.append(f"Overall Confidence: {campaign.overall_confidence:.1%}")
        return " | ".join(parts) if parts else "Campaign analysis complete."

    def _build_risk_assessment(self, campaign: FullCampaign) -> list[str]:
        """Aggregate risks from all engine recommendations."""
        risks: list[str] = []
        for engine_name, out in campaign.engine_outputs.items():
            for rec in out.recommendations:
                for risk in rec.risks:
                    risks.append(f"[{engine_name}] {risk}")
        # Also pull from execution plan risk mitigation
        for rm in campaign.execution_plan.risk_mitigation:
            if isinstance(rm, dict):
                risk = rm.get("risk", "")
                if risk:
                    risks.append(f"[execution] {risk}")
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for r in risks:
            if r not in seen:
                seen.add(r)
                unique.append(r)
        return unique[:20]  # Cap at 20

    # ─── Learning loop ──────────────────────────────────────────────────────

    async def learn_from_campaign(
        self,
        *,
        tenant_id: uuid.UUID,
        brand_id: uuid.UUID,
        campaign_plan: dict[str, Any],
        performance_data: dict[str, Any],
        plan: str = "agency",
    ) -> LearningReport:
        """Run the learning engine and update business memory.

        Called after a campaign completes to extract learnings and
        update the workspace's business memory for future campaigns.
        """
        # Load current memory
        memory = await self._memory_store.get(tenant_id, brand_id)

        # Run learning engine
        out = self.generate_learning_report(
            tenant_id=tenant_id,
            plan=plan,
            campaign_plan=campaign_plan,
            performance_data=performance_data,
            business_memory=memory.to_dict(),
            historical_campaigns=memory.campaign_history,
        )
        report = self.learning_engine.to_report(out)

        # Update memory with learnings
        self._memory_store.update_from_learning(memory, report)
        await self._memory_store.save(tenant_id, brand_id, memory)

        # ─── P4.6: store a concise performance learning for the feedback loop
        # so future generate_campaign() calls can learn from this campaign.
        try:
            campaign_id = str(campaign_plan.get("id") or campaign_plan.get("campaign_id") or "")
            perf = performance_data or {}
            report_perf = report.performance_summary or {}
            learning = {
                "campaign_id": campaign_id,
                "summary": report_perf.get("headline_finding", "") or perf.get("summary", ""),
                "top_performing_hook": (
                    perf.get("top_performing_hook")
                    or (report.what_worked[0] if report.what_worked else "")
                ),
                "roas": perf.get("roas") or report_perf.get("roas"),
                "ctr": perf.get("ctr") or report_perf.get("ctr"),
                "key_insight": (
                    report.key_learnings[0] if report.key_learnings else ""
                ),
            }
            if campaign_id:
                await self._memory_store.store_performance_learning(
                    tenant_id, brand_id, campaign_id, learning
                )
        except Exception as exc:
            logger.warning("failed to store performance learning: %s", exc)

        # Publish LearningStored event
        self._publish(LearningStored(
            tenant_id=str(tenant_id), brand_id=str(brand_id),
            overall_grade=report.performance_summary.get("overall_grade", ""),
            best_practices_count=len(report.updated_best_practices),
        ))

        return report

    # ─── Agency Council integration ──────────────────────────────────────────

    async def review_with_council(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        campaign: FullCampaign | dict[str, Any] | None = None,
        brand_id: uuid.UUID | None = None,
        industry: str = "",
        objective: str = "",
        budget: str = "",
        campaign_type: str = "",
        additional_context: str = "",
        max_rounds: int = 3,
    ) -> tuple[Any, Any]:
        """Submit a campaign to the Agency Council for review.

        The brain depends only on the Council interface (ConsensusEngine),
        not on concrete director implementations. This is the core IP of
        PRACHAR — no single AI agent makes the final decision.

        Args:
            campaign: A FullCampaign object or dict to review. If None,
                the brain will run generate_campaign() first.
            brand_id: For memory lookup and persistence.
            industry/objective/budget/campaign_type: For weight calculation.
            additional_context: Extra context (e.g., business memory).
            max_rounds: Max review rounds (1-3).

        Returns:
            (ConsensusDecision, CouncilSession) — the council's decision
            and the full session record.
        """
        # If no campaign provided, generate one first
        if campaign is None:
            full_campaign = await self.generate_campaign(
                tenant_id=tenant_id,
                plan=plan,
                business_name="",
                brand_id=brand_id,
            )
            campaign = full_campaign

        # Convert FullCampaign to brief dict
        if hasattr(campaign, "to_dict"):
            brief = campaign.to_dict()
        elif isinstance(campaign, dict):
            brief = campaign
        else:
            brief = {}

        # Load business memory for the Analytics Director
        memory_context = additional_context
        if brand_id is not None and not additional_context:
            memory = await self._load_memory(tenant_id, brand_id)
            mem_ctx = self._memory_store.to_prompt_context(memory)
            if mem_ctx:
                memory_context = mem_ctx

        # Delegate to the council
        decision, session = await self.council.reach_consensus(
            tenant_id=tenant_id,
            plan=plan,
            campaign_brief=brief,
            industry=industry,
            objective=objective,
            budget=budget,
            campaign_type=campaign_type,
            brand_id=brand_id,
            additional_context=memory_context,
            max_rounds=max_rounds,
        )

        return decision, session


# ─── Live performance summary helper (C.2.1) ──────────────────────────────────

# Friendly platform names for the live data summary.
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


def _platform_name(channel: str) -> str:
    """Return a friendly platform name for a raw channel string."""
    return _PLATFORM_NAMES.get(channel, channel.replace("_", " ").title())


async def _format_live_performance_summary(
    session_factory: Callable[[], Any],
    brand_id: str,
    days: int = 30,
) -> str:
    """Query live CampaignPerformance data for a brand and format a concise summary.

    Loads all campaigns for the brand, then queries CampaignPerformance for
    the last ``days`` days across all channels. Aggregates per-channel and
    produces a concise summary like::

        Instagram: 12K reach, 3% engagement. WhatsApp: 12% conversion.
        Google Ads: ₹5K spend, 2x ROAS.

    Returns "" when there is no data (graceful).
    """
    from datetime import date, timedelta

    from sqlalchemy import select

    session = session_factory()
    cutoff = date.today() - timedelta(days=days)

    # Load campaigns for the brand to get campaign IDs.
    try:
        from prachar_api.models.tables import Campaign, CampaignPerformance
    except ImportError:
        return ""

    camp_stmt = select(Campaign.id).where(Campaign.brand_id == brand_id)
    camp_result = await session.execute(camp_stmt)
    campaign_ids = [row[0] for row in camp_result.all()]
    if not campaign_ids:
        return ""

    perf_stmt = (
        select(CampaignPerformance)
        .where(
            CampaignPerformance.campaign_id.in_(campaign_ids),
            CampaignPerformance.date >= cutoff,
        )
        .order_by(CampaignPerformance.date.asc())
    )
    perf_result = await session.execute(perf_stmt)
    rows = list(perf_result.scalars().all())
    if not rows:
        return ""

    # Aggregate per channel.
    per_channel: dict[str, dict[str, float]] = {}
    for r in rows:
        ch = getattr(r, "channel", None) or "unknown"
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
        bucket["impressions"] += int(getattr(r, "impressions", 0) or 0)
        bucket["clicks"] += int(getattr(r, "clicks", 0) or 0)
        bucket["conversions"] += int(getattr(r, "conversions", 0) or 0)
        bucket["spend"] += float(getattr(r, "spend", 0) or 0)
        bucket["revenue"] += float(getattr(r, "revenue", 0) or 0)

    # Build concise per-channel summary lines.
    parts: list[str] = []
    for ch, b in per_channel.items():
        name = _platform_name(ch)
        segments: list[str] = []

        if b["impressions"] > 0:
            reach = b["impressions"]
            reach_str = f"{reach / 1000:.0f}K" if reach >= 1000 else str(reach)
            segments.append(f"{reach_str} reach")
            eng = b["clicks"] / b["impressions"] * 100 if b["impressions"] else 0
            if eng > 0:
                segments.append(f"{eng:.0f}% engagement")

        if b["conversions"] > 0 and b["clicks"] > 0:
            conv_rate = b["conversions"] / b["clicks"] * 100
            segments.append(f"{conv_rate:.0f}% conversion")

        if b["spend"] > 0:
            spend_str = f"₹{b['spend'] / 1000:.0f}K" if b["spend"] >= 1000 else f"₹{b['spend']:.0f}"
            segments.append(f"{spend_str} spend")
            roas = b["revenue"] / b["spend"] if b["spend"] else 0
            if roas > 0:
                segments.append(f"{roas:.1f}x ROAS")

        if segments:
            parts.append(f"{name}: {', '.join(segments)}.")

    if not parts:
        return ""

    return " ".join(parts)
