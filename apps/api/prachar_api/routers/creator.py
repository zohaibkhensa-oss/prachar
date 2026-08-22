"""Creator Intelligence router — conversational onboarding for content creators.

This is the creator equivalent of /consult. It takes a free-text description
of a creator's channel and returns:
1. A Creator Profile (niche, platforms, audience, content pillars, growth stage)
2. Current Position (strengths, weaknesses, growth opportunities, content gaps, monetisation)
3. A 30-Day Creator Growth Plan (videos, shorts, reels, community posts, collaborations, SEO, newsletter, live sessions)
4. A campaign preview (content plan + publishing schedule)

It does NOT duplicate the Marketing Intelligence Engine. It uses the AIGateway
directly with creator-specific prompts, just as /consult uses the AIGateway with
business-specific prompts. The CampaignBrain is reused for campaign generation.

Endpoints:
  POST /creator/consult       — Creator Intelligence (analysis + plan)
  POST /creator/campaign      — Creator campaign (content plan + publishing schedule)
  POST /creator/repurpose     — Content repurposing (1 video → 11 asset types)
  POST /creator/youtube-plan  — YouTube video planning (title, thumbnail, hook, SEO, etc.)
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
from ..models import Actor, Brand, CampaignPlanRecord
from prachar_shared.ai_gateway import AIGateway, Tier, BudgetExceeded

router = APIRouter(prefix="/creator", tags=["creator"])


# ─── Request / Response schemas ─────────────────────────────────────────────


class CreatorConsultRequest(BaseModel):
    """The creator's free-text channel description."""

    message: str = Field(..., min_length=5, max_length=2000,
                         description="The creator's description of their channel")
    creator_type: str = Field("youtube_creator",
                         description="Creator type: youtube_creator, instagram_creator, podcaster, etc.")
    brand_id: uuid.UUID | None = Field(None, description="Existing brand ID if user has one")


class CreatorProfile(BaseModel):
    """Structured understanding of a creator's channel."""

    niche: str = Field("", description="Content niche, e.g. 'tech reviews for Indian audiences'")
    platforms: list[str] = Field(default_factory=list, description="Primary platforms")
    upload_frequency: str = Field("", description="e.g. '2 videos/week, 3 shorts/week'")
    content_pillars: list[str] = Field(default_factory=list, description="Main content themes")
    audience: str = Field("", description="Who watches/follows them")
    audience_size: str = Field("", description="e.g. '12K subscribers, 5K Instagram followers'")
    growth_stage: str = Field("", description="e.g. 'Emerging', 'Growing', 'Established', 'Pro'")
    monetisation: str = Field("", description="Current monetisation methods")
    brand_partnerships: list[str] = Field(default_factory=list, description="Notable brand deals if any")
    competitors: list[str] = Field(default_factory=list, description="Similar creators in the niche")


class CreatorPosition(BaseModel):
    """Where the creator is now — strengths, weaknesses, opportunities."""

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    growth_opportunities: list[str] = Field(default_factory=list)
    content_gaps: list[str] = Field(default_factory=list)
    monetisation_opportunities: list[str] = Field(default_factory=list)


class CreatorWeekPlan(BaseModel):
    """One week of the 30-day creator growth plan."""

    week: int
    theme: str
    videos: list[str] = Field(default_factory=list, description="Long-form video ideas")
    shorts: list[str] = Field(default_factory=list, description="Shorts/Reels ideas")
    community_posts: list[str] = Field(default_factory=list)
    collaborations: list[str] = Field(default_factory=list)
    seo: list[str] = Field(default_factory=list, description="SEO/optimisation tasks")
    newsletter: str = Field("", description="Newsletter content for the week")
    live_sessions: str = Field("", description="Live session plan for the week")
    kpis: list[str] = Field(default_factory=list)


