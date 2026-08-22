"""Conversational onboarding router — "Tell me about your business."

This is the orchestration layer that turns a free-text business description into:
1. A Brand record (auto-created from extracted info)
2. Business understanding (strengths, weaknesses, customers, competitors, opportunities)
3. Top 5 growth opportunities (with impact, difficulty, timeframe)
4. A 30-day marketing plan (week-by-week, business language)

It uses the existing Marketing Intelligence Engine (CampaignBrain.analyse()) —
no new engines, no new architecture. Just a new presentation layer that chains
the existing engines into a single conversational response.

The flow:
    User: "We run a biryani restaurant in Hyderabad."
    ↓
    LLM extracts: {industry, name, location, products, services, audience, goals, website}
    ↓
    Brand created in DB (auto, no form)
    ↓
    CampaignBrain.analyse() runs (business + audience + competitor engines)
    ↓
    LLM converts structured analysis into:
      - Business Summary cards (strengths, weaknesses, customers, competitors)
      - Top 5 Growth Opportunities (with impact/difficulty/timeframe)
      - 30-Day Marketing Plan (week-by-week)
    ↓
    Returns everything in one response. User feels understood in <60 seconds.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep, get_tenant_plan
from ..models import Actor, Brand
from prachar_shared.ai_gateway import AIGateway, Tier, BudgetExceeded

router = APIRouter(prefix="/consult", tags=["consult"])


# ─── Request / Response schemas ─────────────────────────────────────────────


class ConsultRequest(BaseModel):
    """The user's free-text business description.

    Example: "We run a biryani restaurant in Hyderabad, 3 years old,
    mostly walk-ins, want to grow catering orders."
    """

    message: str = Field(..., min_length=5, max_length=2000,
                         description="The user's description of their business")
    brand_id: uuid.UUID | None = Field(None,
                         description="Existing brand ID if user already has one")


class BusinessExtraction(BaseModel):
    """Structured info extracted from free text by the LLM."""

    business_name: str = Field("", description="Extracted business name, if any")
    industry: str = Field("", description="Industry category, e.g. 'restaurant', 'clinic'")
    location: str = Field("", description="City/area, if mentioned")
    products: list[str] = Field(default_factory=list, description="Products mentioned")
    services: list[str] = Field(default_factory=list, description="Services mentioned")
    audience: str = Field("", description="Target audience, if inferrable")
    goals: list[str] = Field(default_factory=list, description="Stated or inferred goals")
    website: str = Field("", description="Website, if mentioned")
    social_handles: list[str] = Field(default_factory=list, description="Social handles, if mentioned")
    additional_context: str = Field("", description="Any other useful context (years in business, seasonality, etc.)")


class GrowthOpportunity(BaseModel):
    """A single growth opportunity with business impact."""

    title: str
    description: str
    business_impact: str  # "High", "Medium", "Low"
    difficulty: str       # "Easy", "Medium", "Hard"
    timeframe: str        # "1-2 weeks", "1 month", "3 months"


class WeekPlan(BaseModel):
    """One week of the 30-day marketing plan."""

    week: int
    theme: str
    objectives: list[str]
    content: list[str]
    offers: list[str]
    channels: list[str]
    kpis: list[str]


class BusinessUnderstanding(BaseModel):
    """The 'I understand your business' response."""

    summary: str = Field("", description="2-3 sentence business summary in plain language")
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    likely_customers: list[str] = Field(default_factory=list)
    likely_competitors: list[str] = Field(default_factory=list)
    marketing_opportunities: list[str] = Field(default_factory=list)
    seasonal_opportunities: list[str] = Field(default_factory=list)
    marketing_maturity: str = Field("", description="e.g. 'Beginner', 'Intermediate', 'Advanced'")
    potential_risks: list[str] = Field(default_factory=list)


class ConsultResponse(BaseModel):
    """The full conversational onboarding response."""

    # The conversational reply from CURV AI
    reply: str = Field(..., description="CURV AI's conversational response")

    # Structured business understanding (for cards)
    business: BusinessUnderstanding = Field(default_factory=BusinessUnderstanding)

    # Top 5 growth opportunities (for cards)
    growth_opportunities: list[GrowthOpportunity] = Field(default_factory=list)

    # 30-day marketing plan (for timeline)
    plan: list[WeekPlan] = Field(default_factory=list)

    # The extracted business info (so frontend can show what was inferred)
    extracted: BusinessExtraction = Field(default_factory=BusinessExtraction)

    # The created/used brand ID (so frontend can use it for campaign generation)
    brand_id: str = ""
    brand_name: str = ""

    # Metadata
    confidence: float = 0.0
    tokens_used: int = 0
    model: str = "stub"


class CampaignPreviewRequest(BaseModel):
    """Request to generate a campaign preview from the consultation."""

    brand_id: uuid.UUID
    goal: str = Field("", description="The marketing goal, e.g. 'grow catering orders'")
    budget: str = Field("₹15,000/month", description="Budget in plain language")


class CampaignPreview(BaseModel):
    """A preview of the recommended campaign — feels like a presentation deck."""

    title: str
    hero_image_concept: str
    video_concept: str
    post_ideas: list[str]
    estimated_reach: str
    expected_enquiries: str
    budget_estimate: str
    why_this_campaign: str
    confidence: float
    expected_benefit: str
    risks: list[str]
    alternative: str


class CampaignPreviewResponse(BaseModel):
    reply: str
    preview: CampaignPreview
    campaign_plan_id: str = ""
    tokens_used: int = 0
    model: str = "stub"


# ─── LLM prompts ────────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """\
You are a business analyst. Extract structured information from the user's \
description of their business.

