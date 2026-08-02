"""Unified Consult Router — ONE set of endpoints for ALL domains.

Replaces the duplicated `/consult` (business) and `/creator/*` (creator) routers
with a single domain-agnostic router. The domain is selected by the `domain`
parameter, which loads the appropriate Domain Pack from the registry.

Endpoints:
  POST /consult              — universal consult (any domain)
  POST /consult/campaign     — universal campaign generation (any domain)
  POST /consult/tool/{tool_id} — domain-specific tool (e.g. repurpose, youtube_plan)
  GET  /consult/domains      — list available domains + subtypes (for onboarding UI)

The old /consult and /creator routers remain registered for backward compatibility
but delegate to this unified engine. Future domains (Restaurant, Clinic, etc.)
use ONLY this router — no new routers are created.
"""
from __future__ import annotations

import uuid
from typing import Any
from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from prachar_shared.ai_gateway import BudgetExceeded
from prachar_shared.domain_packs import get_registry, register_all

from ..deps import CurrentUser, SessionDep
from ..infrastructure.consult_engine import ConsultEngine

# Ensure all packs are registered at import time
register_all()

router = APIRouter(prefix="/consult", tags=["consult"])


# ─── Request/Response schemas (domain-agnostic) ───────────────────────────


class ConsultRequest(BaseModel):
    """Universal consult request. Works for any domain."""
    message: str = Field(..., min_length=5, max_length=2000)
    domain: str = Field("business", description="Domain pack id: business, creator, restaurant, clinic")
    subtype_id: str = Field("", description="Optional subtype within the domain")
    brand_id: uuid.UUID | None = None


class CampaignRequest(BaseModel):
    """Universal campaign request. Works for any domain."""
    brand_id: uuid.UUID
    goal: str
    budget: str
    domain: str = Field("business", description="Domain pack id")


class ToolRequest(BaseModel):
    """Universal tool request. The tool is looked up in the domain's pack."""
    domain: str = Field(..., description="Domain pack id")
    inputs: dict[str, Any] = Field(default_factory=dict)


class DomainSummary(BaseModel):
    id: str
    label: str
    emoji: str
    customer_type: str
    subtypes: list[dict[str, Any]]


class DomainsResponse(BaseModel):
    domains: list[DomainSummary]


# ─── Endpoints ─────────────────────────────────────────────────────────────


@router.get("/domains", response_model=DomainsResponse, name="unified_consult_domains")
async def list_domains() -> DomainsResponse:
    """List all available domains and their subtypes.

    Used by the onboarding UI to render the type-selection screen.
    Adding a new domain pack automatically makes it appear here — no UI changes.
    """
    reg = get_registry()
    return DomainsResponse(
        domains=[
            DomainSummary(
                id=p.id,
                label=p.label,
                emoji=p.emoji,
                customer_type=p.customer_type,
                subtypes=[
                    {"id": s.id, "label": s.label, "emoji": s.emoji, "blurb": s.blurb}
                    for s in p.subtypes
                ],
            )
            for p in reg.all()
        ]
    )


@router.post("", name="unified_consult")
async def consult(
    body: ConsultRequest,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    """Universal consult endpoint. Works for ANY domain.

    Takes a free-text description + domain id and returns:
    - A conversational reply from PRACHAR AI
    - Domain-specific understanding (business / creator profile / etc.)
    - Growth opportunities
    - A 30-day plan
    - Extracted entity info
    - Brand id + name

    The pipeline is identical for all domains. Only the Domain Pack changes.
    """
    engine = ConsultEngine()
    try:
        result = await engine.consult(
            message=body.message,
            pack_id=body.domain,
            subtype_id=body.subtype_id,
            user=user,
            session=session,
            brand_id=body.brand_id,
        )
    except BudgetExceeded:
        return {
            "reply": (
                "Hey! I've hit my AI usage limit for this month. "
                "Contact your admin to upgrade your plan, and we'll pick up where we left off."
            ),
        }
    return {
        "reply": result.reply,
        "understanding": result.understanding,
        "opportunities": result.opportunities,
        "plan": result.plan,
        "extracted": result.extracted,
        "brand_id": result.brand_id,
        "brand_name": result.brand_name,
        "confidence": result.confidence,
        "tokens_used": result.tokens_used,
        "model": result.model,
        "domain": result.domain,
    }


@router.post("/campaign", name="unified_consult_campaign")
async def campaign(
    body: CampaignRequest,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, Any]:
    """Universal campaign generation endpoint. Works for ANY domain.

    Uses CampaignBrain.generate_campaign() (always) + the domain pack's
    campaign template + prompt to generate a presentation-deck preview.
    Persists the campaign plan.
    """
    engine = ConsultEngine()
    try:
        result = await engine.campaign(
            pack_id=body.domain,
            brand_id=body.brand_id,
            goal=body.goal,
            budget=body.budget,
            user=user,
            session=session,
        )
    except BudgetExceeded:
        return {
            "reply": "Hey! I've hit my AI usage limit for this month. Contact your admin to upgrade.",
        }
    return {
        "reply": result.reply,
        "preview": result.preview,
        "campaign_plan_id": result.campaign_plan_id,
        "confidence": result.confidence,
        "tokens_used": result.tokens_used,
        "model": result.model,
        "domain": result.domain,
    }


@router.post("/tool/{tool_id}", name="unified_consult_tool")
async def tool(
    tool_id: str,
    body: ToolRequest,
    user: CurrentUser,
) -> dict[str, Any]:
    """Invoke a domain-specific tool (e.g. repurpose, youtube_plan).

    The tool is looked up in the domain's pack. The pack supplies the prompt
    template; the engine handles the LLM call, JSON extraction, and response.

    This replaces the creator-specific /creator/repurpose and /creator/youtube-plan
    endpoints. New domains can add tools by defining ToolSpecs in their pack —
    no new endpoints needed.
    """
    engine = ConsultEngine()
    try:
        result = await engine.tool(
            pack_id=body.domain,
            tool_id=tool_id,
            inputs=body.inputs,
            user=user,
        )
    except BudgetExceeded:
        return {
            "reply": "Hey! I've hit my AI usage limit for this month.",
        }
    return {
        "reply": result.reply,
        "output": result.output,
        "tokens_used": result.tokens_used,
        "model": result.model,
        "tool_id": result.tool_id,
    }


@router.get("/nav/{domain}", name="unified_consult_nav")
async def get_nav(domain: str) -> dict[str, Any]:
    """Get the sidebar navigation for a domain.

    Used by the frontend to render the sidebar. Adding a new domain pack
    automatically makes its nav available here — no frontend hard-coding.
    """
    reg = get_registry()
    pack = reg.get(domain)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown domain: {domain}")
    return {
        "domain": pack.id,
        "label": pack.label,
        "emoji": pack.emoji,
        "nav_sections": [
            {
                "section": s.section,
                "items": [{"label": i.label, "path": i.path, "icon": i.icon} for i in s.items],
            }
            for s in pack.nav_sections
        ],
        "kpi_cards": [
            {"key": k.key, "label": k.label, "icon": k.icon, "hint": k.hint}
            for k in pack.kpi_cards
        ],
        "dashboard_widgets": [
            {"kind": w.kind, "title": w.title, "props": w.props}
            for w in pack.dashboard_widgets
        ],
        "quick_actions": [
            {
                "title": a.title,
                "description": a.description,
                "href": a.href,
                "icon": a.icon,
                "accent": a.accent,
            }
            for a in pack.quick_actions
        ],
        "tools": [
            {
                "id": t.id,
                "label": t.label,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in pack.tools
        ],
    }