class CreatorConsultResponse(BaseModel):
    """The full creator consultation response."""

    reply: str = Field(..., description="CURV AI's conversational response")
    profile: CreatorProfile = Field(default_factory=CreatorProfile)
    position: CreatorPosition = Field(default_factory=CreatorPosition)
    plan: list[CreatorWeekPlan] = Field(default_factory=list)
    brand_id: str = ""
    brand_name: str = ""
    confidence: float = 0.0
    tokens_used: int = 0
    model: str = "stub"


class RepurposeRequest(BaseModel):
    """Request to repurpose one YouTube video into multiple asset types."""

    video_title: str = Field("", description="The video title")
    video_description: str = Field(..., min_length=10, max_length=5000,
                         description="The video description or transcript summary")
    niche: str = Field("", description="Creator's niche for tone/style")
    brand_id: uuid.UUID | None = Field(None)


class RepurposedAsset(BaseModel):
    """One repurposed asset."""

    asset_type: str  # "YouTube Shorts", "Instagram Reels", etc.
    content: str
    notes: str = Field("", description="Posting tips for this asset type")


class RepurposeResponse(BaseModel):
    reply: str
    assets: list[RepurposedAsset] = Field(default_factory=list)
    tokens_used: int = 0
    model: str = "stub"


class YouTubePlanRequest(BaseModel):
    """Request for a full YouTube video plan."""

    video_concept: str = Field(..., min_length=5, max_length=1000,
                         description="The video concept, e.g. 'Review of the new iPhone 16 Pro'")
    niche: str = Field("", description="Creator's niche")
    audience: str = Field("", description="Target audience")
    brand_id: uuid.UUID | None = Field(None)


class YouTubePlan(BaseModel):
    """A complete YouTube video plan."""

    title_options: list[str] = Field(default_factory=list, description="5 title options")
    thumbnail_concepts: list[str] = Field(default_factory=list, description="3 thumbnail concepts")
    opening_hook: str = Field("", description="The first 10 seconds — the hook")
    retention_improvements: list[str] = Field(default_factory=list, description="Techniques to keep viewers watching")
    description: str = Field("", description="Full video description")
    seo_keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    chapters: list[str] = Field(default_factory=list, description="Chapter markers with timestamps")
    pinned_comment: str = Field("", description="The pinned comment to drive engagement")
    community_post: str = Field("", description="A community post to promote the video")
    end_screen_suggestions: list[str] = Field(default_factory=list, description="End screen video suggestions")


class YouTubePlanResponse(BaseModel):
    reply: str
    plan: YouTubePlan = Field(default_factory=YouTubePlan)
    tokens_used: int = 0
    model: str = "stub"


class CreatorCampaignRequest(BaseModel):
    """Request to generate a creator campaign (content plan + publishing schedule)."""

    brand_id: uuid.UUID
    goal: str = Field("", description="e.g. 'grow to 10K subscribers' or 'launch merchandise'")
    budget: str = Field("₹15,000/month", description="Budget in plain language")


class CreatorCampaignResponse(BaseModel):
    reply: str
    title: str = ""
    content_plan: list[CreatorWeekPlan] = Field(default_factory=list)
    publishing_schedule: str = ""
    expected_growth: str = ""
    confidence: float = 0.0
    campaign_plan_id: str = ""
    tokens_used: int = 0
    model: str = "stub"


# ─── LLM prompts ────────────────────────────────────────────────────────────