User said: "{message}"

Extract:
- business_name: The name of the business (if mentioned). If not, leave empty.
- industry: One of these categories: restaurant, clinic, retail, realestate, \
education, gym, salon, hotel, professional, other. Pick the closest match.
- location: City or area (if mentioned).
- products: List of products mentioned (e.g. "biryani", "coffee").
- services: List of services mentioned (e.g. "catering", "dental checkups").
- audience: Who the target customers seem to be.
- goals: What the business owner wants to achieve (stated or inferred).
- website: Website URL (if mentioned).
- social_handles: Social media handles (if mentioned).
- additional_context: Anything else useful (years in business, seasonality, \
special features, current marketing efforts).

Respond as JSON only, no markdown:
{{
  "business_name": "...",
  "industry": "...",
  "location": "...",
  "products": ["..."],
  "services": ["..."],
  "audience": "...",
  "goals": ["..."],
  "website": "...",
  "social_handles": ["..."],
  "additional_context": "..."
}}
"""

_UNDERSTANDING_PROMPT = """\
You are a world-class marketing strategist having a conversation with a business owner.

The business owner said: "{message}"

Here is what we extracted and analyzed about their business:
{analysis}

Write a response that makes the business owner feel understood. Include:

1. **reply**: A warm, conversational 2-3 sentence opening that shows you get \
their business. Speak like a knowledgeable friend ("bro" energy), not a robot. \
Never use the words "AI", "engine", "algorithm", or "data". Speak as "I".

