"""Agency Council REST API.

Endpoints:
    POST /agency-council/review            — Submit a campaign for council review
    POST /agency-council/consensus         — Get consensus decision for a session
    GET  /agency-council/history           — List council sessions for a tenant/brand
    GET  /agency-council/{campaign_id}     — Get council session by campaign ID

The council reviews every campaign before it goes live. No single AI agent
makes the final decision — 9 independent directors review, and the Consensus
Engine produces a weighted decision.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..infrastructure import PostgresCouncilRepository
from ..models import Actor, Brand, CampaignPlanRecord
from prachar_shared.agency_council import (
    ConsensusEngine,
    CouncilMemoryStore,
    CouncilLearning,
)
from prachar_shared.ai_gateway import BudgetExceeded

router = APIRouter(prefix="/agency-council", tags=["agency-council"])


# ─── Request schemas ────────────────────────────────────────────────────────


class ReviewRequest(BaseModel):
    """Submit a campaign brief for council review."""

    brand_id: uuid.UUID
    campaign_plan_id: uuid.UUID | None = None
    campaign_brief: dict[str, Any] = Field(
        ..., description="The campaign to review (business, audience, strategy, etc.)"
    )
    industry: str = Field(default="", description="Industry for weight calculation")
    objective: str = Field(default="", description="Campaign objective for weights")
    budget: str = Field(default="", description="Budget string for weights")
    campaign_type: str = Field(default="", description="Campaign type for weights")
    additional_context: str = Field(default="", description="Extra context (e.g., memory)")
    max_rounds: int = Field(default=3, ge=1, le=3, description="Max review rounds")


class ConsensusRequest(BaseModel):
    """Get the consensus decision for a session."""

    session_id: str


class HistoryRequest(BaseModel):
    """List council sessions."""

    brand_id: uuid.UUID | None = None
    limit: int = Field(default=20, ge=1, le=100)


# ─── Response schemas ───────────────────────────────────────────────────────


class DirectorOpinionOut(BaseModel):
    director: str
    role: str
    opinion: str
    reasoning: str
    confidence: float
    risks: list[str]
    alternatives: list[str]
    recommendations: list[str]
    evidence: list[str]
    priority: str
    approval: bool
    round_number: int
    latency_ms: float
    tokens_used: int


class CampaignScoreOut(BaseModel):
    strategy_score: float
    creative_score: float
    media_score: float
    brand_score: float
    performance_score: float
    risk_score: float
    compliance_score: float
    overall_score: float
    weights_used: dict[str, float]


class ConsensusDecisionOut(BaseModel):
    executive_decision: str
    confidence: float
    approval_status: str
    final_recommendation: str
    disagreements: list[str]
    minority_opinions: list[dict[str, Any]]
    risks: list[str]
    weights: dict[str, float]
    weighted_scores: dict[str, float]
    self_critique: list[str]
    rounds_completed: int
    campaign_score: dict[str, Any]
    total_tokens: int
    total_cost_usd: float
    total_latency_ms: float


class CouncilSessionOut(BaseModel):
    session_id: str
    tenant_id: str
    brand_id: str
    campaign_id: str
    status: str
    rounds_completed: int
    consensus_decision: ConsensusDecisionOut | None = None
    total_tokens: int
    total_cost_usd: float
    created_at: str
    completed_at: str


class ReviewResponse(BaseModel):
    session_id: str
    decision: ConsensusDecisionOut
    opinions: list[DirectorOpinionOut]
    campaign_score: CampaignScoreOut


# ─── Helpers ────────────────────────────────────────────────────────────────


async def _get_brand(
    session: AsyncSession, brand_id: uuid.UUID, tenant_id: uuid.UUID
) -> Brand:
    res = await session.execute(
        select(Brand).where(Brand.id == brand_id, Brand.tenant_id == tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")
    return brand


def _opinion_to_out(op: dict[str, Any]) -> DirectorOpinionOut:
    return DirectorOpinionOut(
        director=op.get("director", ""),
        role=op.get("role", ""),
        opinion=op.get("opinion", ""),
        reasoning=op.get("reasoning", ""),
        confidence=op.get("confidence", 0.5),
        risks=op.get("risks", []),
        alternatives=op.get("alternatives", []),
        recommendations=op.get("recommendations", []),
        evidence=op.get("evidence", []),
        priority=op.get("priority", "medium"),
        approval=op.get("approval", False),
        round_number=op.get("round_number", 1),
        latency_ms=op.get("latency_ms", 0.0),
        tokens_used=op.get("tokens_used", 0),
    )


def _decision_to_out(decision: dict[str, Any]) -> ConsensusDecisionOut:
    return ConsensusDecisionOut(
        executive_decision=decision.get("executive_decision", ""),
        confidence=decision.get("confidence", 0.5),
        approval_status=decision.get("approval_status", "pending"),
        final_recommendation=decision.get("final_recommendation", ""),
        disagreements=decision.get("disagreements", []),
        minority_opinions=decision.get("minority_opinions", []),
        risks=decision.get("risks", []),
        weights=decision.get("weights", {}),
        weighted_scores=decision.get("weighted_scores", {}),
        self_critique=decision.get("self_critique", []),
        rounds_completed=decision.get("rounds_completed", 1),
        campaign_score=decision.get("campaign_score", {}),
        total_tokens=decision.get("total_tokens", 0),
        total_cost_usd=decision.get("total_cost_usd", 0.0),
        total_latency_ms=decision.get("total_latency_ms", 0.0),
    )


def _score_to_out(score: dict[str, Any]) -> CampaignScoreOut:
    return CampaignScoreOut(
        strategy_score=score.get("strategy_score", 0.0),
        creative_score=score.get("creative_score", 0.0),
        media_score=score.get("media_score", 0.0),
        brand_score=score.get("brand_score", 0.0),
        performance_score=score.get("performance_score", 0.0),
        risk_score=score.get("risk_score", 0.0),
        compliance_score=score.get("compliance_score", 0.0),
        overall_score=score.get("overall_score", 0.0),
        weights_used=score.get("weights_used", {}),
    )


def _session_to_out(session: dict[str, Any]) -> CouncilSessionOut:
    decision = session.get("consensus_decision", {})
    return CouncilSessionOut(
        session_id=session.get("session_id", ""),
        tenant_id=session.get("tenant_id", ""),
        brand_id=session.get("brand_id", ""),
        campaign_id=session.get("campaign_id", ""),
        status=session.get("status", "pending"),
        rounds_completed=session.get("rounds_completed", 0),
        consensus_decision=_decision_to_out(decision) if decision else None,
        total_tokens=session.get("total_tokens", 0),
        total_cost_usd=session.get("total_cost_usd", 0.0),
        created_at=session.get("created_at", ""),
        completed_at=session.get("completed_at", ""),
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/review", response_model=ReviewResponse)
async def review(
    body: ReviewRequest,
    user: CurrentUser,
    session: SessionDep,
) -> ReviewResponse:
    """Submit a campaign for council review.

    Runs all 9 directors, reaches consensus, and persists the session.
    Returns the decision, all opinions, and the campaign score.
    """
    brand = await _get_brand(session, body.brand_id, user.tenant_id)
    plan = await get_tenant_plan(session, user)

    # Set up the consensus engine with the Postgres repository
    repo = PostgresCouncilRepository(session)
    memory_store = CouncilMemoryStore(repository=repo)
    engine = ConsensusEngine()

    try:
        decision, council_session = await engine.reach_consensus(
            tenant_id=user.tenant_id,
            plan=plan,
            campaign_brief=body.campaign_brief,
            industry=body.industry or brand.category or "",
            objective=body.objective,
            budget=body.budget,
            campaign_type=body.campaign_type,
            brand_id=body.brand_id,
            additional_context=body.additional_context,
            max_rounds=body.max_rounds,
        )
    except BudgetExceeded:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            "AI token budget exceeded for this month",
        )

    # Set the campaign_id on the session before persisting
    if body.campaign_plan_id:
        council_session.campaign_id = str(body.campaign_plan_id)

    # Persist the session
    await memory_store.save_session(council_session)

    # Audit log
    await log_audit(
        session=session,
        tenant_id=user.tenant_id,
        actor=Actor.user,
        actor_id=str(user.user_id),
        action="agency_council.review",
        resource_type="council_session",
        resource_id=council_session.session_id,
        details={
            "brand_id": str(body.brand_id),
            "approval_status": decision.approval_status,
            "overall_score": decision.campaign_score.get("overall_score", 0.0),
            "rounds_completed": decision.rounds_completed,
        },
    )

    # Collect all opinions from the final round
    final_round = str(council_session.rounds_completed)
    all_opinions = council_session.opinions_by_round.get(final_round, [])
    opinions_out = [_opinion_to_out(op) for op in all_opinions]

    return ReviewResponse(
        session_id=council_session.session_id,
        decision=_decision_to_out(decision.to_dict()),
        opinions=opinions_out,
        campaign_score=_score_to_out(decision.campaign_score),
    )


@router.post("/consensus", response_model=ConsensusDecisionOut)
async def get_consensus(
    body: ConsensusRequest,
    user: CurrentUser,
    session: SessionDep,
) -> ConsensusDecisionOut:
    """Get the consensus decision for a council session."""
    repo = PostgresCouncilRepository(session)
    memory_store = CouncilMemoryStore(repository=repo)
    council_session = await memory_store.get_session(body.session_id)
    if council_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "council session not found")
    if council_session.tenant_id != str(user.tenant_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "council session not found")
    decision = council_session.consensus_decision
    if not decision:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no decision found for session")
    return _decision_to_out(decision)


@router.get("/history", response_model=list[CouncilSessionOut])
async def history(
    user: CurrentUser,
    session: SessionDep,
    brand_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[CouncilSessionOut]:
    """List council sessions for the tenant, optionally filtered by brand."""
    repo = PostgresCouncilRepository(session)
    memory_store = CouncilMemoryStore(repository=repo)
    sessions = await memory_store.list_sessions(
        tenant_id=user.tenant_id,
        brand_id=brand_id,
        limit=limit,
    )
    return [_session_to_out(s.to_dict()) for s in sessions]


@router.get("/{campaign_id}", response_model=CouncilSessionOut)
async def get_by_campaign(
    campaign_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> CouncilSessionOut:
    """Get the most recent council session for a campaign."""
    repo = PostgresCouncilRepository(session)
    memory_store = CouncilMemoryStore(repository=repo)
    council_session = await memory_store.get_session_by_campaign(
        tenant_id=user.tenant_id,
        campaign_id=campaign_id,
    )
    if council_session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no council session for this campaign")
    return _session_to_out(council_session.to_dict())