_CONSULT_PROMPT = """\
You are a world-class creator strategist having a conversation with a content creator.

The creator said: "{message}"

Creator type: {creator_type}

Write a response that makes the creator feel understood. Include:

1. **reply**: A warm, conversational 2-3 sentence opening that shows you get \
their channel. Speak like a knowledgeable friend ("bro" energy), not a robot. \
Never use the words "AI", "engine", "algorithm", or "data". Speak as "I".

2. **profile**: A structured creator profile:
   - niche: Their content niche (be specific, e.g. "tech reviews for Indian audiences")
   - platforms: Primary platforms (e.g. ["YouTube", "Instagram"])
   - upload_frequency: Their posting cadence (e.g. "2 videos/week, 3 shorts/week")
   - content_pillars: 3-4 main content themes
   - audience: Who watches/follows them
   - audience_size: Estimated audience size if inferrable
   - growth_stage: "Emerging" (<10K), "Growing" (10K-100K), "Established" (100K-1M), or "Pro" (1M+)
   - monetisation: Current monetisation methods (or "Not yet monetised")
   - brand_partnerships: Any notable brand deals mentioned
   - competitors: 2-3 similar creators in the niche

3. **position**: Where they are now:
   - strengths: 3-4 strengths
   - weaknesses: 2-3 weaknesses or gaps
   - growth_opportunities: 3-4 growth opportunities specific to their channel
   - content_gaps: 2-3 content types they're missing
   - monetisation_opportunities: 2-3 monetisation opportunities

4. **plan**: A 30-day growth plan with 4 weeks, each with:
   - week: 1, 2, 3, or 4
   - theme: Short theme (e.g. "Double down on shorts")
   - videos: 1-2 long-form video ideas
   - shorts: 3-5 shorts/reels ideas
   - community_posts: 2-3 community post ideas
   - collaborations: 1-2 collaboration ideas
   - seo: 1-2 SEO/optimisation tasks
   - newsletter: Newsletter content for the week (or "" if no newsletter)
   - live_sessions: Live session plan (or "" if not applicable)
   - kpis: 2-3 KPIs to track (e.g. "5K new subscribers", "10% CTR")

Be specific to their niche. A tech reviewer's plan should look different from \
a gaming creator's plan. Use creator language — never use business jargon like \
"ROAS", "CPA", "conversions", "customers".

Respond as JSON only:
{{
  "reply": "...",
  "profile": {{
    "niche": "...",
    "platforms": ["..."],
    "upload_frequency": "...",
    "content_pillars": ["..."],
    "audience": "...",
    "audience_size": "...",
    "growth_stage": "...",
    "monetisation": "...",
    "brand_partnerships": ["..."],
    "competitors": ["..."]
  }},
  "position": {{
    "strengths": ["..."],
    "weaknesses": ["..."],
    "growth_opportunities": ["..."],
    "content_gaps": ["..."],
    "monetisation_opportunities": ["..."]
  }},
  "plan": [
    {{
      "week": 1,
      "theme": "...",
      "videos": ["..."],
      "shorts": ["..."],
      "community_posts": ["..."],
      "collaborations": ["..."],
      "seo": ["..."],
      "newsletter": "...",
      "live_sessions": "...",
      "kpis": ["..."]
    }}
  ]
}}
"""

_REPURPOSE_PROMPT = """\
You are a content repurposing expert. Given one YouTube video, create 11 \
repurposed assets — each optimised for its platform.

Video title: "{title}"
Video description/transcript: "{description}"
Creator niche: {niche}

Create these 11 assets:

1. **YouTube Shorts** — 3 short scripts (30-60 seconds each), each with a \
strong hook in the first 3 seconds. Format: "Short 1: [script]"

2. **Instagram Reels** — 2 reel concepts with visual descriptions and captions. \
Format: "Reel 1: [concept + caption]"

3. **Facebook Reel** — 1 reel adapted for Facebook audience (slightly longer, \
more context). Format: "[concept + script]"

4. **LinkedIn Post** — 1 professional post extracting the key insight. \
150-300 words. No hashtags in the body.

5. **X Thread** — 1 thread of 5-7 tweets. First tweet is the hook. \
Each tweet standalone-readable.

6. **Blog Article** — 1 blog post outline with 5-7 sections, each with a \
1-sentence summary. Include suggested title and meta description.

7. **Newsletter** — 1 newsletter section (200-400 words) summarising the video \
for email subscribers. Include subject line.

8. **Email** — 1 short email (100-150 words) promoting the video to a list. \
Include subject line.

9. **Community Post** — 1 YouTube community post (poll or text) to drive \
engagement before/after the video.

10. **Podcast Summary** — If the video were a podcast episode, a 100-word \
summary for podcast directories.

11. **Sponsor Pitch** — A 100-word pitch to a relevant brand explaining why \
they should sponsor this content.

Respond as JSON only:
{{
  "reply": "A 1-2 sentence conversational summary of what you created.",
  "assets": [
    {{"asset_type": "YouTube Shorts", "content": "...", "notes": "..."}},
    {{"asset_type": "Instagram Reels", "content": "...", "notes": "..."}},
    {{"asset_type": "Facebook Reel", "content": "...", "notes": "..."}},
    {{"asset_type": "LinkedIn Post", "content": "...", "notes": "..."}},
    {{"asset_type": "X Thread", "content": "...", "notes": "..."}},
    {{"asset_type": "Blog Article", "content": "...", "notes": "..."}},
    {{"asset_type": "Newsletter", "content": "...", "notes": "..."}},
    {{"asset_type": "Email", "content": "...", "notes": "..."}},
    {{"asset_type": "Community Post", "content": "...", "notes": "..."}},
    {{"asset_type": "Podcast Summary", "content": "...", "notes": "..."}},
    {{"asset_type": "Sponsor Pitch", "content": "...", "notes": "..."}}
  ]
}}
"""