2. **business**: A structured business understanding with:
   - summary: 2-3 sentence plain-language summary of their business
   - strengths: 3-4 strengths (what they're doing right or have going for them)
   - weaknesses: 2-3 weaknesses or gaps
   - likely_customers: 3-4 customer types they likely serve
   - likely_competitors: 2-3 competitor types (not specific names unless obvious)
   - marketing_opportunities: 3-4 marketing opportunities specific to their business
   - seasonal_opportunities: 2-3 seasonal opportunities (if applicable, else empty)
   - marketing_maturity: "Beginner", "Intermediate", or "Advanced" with a one-word reason
   - potential_risks: 2-3 risks to watch out for

3. **growth_opportunities**: Exactly 5 growth opportunities, each with:
   - title: Short, action-oriented title (e.g. "Launch weekday lunch combo")
   - description: 1-2 sentence description
   - business_impact: "High", "Medium", or "Low"
   - difficulty: "Easy", "Medium", or "Hard"
   - timeframe: e.g. "1-2 weeks", "1 month", "3 months"

4. **plan**: A 30-day marketing plan with 4 weeks, each with:
   - week: 1, 2, 3, or 4
   - theme: A short theme for the week (e.g. "Build your foundation")
   - objectives: 2-3 objectives for the week
   - content: 2-3 content pieces to create (e.g. "5 Instagram posts showing your best dishes")
   - offers: 1-2 offers or promotions (e.g. "Weekday lunch combo at ₹199")
   - channels: 2-3 channels to focus on (use friendly names: "Google", "Instagram", "WhatsApp")
   - kpis: 2-3 KPIs to track (in business language, e.g. "10 new reviews", "50 enquiries")

Be specific to their business. A biryani restaurant's plan should look \
different from a dental clinic's plan. Use business language only — \
never use marketing jargon like "ROAS", "CPA", "CTR", "funnel", "TOFU".

Respond as JSON only:
{{
  "reply": "...",
  "business": {{
    "summary": "...",
    "strengths": ["..."],
    "weaknesses": ["..."],
    "likely_customers": ["..."],
    "likely_competitors": ["..."],
    "marketing_opportunities": ["..."],
    "seasonal_opportunities": ["..."],
    "marketing_maturity": "...",
    "potential_risks": ["..."]
  }},
  "growth_opportunities": [
    {{"title": "...", "description": "...", "business_impact": "...", "difficulty": "...", "timeframe": "..."}}
  ],
  "plan": [
    {{"week": 1, "theme": "...", "objectives": ["..."], "content": ["..."], "offers": ["..."], "channels": ["..."], "kpis": ["..."]}}
  ]
}}
"""

_CAMPAIGN_PREVIEW_PROMPT = """\
You are a marketing strategist presenting a campaign recommendation to a business owner.

Business: {business_name}
Goal: {goal}
Budget: {budget}

Here is the full campaign analysis from our strategy team:
{campaign}

Create a campaign preview that feels like a presentation deck. Include:

1. **reply**: A 2-3 sentence conversational pitch for this campaign. Speak as "I". \
Make the owner excited but honest. Never use jargon.

2. **preview**: A campaign preview with:
   - title: A catchy campaign title (e.g. "Hyderabad's Best Biryani Tour")
   - hero_image_concept: Describe what the hero image should show (1 sentence)
   - video_concept: Describe a 30-second video concept (1-2 sentences)
   - post_ideas: 5 specific post ideas (e.g. "Behind-the-scenes: how we marinate the chicken for 12 hours")
   - estimated_reach: e.g. "15,000-25,000 people in Hyderabad"
   - expected_enquiries: e.g. "30-50 catering enquiries in the first month"
   - budget_estimate: e.g. "₹15,000/month (₹500/day)"
   - why_this_campaign: 2-3 sentences explaining why this campaign makes sense for their business
   - confidence: 0-100, how confident you are this will work
   - expected_benefit: 1 sentence on what they'll get out of it
   - risks: 2-3 risks (e.g. "Slow first week while ads learn your audience")
   - alternative: 1 sentence on a backup approach if this doesn't work

Use business language only. No jargon.

Respond as JSON only:
{{
  "reply": "...",
  "preview": {{
    "title": "...",
    "hero_image_concept": "...",
    "video_concept": "...",
    "post_ideas": ["..."],
    "estimated_reach": "...",
    "expected_enquiries": "...",
    "budget_estimate": "...",
    "why_this_campaign": "...",
    "confidence": 85,
    "expected_benefit": "...",
    "risks": ["..."],
    "alternative": "..."
  }}
}}
"""


# ─── Helpers ────────────────────────────────────────────────────────────────


_INDUSTRY_TO_CATEGORY: dict[str, str] = {
    "restaurant": "restaurant",
    "clinic": "healthcare",
    "dental": "healthcare",
    "healthcare": "healthcare",
    "retail": "retail",
    "shop": "retail",
    "store": "retail",
    "realestate": "realestate",
    "real estate": "realestate",
    "property": "realestate",
    "education": "education",
    "school": "education",
    "institute": "education",
    "coaching": "education",
    "gym": "fitness",
    "fitness": "fitness",
    "salon": "salon",
    "spa": "salon",
    "beauty": "salon",
    "hotel": "hospitality",
    "hospitality": "hospitality",
    "professional": "professional",
    "lawyer": "professional",
    "consultant": "professional",
    "agency": "professional",
}


def _map_industry_to_category(industry: str) -> str:
    """Map extracted industry to Brand.category."""
    ind = industry.lower().strip()
    if ind in _INDUSTRY_TO_CATEGORY:
        return _INDUSTRY_TO_CATEGORY[ind]
    # Fuzzy match
    for key, val in _INDUSTRY_TO_CATEGORY.items():
        if key in ind or ind in key:
            return val
    return "other"


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from an LLM response (handles markdown fences + prose)."""
    # Strip markdown code fences
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove first line (```json or ```)
        lines = cleaned.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]  # drop closing fence
        cleaned = "\n".join(lines)
    # Find first { and last }
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return {}
    return json.loads(cleaned[start : end + 1])


