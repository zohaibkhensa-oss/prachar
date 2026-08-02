"""Campaign Brain REST API.

Endpoints:
    POST /campaign-brain/analyse          — Business + audience + competitor analysis
    POST /campaign-brain/strategy         — Marketing objective + campaign strategy
    POST /campaign-brain/creative-direction — Creative direction
    POST /campaign-brain/media-plan       — Media plan
    POST /campaign-brain/execution-plan   — Execution plan
    POST /campaign-brain/full-campaign    — Complete campaign (all 9 engines)
    GET  /campaign-brain/plans            — List saved campaign plans
    GET  /campaign-brain/plans/{id}       — Get a saved campaign plan
    POST /campaign-brain/{id}/learn       — Generate learning report from performance data
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..models import (
    Actor,
    Brand,
    CampaignPlanRecord,
)
from prachar_shared.marketing_intelligence import (
    CampaignBrain,
)

router = APIRouter(prefix="/campaign-brain", tags=["campaign-brain"])


# ─── Request schemas ────────────────────────────────────────────────────────


class AnalyseRequest(BaseModel):
    """Request for business + audience + competitor analysis."""

    brand_id: uuid.UUID
    goal: str = Field(default="", description="The marketing goal in plain language")
    budget: str = Field(default="", description="Total budget, e.g. '₹5,00,000'")
    locale: str = "en-IN"
    additional_context: str = ""


class StrategyRequest(BaseModel):
    """Request for marketing objective + campaign strategy."""

    brand_id: uuid.UUID
    goal: str
    budget: str = ""
    locale: str = "en-IN"
    # Optional: pre-existing profiles to use instead of re-analyzing
    business_profile: dict[str, Any] | None = None
    audience_profile: dict[str, Any] | None = None
    competitor_profile: dict[str, Any] | None = None
    additional_context: str = ""


class CreativeDirectionRequest(BaseModel):
    """Request for creative direction."""

    brand_id: uuid.UUID
    campaign_strategy: dict[str, Any] | None = None
    business_profile: dict[str, Any] | None = None
    audience_profile: dict[str, Any] | None = None
    additional_context: str = ""


class MediaPlanRequest(BaseModel):
    """Request for media plan."""

    brand_id: uuid.UUID
    goal: str = ""
    budget: str = ""
    locale: str = "en-IN"
    campaign_strategy: dict[str, Any] | None = None
    business_profile: dict[str, Any] | None = None
    audience_profile: dict[str, Any] | None = None
    objective: dict[str, Any] | None = None
    additional_context: str = ""


class ExecutionPlanRequest(BaseModel):
    """Request for execution plan."""

    brand_id: uuid.UUID
    campaign_strategy: dict[str, Any] | None = None
    creative_direction: dict[str, Any] | None = None
    media_plan: dict[str, Any] | None = None
    budget_estimate: dict[str, Any] | None = None
    objective: dict[str, Any] | None = None
    additional_context: str = ""


class FullCampaignRequest(BaseModel):
    """Request for a complete campaign (all 9 engines)."""

    brand_id: uuid.UUID
    goal: str = Field(description="The marketing goal, e.g. 'increase sales by 30%'")
    budget: str = Field(default="", description="Total budget, e.g. '₹5,00,000'")
    locale: str = "en-IN"
    name: str = Field(default="", description="Campaign name (auto-generated if empty)")
    additional_context: str = ""
    save: bool = Field(default=True, description="Whether to persist the campaign plan")


class LearnRequest(BaseModel):
    """Request for the learning engine."""

    campaign_plan_id: uuid.UUID | None = None
    performance_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Performance metrics: CTR, reach, impressions, conversions, cost, ROI",
    )


# ─── Response schemas ───────────────────────────────────────────────────────


class EngineOutputOut(BaseModel):
    result: dict[str, Any]
    confidence: float
    reasoning: str
    recommendations: list[dict[str, Any]]
    model: str
    provider: str
    tokens_used: int
    cost_usd: float
    latency_ms: float
    cached: bool
    prompt_version: str
    request_id: str


class FullCampaignOut(BaseModel):
    business_profile: dict[str, Any]
    audience_profile: dict[str, Any]
    competitor_profile: dict[str, Any]
    marketing_objective: dict[str, Any]
    campaign_strategy: dict[str, Any]
    creative_direction: dict[str, Any]
    media_plan: dict[str, Any]
    budget_estimate: dict[str, Any]
    execution_plan: dict[str, Any]
    engine_outputs: dict[str, dict[str, Any]]
    overall_confidence: float
    total_cost_usd: float
    total_latency_ms: float
    total_tokens: int
    executive_summary: str
    risk_assessment: list[str]
    campaign_plan_id: uuid.UUID | None = None


class CampaignPlanSummaryOut(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    goal: str
    status: str
    overall_confidence: float
    created_at: Any


class CampaignPlanDetailOut(CampaignPlanSummaryOut):
    budget: str | None
    locale: str
    campaign: dict[str, Any]
    total_cost_usd: float
    total_tokens: int


class LearningReportOut(BaseModel):
    report: dict[str, Any]
    confidence: float
    reasoning: str
    recommendations: list[dict[str, Any]]
    model: str
    tokens_used: int
    cost_usd: float


# ─── Helpers ────────────────────────────────────────────────────────────────


async def _get_brand(
    session: SessionDep, brand_id: uuid.UUID, tenant_id: uuid.UUID
) -> Brand:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    return brand


def _engine_output_to_dict(out: Any) -> dict[str, Any]:
    """Convert an EngineOutput object to a dict matching EngineOutputOut schema."""
    return {
        "result": out.result,
        "confidence": out.confidence,
        "reasoning": out.reasoning,
        "recommendations": [r.to_dict() for r in out.recommendations],
        "model": out.model,
        "provider": out.provider,
        "tokens_used": out.tokens_used,
        "cost_usd": out.cost_usd,
        "latency_ms": out.latency_ms,
        "cached": out.cached,
        "prompt_version": out.prompt_version,
        "request_id": out.request_id,
    }


def _engine_output_dict_to_schema(d: dict[str, Any]) -> dict[str, Any]:
    """Convert a serialized engine output dict (from brain public API) to
    the EngineOutputOut schema dict. Handles recommendations being dicts.
    """
    return {
        "result": d.get("result", {}),
        "confidence": d.get("confidence", 0.5),
        "reasoning": d.get("reasoning", ""),
        "recommendations": d.get("recommendations", []),
        "model": d.get("model", ""),
        "provider": d.get("provider", ""),
        "tokens_used": d.get("tokens_used", 0),
        "cost_usd": d.get("cost_usd", 0.0),
        "latency_ms": d.get("latency_ms", 0.0),
        "cached": d.get("cached", False),
        "prompt_version": d.get("prompt_version", ""),
        "request_id": d.get("request_id", ""),
    }


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/analyse", response_model=EngineOutputOut)
async def analyse(
    body: AnalyseRequest,
    user: CurrentUser,
    session: SessionDep,
) -> EngineOutputOut:
    """Run business + audience + competitor analysis.

    This is the "understand before create" phase. Returns structured
    understanding of the business, audience, and competitive landscape.

    Phase 5: Delegates to CampaignBrain.analyse() — no manual engine chaining.
    """
    brand = await _get_brand(session, body.brand_id, user.tenant_id)
    plan = await get_tenant_plan(session, user)
    brain = CampaignBrain()
    result = await brain.analyse(
        tenant_id=user.tenant_id,
        plan=plan,
        business_name=brand.name,
        website=brand.website or "",
        category=brand.category or "",
        goal=body.goal,
        locale=body.locale,
        brand_id=body.brand_id,
        additional_context=body.additional_context,
    )
    # Aggregate the three engine outputs into a single EngineOutputOut
    outputs = result["engine_outputs"]
    biz = outputs["business"]
    aud = outputs["audience"]
    comp = outputs["competitor"]
    combined = {
        **result["business_profile"],
        "audience": result["audience_profile"],
        "competitor": result["competitor_profile"],
    }
    return EngineOutputOut(
        result=combined,
        confidence=(biz["confidence"] + aud["confidence"] + comp["confidence"]) / 3,
        reasoning=f"Business: {biz['reasoning']}\nAudience: {aud['reasoning']}\nCompetitor: {comp['reasoning']}",
        recommendations=biz["recommendations"] + aud["recommendations"] + comp["recommendations"],
        model=biz["model"],
        provider=biz["provider"],
        tokens_used=biz["tokens_used"] + aud["tokens_used"] + comp["tokens_used"],
        cost_usd=biz["cost_usd"] + aud["cost_usd"] + comp["cost_usd"],
        latency_ms=biz["latency_ms"] + aud["latency_ms"] + comp["latency_ms"],
        cached=biz["cached"],
        prompt_version=biz["prompt_version"],
        request_id=biz["request_id"],
    )


@router.post("/strategy", response_model=EngineOutputOut)
async def strategy(
    body: StrategyRequest,
    user: CurrentUser,
    session: SessionDep,
) -> EngineOutputOut:
    """Create marketing objective + campaign strategy.

    Phase 5: Delegates to CampaignBrain.generate_strategy() — no manual chaining.
    If pre-existing profiles are provided in the request, they're passed through;
    otherwise the brain analyzes from scratch.
    """
    brand = await _get_brand(session, body.brand_id, user.tenant_id)
    plan = await get_tenant_plan(session, user)
    brain = CampaignBrain()

    # If profiles are provided, we still need to run objective+strategy.
    # generate_strategy() always runs business+audience internally, so for the
    # case where profiles are pre-supplied, we use the private runners (acceptable
    # — this is the router, not another engine). For the common case (no profiles),
    # we delegate to the public API.
    if body.business_profile is None and body.audience_profile is None:
        result = await brain.generate_strategy(
            tenant_id=user.tenant_id,
            plan=plan,
            goal=body.goal,
            business_name=brand.name,
            website=brand.website or "",
            category=brand.category or "",
            budget=body.budget,
            locale=body.locale,
            brand_id=body.brand_id,
            additional_context=body.additional_context,
        )
        outputs = result["engine_outputs"]
        obj = outputs["objective"]
        strat = outputs["strategy"]
        combined = {
            "objective": result["marketing_objective"],
            "strategy": result["campaign_strategy"],
        }
        return EngineOutputOut(
            result=combined,
            confidence=(obj["confidence"] + strat["confidence"]) / 2,
            reasoning=f"Objective: {obj['reasoning']}\nStrategy: {strat['reasoning']}",
            recommendations=obj["recommendations"] + strat["recommendations"],
            model=strat["model"],
            provider=strat["provider"],
            tokens_used=obj["tokens_used"] + strat["tokens_used"],
            cost_usd=obj["cost_usd"] + strat["cost_usd"],
            latency_ms=obj["latency_ms"] + strat["latency_ms"],
            cached=strat["cached"],
            prompt_version=strat["prompt_version"],
            request_id=strat["request_id"],
        )

    # Pre-supplied profiles path — use objective + strategy engines directly
    # via the brain's private runners (router is allowed to call the brain,
    # just not to chain engines outside of it).
    biz_profile = body.business_profile or {}
    aud_profile = body.audience_profile or {}
    obj_out = brain.derive_objective(
        tenant_id=user.tenant_id,
        plan=plan,
        user_request=body.goal,
        business_profile=biz_profile,
        audience_profile=aud_profile,
        budget=body.budget,
    )
    strat_out = brain.create_strategy(
        tenant_id=user.tenant_id,
        plan=plan,
        business_profile=biz_profile,
        audience_profile=aud_profile,
        competitor_profile=body.competitor_profile or {},
        objective=obj_out.result,
        budget=body.budget,
        locale=body.locale,
    )
    combined = {"objective": obj_out.result, "strategy": strat_out.result}
    return EngineOutputOut(
        result=combined,
        confidence=(obj_out.confidence + strat_out.confidence) / 2,
        reasoning=f"Objective: {obj_out.reasoning}\nStrategy: {strat_out.reasoning}",
        recommendations=obj_out.recommendations + strat_out.recommendations,
        model=strat_out.model,
        provider=strat_out.provider,
        tokens_used=obj_out.tokens_used + strat_out.tokens_used,
        cost_usd=obj_out.cost_usd + strat_out.cost_usd,
        latency_ms=obj_out.latency_ms + strat_out.latency_ms,
        cached=strat_out.cached,
        prompt_version=strat_out.prompt_version,
        request_id=strat_out.request_id,
    )


@router.post("/creative-direction", response_model=EngineOutputOut)
async def creative_direction(
    body: CreativeDirectionRequest,
    user: CurrentUser,
    session: SessionDep,
) -> EngineOutputOut:
    """Create creative direction (visual style, colours, typography, etc.)."""
    brand = await _get_brand(session, body.brand_id, user.tenant_id)
    brain = CampaignBrain()

    # If strategy not provided, generate it
    strategy = body.campaign_strategy
    biz_profile = body.business_profile
    aud_profile = body.audience_profile

    if strategy is None or biz_profile is None or aud_profile is None:
        biz_out = brain.analyse_business(
            tenant_id=user.tenant_id,
            plan="agency",
            business_name=brand.name,
            website=brand.website or "",
            category=brand.category or "",
            brand_graph=brand.brand_graph or {},
        )
        biz_profile = biz_profile or biz_out.result
        aud_out = brain.analyse_audience(
            tenant_id=user.tenant_id,
            plan="agency",
            business_profile=biz_profile,
            business_name=brand.name,
        )
        aud_profile = aud_profile or aud_out.result

    out = brain.create_creative_direction(
        tenant_id=user.tenant_id,
        plan="agency",
        business_profile=biz_profile or {},
        audience_profile=aud_profile or {},
        campaign_strategy=strategy or {},
        additional_context=body.additional_context,
    )
    return EngineOutputOut(**_engine_output_to_dict(out))


@router.post("/media-plan", response_model=EngineOutputOut)
async def media_plan(
    body: MediaPlanRequest,
    user: CurrentUser,
    session: SessionDep,
) -> EngineOutputOut:
    """Create media plan (channel selection, budget split, scheduling).

    Phase 5: Delegates to CampaignBrain.generate_media_plan() when profiles
    are pre-supplied. Otherwise runs a fuller analysis chain.
    """
    brand = await _get_brand(session, body.brand_id, user.tenant_id)
    plan = await get_tenant_plan(session, user)
    brain = CampaignBrain()

    biz_profile = body.business_profile
    aud_profile = body.audience_profile
    objective = body.objective
    strategy = body.campaign_strategy

    # If all required inputs are provided, use the public API directly
    if biz_profile is not None and aud_profile is not None and objective is not None:
        result = await brain.generate_media_plan(
            tenant_id=user.tenant_id,
            plan=plan,
            business_profile=biz_profile,
            audience_profile=aud_profile,
            objective=objective,
            budget=body.budget,
            campaign_strategy=strategy,
            locale=body.locale,
            brand_id=body.brand_id,
            additional_context=body.additional_context,
        )
        out_dict = result["engine_outputs"]["media"]
        return EngineOutputOut(**_engine_output_dict_to_schema(out_dict))

    # Otherwise, analyze first then generate media plan
    if biz_profile is None or aud_profile is None:
        biz_out = brain.analyse_business(
            tenant_id=user.tenant_id,
            plan=plan,
            business_name=brand.name,
            website=brand.website or "",
            category=brand.category or "",
        )
        biz_profile = biz_profile or biz_out.result
        aud_out = brain.analyse_audience(
            tenant_id=user.tenant_id,
            plan=plan,
            business_profile=biz_profile,
            business_name=brand.name,
            goal=body.goal,
        )
        aud_profile = aud_profile or aud_out.result

    if objective is None:
        obj_out = brain.derive_objective(
            tenant_id=user.tenant_id,
            plan=plan,
            user_request=body.goal,
            business_profile=biz_profile,
            audience_profile=aud_profile,
            budget=body.budget,
        )
        objective = obj_out.result

    result = await brain.generate_media_plan(
        tenant_id=user.tenant_id,
        plan=plan,
        business_profile=biz_profile or {},
        audience_profile=aud_profile or {},
        objective=objective or {},
        budget=body.budget,
        campaign_strategy=strategy,
        locale=body.locale,
        brand_id=body.brand_id,
        additional_context=body.additional_context,
    )
    out_dict = result["engine_outputs"]["media"]
    return EngineOutputOut(**_engine_output_dict_to_schema(out_dict))


@router.post("/execution-plan", response_model=EngineOutputOut)
async def execution_plan(
    body: ExecutionPlanRequest,
    user: CurrentUser,
    session: SessionDep,
) -> EngineOutputOut:
    """Create execution plan (task breakdown, timeline, approvals)."""
    await _get_brand(session, body.brand_id, user.tenant_id)
    brain = CampaignBrain()

    out = brain.create_execution_plan(
        tenant_id=user.tenant_id,
        plan="agency",
        campaign_strategy=body.campaign_strategy or {},
        creative_direction=body.creative_direction or {},
        media_plan=body.media_plan or {},
        budget_estimate=body.budget_estimate or {},
        objective=body.objective or {},
        additional_context=body.additional_context,
    )
    return EngineOutputOut(**_engine_output_to_dict(out))


@router.post("/full-campaign", response_model=FullCampaignOut, status_code=status.HTTP_201_CREATED)
async def full_campaign(
    body: FullCampaignRequest,
    user: CurrentUser,
    session: SessionDep,
) -> FullCampaignOut:
    """Run the complete campaign analysis pipeline (all 9 engines).

    This is the main entry point. It chains:
    Business → Audience → Competitor → Objective → Strategy →
    Creative Direction → Media Plan → Budget → Execution Plan.

    Returns a FullCampaign with every analysis + executive summary.
    Optionally persists the campaign plan to the database.
    """
    brand = await _get_brand(session, body.brand_id, user.tenant_id)
    brain = CampaignBrain()

    name = body.name or f"{brand.name} — {body.goal[:50]}"

    campaign = await brain.generate_campaign(
        tenant_id=user.tenant_id,
        plan="agency",
        business_name=brand.name,
        website=brand.website or "",
        category=brand.category or "",
        description="",
        goal=body.goal,
        budget=body.budget,
        locale=body.locale,
        brand_id=brand.id,
        brand_graph=brand.brand_graph or {},
        additional_context=body.additional_context,
    )

    campaign_plan_id: uuid.UUID | None = None
    if body.save:
        record = CampaignPlanRecord(
            tenant_id=user.tenant_id,
            brand_id=brand.id,
            name=name,
            goal=body.goal,
            budget=body.budget,
            locale=body.locale,
            campaign=campaign.to_dict(),
            overall_confidence=campaign.overall_confidence,
            total_cost_usd=campaign.total_cost_usd,
            total_tokens=campaign.total_tokens,
            status="draft",
        )
        session.add(record)
        await session.flush()
        campaign_plan_id = record.id
        await log_audit(
            session,
            tenant_id=user.tenant_id,
            actor=Actor.user,
            action="campaign_brain.full_campaign",
            entity_type="campaign_plan",
            entity_id=record.id,
            payload={"name": name, "goal": body.goal, "confidence": campaign.overall_confidence},
        )
        await session.commit()

    return FullCampaignOut(
        business_profile=campaign.business_profile.to_dict(),
        audience_profile=campaign.audience_profile.to_dict(),
        competitor_profile=campaign.competitor_profile.to_dict(),
        marketing_objective=campaign.marketing_objective.to_dict(),
        campaign_strategy=campaign.campaign_strategy.to_dict(),
        creative_direction=campaign.creative_direction.to_dict(),
        media_plan=campaign.media_plan.to_dict(),
        budget_estimate=campaign.budget_estimate.to_dict(),
        execution_plan=campaign.execution_plan.to_dict(),
        engine_outputs={k: v.to_dict() for k, v in campaign.engine_outputs.items()},
        overall_confidence=campaign.overall_confidence,
        total_cost_usd=campaign.total_cost_usd,
        total_latency_ms=campaign.total_latency_ms,
        total_tokens=campaign.total_tokens,
        executive_summary=campaign.executive_summary,
        risk_assessment=campaign.risk_assessment,
        campaign_plan_id=campaign_plan_id,
    )


@router.get("/plans", response_model=list[CampaignPlanSummaryOut])
async def list_plans(
    user: CurrentUser,
    session: SessionDep,
    brand_id: uuid.UUID | None = None,
) -> list[CampaignPlanSummaryOut]:
    """List saved campaign plans for the tenant."""
    stmt = (
        select(CampaignPlanRecord)
        .where(CampaignPlanRecord.tenant_id == user.tenant_id)
        .order_by(CampaignPlanRecord.created_at.desc())
    )
    if brand_id is not None:
        stmt = stmt.where(CampaignPlanRecord.brand_id == brand_id)
    res = await session.execute(stmt)
    return [
        CampaignPlanSummaryOut(
            id=r.id,
            brand_id=r.brand_id,
            name=r.name,
            goal=r.goal,
            status=r.status,
            overall_confidence=r.overall_confidence,
            created_at=r.created_at,
        )
        for r in res.scalars().all()
    ]


@router.get("/plans/{plan_id}", response_model=CampaignPlanDetailOut)
async def get_plan(
    plan_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignPlanDetailOut:
    """Get a saved campaign plan by ID."""
    res = await session.execute(
        select(CampaignPlanRecord).where(
            CampaignPlanRecord.id == plan_id,
            CampaignPlanRecord.tenant_id == user.tenant_id,
        )
    )
    r = res.scalar_one_or_none()
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign plan not found")
    return CampaignPlanDetailOut(
        id=r.id,
        brand_id=r.brand_id,
        name=r.name,
        goal=r.goal,
        status=r.status,
        overall_confidence=r.overall_confidence,
        created_at=r.created_at,
        budget=r.budget,
        locale=r.locale,
        campaign=r.campaign,
        total_cost_usd=r.total_cost_usd,
        total_tokens=r.total_tokens,
    )


@router.post("/{plan_id}/learn", response_model=LearningReportOut)
async def learn(
    plan_id: uuid.UUID,
    body: LearnRequest,
    user: CurrentUser,
    session: SessionDep,
) -> LearningReportOut:
    """Generate a learning report from campaign performance data.

    Updates the brand's business memory with learnings for future campaigns.
    """
    res = await session.execute(
        select(CampaignPlanRecord).where(
            CampaignPlanRecord.id == plan_id,
            CampaignPlanRecord.tenant_id == user.tenant_id,
        )
    )
    plan = res.scalar_one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign plan not found")

    brain = CampaignBrain()
    report = await brain.learn(
        tenant_id=user.tenant_id,
        brand_id=plan.brand_id,
        campaign_plan=plan.campaign,
        performance_data=body.performance_data,
        plan="agency",
    )

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=Actor.ai,
        action="campaign_brain.learn",
        entity_type="campaign_plan",
        entity_id=plan.id,
        payload={"confidence": report.confidence if hasattr(report, "confidence") else 0.5},
    )
    await session.commit()

    report_dict = report.to_dict() if hasattr(report, "to_dict") else {}
    return LearningReportOut(
        report=report_dict,
        confidence=0.5,
        reasoning="",
        recommendations=[],
        model="",
        tokens_used=0,
        cost_usd=0.0,
    )