_YOUTUBE_PLAN_PROMPT = """\
You are a YouTube growth expert. Create a complete video plan for one video.

Video concept: "{concept}"
Creator niche: {niche}
Target audience: {audience}

Create:

1. **title_options**: 5 title options. Each must be:
   - Under 70 characters
   - Clickable but not clickbait
   - Optimised for search and CTR

2. **thumbnail_concepts**: 3 thumbnail concepts. Each describes:
   - The main visual
   - Text overlay (max 5 words)
   - Emotion/expression

3. **opening_hook**: The first 10 seconds of the video — the script that \
keeps viewers from clicking away.

4. **retention_improvements**: 3-5 techniques to keep viewers watching \
(e.g. "Tease the best part at 0:30", "Use pattern interrupts every 60 seconds").

5. **description**: A full video description (200-400 words) with:
   - First 2 lines are the hook (visible before "Show more")
   - Key points
   - Timestamps
   - Call to action
   - Links to social

6. **seo_keywords**: 10 SEO keywords for this video.

7. **tags**: 15 tags (mix of broad and specific).

8. **chapters**: Chapter markers with timestamps (e.g. "0:00 Intro", "1:30 The problem").

9. **pinned_comment**: A pinned comment that drives engagement \
(asks a question, offers a resource, or teases the next video).

10. **community_post**: A community post to promote the video 24 hours before launch.

11. **end_screen_suggestions**: 3 end screen video suggestions \
(describe which videos to link and why).

Respond as JSON only:
{{
  "reply": "A 1-2 sentence conversational summary.",
  "plan": {{
    "title_options": ["..."],
    "thumbnail_concepts": ["..."],
    "opening_hook": "...",
    "retention_improvements": ["..."],
    "description": "...",
    "seo_keywords": ["..."],
    "tags": ["..."],
    "chapters": ["..."],
    "pinned_comment": "...",
    "community_post": "...",
    "end_screen_suggestions": ["..."]
  }}
}}
"""