async def _get_or_create_brand(
    session: SessionDep,
    user: CurrentUser,
    extracted: BusinessExtraction,
    existing_brand_id: uuid.UUID | None,
) -> Brand:
    """Get an existing brand or create one from extracted info."""
    if existing_brand_id is not None:
        res = await session.execute(
            select(Brand).where(Brand.id == existing_brand_id, Brand.tenant_id == user.tenant_id)
        )
        brand = res.scalar_one_or_none()
        if brand is not None:
            return brand

    # Create a new brand from extracted info
    name = extracted.business_name or extracted.industry.title() or "My Business"
    category = _map_industry_to_category(extracted.industry)
    tone = {
        "voice": "Friendly, professional, authentic",
        "description": f"Tone appropriate for {category}.",
    }
    brand = Brand(
        tenant_id=user.tenant_id,
        name=name,
        website=extracted.website or None,
        category=category,
        locales=["en-IN"],
        tone=tone,
        brand_graph={
            "location": extracted.location,
            "products": extracted.products,
            "services": extracted.services,
            "audience": extracted.audience,
            "goals": extracted.goals,
            "social_handles": extracted.social_handles,
            "additional_context": extracted.additional_context,
        },
    )
    session.add(brand)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user,
        action="consult.brand_created",
        entity_type="brand", entity_id=brand.id,
        payload={"name": name, "category": category, "source": "conversational_onboarding"},
    )
    await session.commit()
    return brand


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("", response_model=ConsultResponse)
async def consult(
    body: ConsultRequest,
    user: CurrentUser,
    session: SessionDep,
) -> ConsultResponse:
    """The conversational onboarding endpoint.

    Takes a free-text business description and returns:
    - A conversational reply from CURV AI
    - Business understanding (strengths, weaknesses, customers, competitors)
    - Top 5 growth opportunities
    - A 30-day marketing plan

    Auto-creates a Brand record from the extracted info.
    Uses the existing Marketing Intelligence Engine for analysis.
    """
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)

    # ─── Step 1: Extract structured info from free text ──────────────────
    try:
        extract_comp = gw.complete(
            prompt=_EXTRACT_PROMPT.format(message=body.message[:1000]),
            tier=Tier.small,
            task="consult_extract",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=400,
            temperature=0.1,
            user_input=body.message,
            prompt_version="consult_extract_v1.0",
        )
    except BudgetExceeded:
        return ConsultResponse(
            reply=(
                "Hey! I've hit my AI usage limit for this month. "
                "Contact your admin to upgrade your plan, and we'll pick up where we left off."
            ),
        )
    except Exception as e:
        import logging
        logging.error("consult extract failed: %s", e)
        return ConsultResponse(
            reply=(
                "I couldn't quite process that. Could you tell me a bit more about your business? "
                "For example: 'We run a biryani restaurant in Hyderabad.'"
            ),
        )

    try:
        extracted_dict = _extract_json(extract_comp.text)
    except json.JSONDecodeError:
        extracted_dict = {}
    extracted = BusinessExtraction(**{k: v for k, v in extracted_dict.items() if k in BusinessExtraction.model_fields})

    # ─── Step 2: Create or get the brand ─────────────────────────────────
    try:
        brand = await _get_or_create_brand(session, user, extracted, body.brand_id)
    except Exception as e:
        import logging
        logging.error("consult brand creation failed: %s", e)
        return ConsultResponse(
            reply="I had trouble setting up your business profile. Please try again.",
            extracted=extracted,
        )

    # ─── Step 3: Run the Marketing Intelligence Engine ───────────────────
    analysis_text = ""
    engine_tokens = 0
    try:
        from prachar_shared.marketing_intelligence import CampaignBrain

        brain = CampaignBrain()
        result = await brain.analyse(
            tenant_id=user.tenant_id,
            plan=plan,
            business_name=brand.name,
            website=brand.website or "",
            category=brand.category or "",
            description=extracted.additional_context,
            goal="; ".join(extracted.goals) if extracted.goals else "grow the business",
            locale="en-IN",
            brand_id=brand.id,
            additional_context=body.message,
        )
        biz = result.get("business_profile", {})
        aud = result.get("audience_profile", {})
        comp = result.get("competitor_profile", {})
        analysis_text = (
            f"Business Profile: {json.dumps(biz, indent=2)}\n\n"
            f"Audience Profile: {json.dumps(aud, indent=2)}\n\n"
            f"Competitor Profile: {json.dumps(comp, indent=2)}"
        )
        engine_tokens = sum(
            eo.get("tokens_used", 0) for eo in result.get("engine_outputs", {}).values()
        )
    except BudgetExceeded:
        return ConsultResponse(
            reply=(
                "Hey! I've hit my AI usage limit for this month. "
                "Contact your admin to upgrade your plan."
            ),
            extracted=extracted,
            brand_id=str(brand.id),
            brand_name=brand.name,
        )
    except Exception as e:
        import logging
        logging.warning("consult analysis failed (continuing with extraction only): %s", e)
        analysis_text = f"Extracted info: {extracted.model_dump_json()}"

    # ─── Step 4: Convert analysis into conversational response + cards ───
    try:
        understanding_comp = gw.complete(
            prompt=_UNDERSTANDING_PROMPT.format(
                message=body.message[:1000],
                analysis=analysis_text[:6000],
            ),
            tier=Tier.small,
            task="consult_understanding",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=2000,
            temperature=0.7,
            user_input=body.message,
            prompt_version="consult_understanding_v1.0",
        )
    except BudgetExceeded:
        return ConsultResponse(
            reply=(
                "Hey! I've hit my AI usage limit for this month. "
                "I've set up your business profile — contact your admin to upgrade for the full analysis."
            ),
            extracted=extracted,
            brand_id=str(brand.id),
            brand_name=brand.name,
            tokens_used=engine_tokens + extract_comp.tokens_used,
        )
    except Exception as e:
        import logging
        logging.error("consult understanding failed: %s", e)
        return ConsultResponse(
            reply=(
                f"Thanks for telling me about {brand.name}! I've set up your business profile. "
                "I can build your marketing campaign whenever you're ready — just say the word."
            ),
            extracted=extracted,
            brand_id=str(brand.id),
            brand_name=brand.name,
            tokens_used=engine_tokens + extract_comp.tokens_used,
        )

    try:
        resp_dict = _extract_json(understanding_comp.text)
    except json.JSONDecodeError:
        resp_dict = {"reply": understanding_comp.text[:500]}

    # Parse the structured response
    biz_data = resp_dict.get("business", {})
    business = BusinessUnderstanding(
        summary=biz_data.get("summary", ""),
        strengths=biz_data.get("strengths", [])[:5],
        weaknesses=biz_data.get("weaknesses", [])[:5],
        likely_customers=biz_data.get("likely_customers", [])[:5],
        likely_competitors=biz_data.get("likely_competitors", [])[:5],
        marketing_opportunities=biz_data.get("marketing_opportunities", [])[:5],
        seasonal_opportunities=biz_data.get("seasonal_opportunities", [])[:5],
        marketing_maturity=biz_data.get("marketing_maturity", ""),
        potential_risks=biz_data.get("potential_risks", [])[:5],
    )

    opportunities = [
        GrowthOpportunity(
            title=op.get("title", ""),
            description=op.get("description", ""),
            business_impact=op.get("business_impact", "Medium"),
            difficulty=op.get("difficulty", "Medium"),
            timeframe=op.get("timeframe", "1 month"),
        )
        for op in resp_dict.get("growth_opportunities", [])[:5]
        if op.get("title")
    ]

    plan_weeks = []
    for wk in resp_dict.get("plan", [])[:4]:
        try:
            plan_weeks.append(WeekPlan(
                week=int(wk.get("week", len(plan_weeks) + 1)),
                theme=str(wk.get("theme", "")),
                objectives=wk.get("objectives", [])[:3],
                content=wk.get("content", [])[:3],
                offers=wk.get("offers", [])[:2],
                channels=wk.get("channels", [])[:3],
                kpis=wk.get("kpis", [])[:3],
            ))
        except (TypeError, ValueError):
            continue

    return ConsultResponse(
        reply=resp_dict.get("reply", f"Thanks for telling me about {brand.name}!"),
        business=business,
        growth_opportunities=opportunities,
        plan=plan_weeks,
        extracted=extracted,
        brand_id=str(brand.id),
        brand_name=brand.name,
        confidence=understanding_comp.confidence,
        tokens_used=engine_tokens + extract_comp.tokens_used + understanding_comp.tokens_used,
        model=understanding_comp.model,
    )