_CREATOR_CAMPAIGN_PROMPT = """\
You are a creator growth strategist. Create a 30-day content campaign for a creator.

Creator: {creator_name}
Goal: {goal}
Budget: {budget}

Here is the creator's profile and analysis:
{analysis}

Create a content campaign that includes:

1. **reply**: A 2-3 sentence conversational pitch for this campaign.

2. **title**: A catchy campaign title (e.g. "Tech Tuesday Marathon" or \
"Road to 10K Subscribers").

3. **content_plan**: A 4-week content plan (reuse the weekly structure with \
videos, shorts, community_posts, collaborations, seo, newsletter, \
live_sessions, kpis).

4. **publishing_schedule**: A summary of the publishing cadence \
(e.g. "2 long-form videos/week on Tue+Fri, 3 shorts/week, 1 community post/week").

5. **expected_growth**: What they can expect in 30 days \
(e.g. "2,000-3,000 new subscribers if execution is consistent").

6. **confidence**: 0-100, how confident you are this plan will work.

Use creator language only. No business jargon.

Respond as JSON only:
{{
  "reply": "...",
  "title": "...",
  "content_plan": [
    {{
      "week": 1,
      "theme": "...",
      "videos": ["..."],
      "shorts": ["..."],
      "community_posts": ["..."],
      "collaborations": ["..."],
      "seo": ["..."],
      "newsletter": "...",
      "live_sessions": "...",
      "kpis": ["..."]
    }}
  ],
  "publishing_schedule": "...",
  "expected_growth": "...",
  "confidence": 85
}}
"""


# ─── Helpers ────────────────────────────────────────────────────────────────


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from an LLM response (handles markdown fences + prose)."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return {}
    return json.loads(cleaned[start : end + 1])


_CREATOR_TYPE_TO_CATEGORY: dict[str, str] = {
    "youtube_creator": "youtube",
    "instagram_creator": "instagram",
    "podcaster": "podcast",
    "influencer": "influencer",
    "gaming_creator": "gaming",
    "educator": "education",
    "media_company": "media",
    "production_studio": "production",
    "musician": "music",
    "personal_brand": "personal",
}


async def _get_or_create_creator_brand(
    session: SessionDep,
    user: CurrentUser,
    message: str,
    creator_type: str,
    existing_brand_id: uuid.UUID | None,
) -> Brand:
    """Get an existing brand or create one for a creator."""
    if existing_brand_id is not None:
        res = await session.execute(
            select(Brand).where(Brand.id == existing_brand_id, Brand.tenant_id == user.tenant_id)
        )
        brand = res.scalar_one_or_none()
        if brand is not None:
            return brand

    category = _CREATOR_TYPE_TO_CATEGORY.get(creator_type, "creator")
    # Try to infer a name from the message
    name = "My Channel"
    # Simple heuristic: look for "called X" or "named X" or "channel X"
    lower = message.lower()
    for prefix in ["called ", "named ", "channel ", "@"]:
        idx = lower.find(prefix)
        if idx != -1:
            rest = message[idx + len(prefix):].strip()
            # Take first 3-5 words
            words = rest.split()[:4]
            name = " ".join(words).rstrip(",.;!?")
            break

    brand = Brand(
        tenant_id=user.tenant_id,
        name=name,
        category=category,
        customer_type="creator",
        locales=["en-IN"],
        tone={"voice": "Authentic, engaging, creator-native", "description": f"Tone for {category} creator."},
        brand_graph={
            "creator_type": creator_type,
            "description": message,
        },
    )
    session.add(brand)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user,
        action="creator.brand_created",
        entity_type="brand", entity_id=brand.id,
        payload={"name": name, "creator_type": creator_type, "source": "conversational_onboarding"},
    )
    await session.commit()
    return brand


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.post("/consult", response_model=CreatorConsultResponse)
async def creator_consult(
    body: CreatorConsultRequest,
    user: CurrentUser,
    session: SessionDep,
) -> CreatorConsultResponse:
    """The creator conversational onboarding endpoint.

    Takes a free-text channel description and returns:
    - A conversational reply from CURV AI
    - A Creator Profile (niche, platforms, audience, growth stage, monetisation)
    - Current Position (strengths, weaknesses, opportunities, content gaps)
    - A 30-day creator growth plan (videos, shorts, reels, community posts, etc.)

    Auto-creates a Brand record with customer_type="creator".
    """
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)

    # Create or get the brand
    try:
        brand = await _get_or_create_creator_brand(session, user, body.message, body.creator_type, body.brand_id)
    except Exception as e:
        import logging
        logging.error("creator brand creation failed: %s", e)
        return CreatorConsultResponse(
            reply="I had trouble setting up your channel profile. Please try again.",
        )

    # Generate the creator analysis + plan in one LLM call
    try:
        comp = gw.complete(
            prompt=_CONSULT_PROMPT.format(
                message=body.message[:1500],
                creator_type=body.creator_type,
            ),
            tier=Tier.small,
            task="creator_consult",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=2500,
            temperature=0.7,
            user_input=body.message,
            prompt_version="creator_consult_v1.0",
        )
    except BudgetExceeded:
        return CreatorConsultResponse(
            reply="I've hit my AI usage limit for this month. Contact your admin to upgrade.",
            brand_id=str(brand.id),
            brand_name=brand.name,
        )
    except Exception as e:
        import logging
        logging.error("creator consult failed: %s", e)
        return CreatorConsultResponse(
            reply=f"Thanks for telling me about your channel! I've set up your profile. I can build your content plan whenever you're ready.",
            brand_id=str(brand.id),
            brand_name=brand.name,
        )

    try:
        resp_dict = _extract_json(comp.text)
    except json.JSONDecodeError:
        resp_dict = {"reply": comp.text[:500]}

    profile_data = resp_dict.get("profile", {})
    profile = CreatorProfile(
        niche=profile_data.get("niche", ""),
        platforms=profile_data.get("platforms", [])[:5],
        upload_frequency=profile_data.get("upload_frequency", ""),
        content_pillars=profile_data.get("content_pillars", [])[:5],
        audience=profile_data.get("audience", ""),
        audience_size=profile_data.get("audience_size", ""),
        growth_stage=profile_data.get("growth_stage", ""),
        monetisation=profile_data.get("monetisation", ""),
        brand_partnerships=profile_data.get("brand_partnerships", [])[:5],
        competitors=profile_data.get("competitors", [])[:5],
    )

    position_data = resp_dict.get("position", {})
    position = CreatorPosition(
        strengths=position_data.get("strengths", [])[:5],
        weaknesses=position_data.get("weaknesses", [])[:5],
        growth_opportunities=position_data.get("growth_opportunities", [])[:5],
        content_gaps=position_data.get("content_gaps", [])[:5],
        monetisation_opportunities=position_data.get("monetisation_opportunities", [])[:5],
    )

    plan_weeks = []
    for wk in resp_dict.get("plan", [])[:4]:
        try:
            plan_weeks.append(CreatorWeekPlan(
                week=int(wk.get("week", len(plan_weeks) + 1)),
                theme=str(wk.get("theme", "")),
                videos=wk.get("videos", [])[:2],
                shorts=wk.get("shorts", [])[:5],
                community_posts=wk.get("community_posts", [])[:3],
                collaborations=wk.get("collaborations", [])[:2],
                seo=wk.get("seo", [])[:2],
                newsletter=str(wk.get("newsletter", "")),
                live_sessions=str(wk.get("live_sessions", "")),
                kpis=wk.get("kpis", [])[:3],
            ))
        except (TypeError, ValueError):
            continue

    # Update brand_graph with the profile
    brand.brand_graph = {
        **(brand.brand_graph or {}),
        "profile": profile.model_dump(),
        "position": position.model_dump(),
    }
    await session.commit()

    return CreatorConsultResponse(
        reply=resp_dict.get("reply", f"Thanks for telling me about your channel!"),
        profile=profile,
        position=position,
        plan=plan_weeks,
        brand_id=str(brand.id),
        brand_name=brand.name,
        confidence=comp.confidence,
        tokens_used=comp.tokens_used,
        model=comp.model,
    )