@router.post("/campaign", response_model=CampaignPreviewResponse)
async def campaign_preview(
    body: CampaignPreviewRequest,
    user: CurrentUser,
    session: SessionDep,
) -> CampaignPreviewResponse:
    """Generate a campaign preview from the consultation.

    Uses the existing CampaignBrain.generate_campaign() to build a full campaign,
    then converts it into a presentation-deck-style preview.
    """
    # Get the brand
    res = await session.execute(
        select(Brand).where(Brand.id == body.brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    plan = await get_tenant_plan(session, user)
    gw = AIGateway()

    # ─── Run the full campaign generation ────────────────────────────────
    try:
        from prachar_shared.marketing_intelligence import CampaignBrain

        brain = CampaignBrain()
        campaign = await brain.generate_campaign(
            tenant_id=user.tenant_id,
            plan=plan,
            business_name=brand.name,
            website=brand.website or "",
            category=brand.category or "",
            description="",
            goal=body.goal or "grow the business",
            budget=body.budget,
            locale="en-IN",
            brand_id=brand.id,
            brand_graph=brand.brand_graph or {},
        )
    except BudgetExceeded:
        return CampaignPreviewResponse(
            reply="I've hit my AI usage limit for this month. Contact your admin to upgrade.",
            preview=CampaignPreview(
                title="", hero_image_concept="", video_concept="",
                post_ideas=[], estimated_reach="", expected_enquiries="",
                budget_estimate="", why_this_campaign="", confidence=0,
                expected_benefit="", risks=[], alternative="",
            ),
        )
    except Exception as e:
        import logging
        logging.error("consult campaign generation failed: %s", e)
        return CampaignPreviewResponse(
            reply="I couldn't build the campaign right now. Please try again in a moment.",
            preview=CampaignPreview(
                title="", hero_image_concept="", video_concept="",
                post_ideas=[], estimated_reach="", expected_enquiries="",
                budget_estimate="", why_this_campaign="", confidence=0,
                expected_benefit="", risks=[], alternative="",
            ),
        )

    # ─── Convert to presentation-deck preview ────────────────────────────
    campaign_text = campaign.executive_summary or json.dumps(campaign.to_dict(), indent=2)
    engine_tokens = campaign.total_tokens

    try:
        preview_comp = gw.complete(
            prompt=_CAMPAIGN_PREVIEW_PROMPT.format(
                business_name=brand.name,
                goal=body.goal,
                budget=body.budget,
                campaign=campaign_text[:6000],
            ),
            tier=Tier.small,
            task="consult_campaign_preview",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=1500,
            temperature=0.7,
            user_input=body.goal,
            prompt_version="consult_campaign_preview_v1.0",
        )
    except BudgetExceeded:
        return CampaignPreviewResponse(
            reply="I built your campaign but hit my AI usage limit while preparing the preview. Contact your admin to upgrade.",
            preview=CampaignPreview(
                title=f"{brand.name} Campaign",
                hero_image_concept="", video_concept="",
                post_ideas=[], estimated_reach="", expected_enquiries="",
                budget_estimate=body.budget, why_this_campaign="",
                confidence=campaign.overall_confidence,
                expected_benefit="", risks=[], alternative="",
            ),
            tokens_used=engine_tokens,
        )
    except Exception as e:
        import logging
        logging.error("consult campaign preview failed: %s", e)
        return CampaignPreviewResponse(
            reply=f"I've built a campaign for {brand.name}. Here's the summary: {campaign.executive_summary[:300]}",
            preview=CampaignPreview(
                title=f"{brand.name} Campaign",
                hero_image_concept="", video_concept="",
                post_ideas=[], estimated_reach="", expected_enquiries="",
                budget_estimate=body.budget, why_this_campaign=campaign.executive_summary or "",
                confidence=campaign.overall_confidence,
                expected_benefit="", risks=[], alternative="",
            ),
            tokens_used=engine_tokens,
        )

    try:
        resp_dict = _extract_json(preview_comp.text)
    except json.JSONDecodeError:
        resp_dict = {"reply": preview_comp.text[:500], "preview": {}}

    preview_data = resp_dict.get("preview", {})
    preview = CampaignPreview(
        title=preview_data.get("title", f"{brand.name} Campaign"),
        hero_image_concept=preview_data.get("hero_image_concept", ""),
        video_concept=preview_data.get("video_concept", ""),
        post_ideas=preview_data.get("post_ideas", [])[:5],
        estimated_reach=preview_data.get("estimated_reach", ""),
        expected_enquiries=preview_data.get("expected_enquiries", ""),
        budget_estimate=preview_data.get("budget_estimate", body.budget),
        why_this_campaign=preview_data.get("why_this_campaign", ""),
        confidence=float(preview_data.get("confidence", campaign.overall_confidence * 100)),
        expected_benefit=preview_data.get("expected_benefit", ""),
        risks=preview_data.get("risks", [])[:3],
        alternative=preview_data.get("alternative", ""),
    )

    # Persist the campaign plan
    from ..models import CampaignPlanRecord
    record = CampaignPlanRecord(
        tenant_id=user.tenant_id,
        brand_id=brand.id,
        name=preview.title,
        goal=body.goal,
        budget=body.budget,
        locale="en-IN",
        campaign=campaign.to_dict(),
        overall_confidence=campaign.overall_confidence,
        total_cost_usd=campaign.total_cost_usd,
        total_tokens=campaign.total_tokens,
        status="draft",
    )
    session.add(record)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user,
        action="consult.campaign_preview",
        entity_type="campaign_plan", entity_id=record.id,
        payload={"name": preview.title, "goal": body.goal},
    )
    await session.commit()

    return CampaignPreviewResponse(
        reply=resp_dict.get("reply", f"Here's the campaign I'd recommend for {brand.name}."),
        preview=preview,
        campaign_plan_id=str(record.id),
        tokens_used=engine_tokens + preview_comp.tokens_used,
        model=preview_comp.model,
    )