@router.post("/repurpose", response_model=RepurposeResponse)
async def repurpose(
    body: RepurposeRequest,
    user: CurrentUser,
    session: SessionDep,
) -> RepurposeResponse:
    """Repurpose one YouTube video into 11 asset types.

    Given a video title and description/transcript, generates:
    YouTube Shorts, Instagram Reels, Facebook Reel, LinkedIn Post, X Thread,
    Blog Article, Newsletter, Email, Community Post, Podcast Summary, Sponsor Pitch.
    """
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)

    try:
        comp = gw.complete(
            prompt=_REPURPOSE_PROMPT.format(
                title=body.video_title[:200],
                description=body.video_description[:3000],
                niche=body.niche or "general",
            ),
            tier=Tier.small,
            task="creator_repurpose",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=3000,
            temperature=0.7,
            user_input=body.video_description[:500],
            prompt_version="creator_repurpose_v1.0",
        )
    except BudgetExceeded:
        return RepurposeResponse(
            reply="I've hit my AI usage limit for this month. Contact your admin to upgrade.",
        )
    except Exception as e:
        import logging
        logging.error("creator repurpose failed: %s", e)
        return RepurposeResponse(
            reply="I couldn't repurpose this video right now. Please try again.",
        )

    try:
        resp_dict = _extract_json(comp.text)
    except json.JSONDecodeError:
        resp_dict = {"reply": comp.text[:500], "assets": []}

    assets = [
        RepurposedAsset(
            asset_type=a.get("asset_type", ""),
            content=a.get("content", ""),
            notes=a.get("notes", ""),
        )
        for a in resp_dict.get("assets", [])[:11]
        if a.get("asset_type")
    ]

    return RepurposeResponse(
        reply=resp_dict.get("reply", "Here are your repurposed assets!"),
        assets=assets,
        tokens_used=comp.tokens_used,
        model=comp.model,
    )


@router.post("/youtube-plan", response_model=YouTubePlanResponse)
async def youtube_plan(
    body: YouTubePlanRequest,
    user: CurrentUser,
    session: SessionDep,
) -> YouTubePlanResponse:
    """Generate a complete YouTube video plan.

    Given a video concept, generates: title options, thumbnail concepts,
    opening hook, retention improvements, description, SEO keywords, tags,
    chapters, pinned comment, community post, end screen suggestions.
    """
    gw = AIGateway()
    plan = await get_tenant_plan(session, user)

    try:
        comp = gw.complete(
            prompt=_YOUTUBE_PLAN_PROMPT.format(
                concept=body.video_concept[:500],
                niche=body.niche or "general",
                audience=body.audience or "general audience",
            ),
            tier=Tier.small,
            task="creator_youtube_plan",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=2500,
            temperature=0.7,
            user_input=body.video_concept[:500],
            prompt_version="creator_youtube_plan_v1.0",
        )
    except BudgetExceeded:
        return YouTubePlanResponse(
            reply="I've hit my AI usage limit for this month. Contact your admin to upgrade.",
        )
    except Exception as e:
        import logging
        logging.error("creator youtube plan failed: %s", e)
        return YouTubePlanResponse(
            reply="I couldn't build the video plan right now. Please try again.",
        )

    try:
        resp_dict = _extract_json(comp.text)
    except json.JSONDecodeError:
        resp_dict = {"reply": comp.text[:500], "plan": {}}

    plan_data = resp_dict.get("plan", {})
    yt_plan = YouTubePlan(
        title_options=plan_data.get("title_options", [])[:5],
        thumbnail_concepts=plan_data.get("thumbnail_concepts", [])[:3],
        opening_hook=plan_data.get("opening_hook", ""),
        retention_improvements=plan_data.get("retention_improvements", [])[:5],
        description=plan_data.get("description", ""),
        seo_keywords=plan_data.get("seo_keywords", [])[:10],
        tags=plan_data.get("tags", [])[:15],
        chapters=plan_data.get("chapters", [])[:10],
        pinned_comment=plan_data.get("pinned_comment", ""),
        community_post=plan_data.get("community_post", ""),
        end_screen_suggestions=plan_data.get("end_screen_suggestions", [])[:3],
    )

    return YouTubePlanResponse(
        reply=resp_dict.get("reply", "Here's your video plan!"),
        plan=yt_plan,
        tokens_used=comp.tokens_used,
        model=comp.model,
    )


@router.post("/campaign", response_model=CreatorCampaignResponse)
async def creator_campaign(
    body: CreatorCampaignRequest,
    user: CurrentUser,
    session: SessionDep,
) -> CreatorCampaignResponse:
    """Generate a 30-day creator content campaign.

    Uses the creator's profile (stored in brand_graph) to create a tailored
    content campaign with a 4-week plan, publishing schedule, and expected growth.
    """
    res = await session.execute(
        select(Brand).where(Brand.id == body.brand_id, Brand.tenant_id == user.tenant_id)
    )
    brand = res.scalar_one_or_none()
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "brand not found")

    gw = AIGateway()
    plan = await get_tenant_plan(session, user)

    analysis = json.dumps(brand.brand_graph or {}, indent=2)

    try:
        comp = gw.complete(
            prompt=_CREATOR_CAMPAIGN_PROMPT.format(
                creator_name=brand.name,
                goal=body.goal,
                budget=body.budget,
                analysis=analysis[:4000],
            ),
            tier=Tier.small,
            task="creator_campaign",
            tenant_id=user.tenant_id,
            plan=plan,
            max_tokens=2500,
            temperature=0.7,
            user_input=body.goal,
            prompt_version="creator_campaign_v1.0",
        )
    except BudgetExceeded:
        return CreatorCampaignResponse(
            reply="I've hit my AI usage limit for this month. Contact your admin to upgrade.",
        )
    except Exception as e:
        import logging
        logging.error("creator campaign failed: %s", e)
        return CreatorCampaignResponse(
            reply="I couldn't build the campaign right now. Please try again.",
        )

    try:
        resp_dict = _extract_json(comp.text)
    except json.JSONDecodeError:
        resp_dict = {"reply": comp.text[:500]}

    content_plan = []
    for wk in resp_dict.get("content_plan", [])[:4]:
        try:
            content_plan.append(CreatorWeekPlan(
                week=int(wk.get("week", len(content_plan) + 1)),
                theme=str(wk.get("theme", "")),
                videos=wk.get("videos", [])[:2],
                shorts=wk.get("shorts", [])[:5],
                community_posts=wk.get("community_posts", [])[:3],
                collaborations=wk.get("collaborations", [])[:2],
                seo=wk.get("seo", [])[:2],
                newsletter=str(wk.get("newsletter", "")),
                live_sessions=str(wk.get("live_sessions", "")),
                kpis=wk.get("kpis", [])[:3],
            ))
        except (TypeError, ValueError):
            continue

    # Persist the campaign plan
    record = CampaignPlanRecord(
        tenant_id=user.tenant_id,
        brand_id=brand.id,
        name=resp_dict.get("title", f"{brand.name} Campaign"),
        goal=body.goal,
        budget=body.budget,
        locale="en-IN",
        campaign={"content_plan": [w.model_dump() for w in content_plan], "publishing_schedule": resp_dict.get("publishing_schedule", ""), "expected_growth": resp_dict.get("expected_growth", "")},
        overall_confidence=float(resp_dict.get("confidence", 0.7)),
        total_cost_usd=0.0,
        total_tokens=comp.tokens_used,
        status="draft",
    )
    session.add(record)
    await session.flush()
    await log_audit(
        session, tenant_id=user.tenant_id, actor=Actor.user,
        action="creator.campaign",
        entity_type="campaign_plan", entity_id=record.id,
        payload={"name": resp_dict.get("title", ""), "goal": body.goal},
    )
    await session.commit()

    return CreatorCampaignResponse(
        reply=resp_dict.get("reply", f"Here's your campaign for {brand.name}!"),
        title=resp_dict.get("title", f"{brand.name} Campaign"),
        content_plan=content_plan,
        publishing_schedule=resp_dict.get("publishing_schedule", ""),
        expected_growth=resp_dict.get("expected_growth", ""),
        confidence=float(resp_dict.get("confidence", 0.7)),
        campaign_plan_id=str(record.id),
        tokens_used=comp.tokens_used,
        model=comp.model,
    )
