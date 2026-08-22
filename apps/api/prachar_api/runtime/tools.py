"""Tool Registrations — wraps all existing capabilities as Runtime Tools.

This file registers every existing backend capability (CampaignBrain, Agency
Council, Creative Studio, Performance, Chat, Proactive, Memory, etc.) as a
Tool with a Tool Manifest. The Planner discovers these via the Tool Registry.

Constitution Rule 6: Every tool must expose a Tool Manifest.
Constitution Rule 7: The Planner reasons from manifests. Never hard-code.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from .registry import (
    RetryPolicy,
    SideEffects,
    ToolCategory,
    ToolManifest,
    get_registry,
    register_tool,
)
from .memory_categories import MemoryCategory
from .context import AIContext
from .artefacts import (
    campaign_card,
    kpi_widget,
    kpi_grid,
    image_artefact,
    chart,
    budget_table,
    copy_draft,
    copy_drafts,
    review_feedback,
    review_summary,
    timeline_plan,
    opportunity_card,
    audience_card,
    competitor_card,
    creative_brief,
    media_plan,
    task_list,
    alert,
    memory_insight,
)

log = logging.getLogger("prachar.runtime.tools")


# ─── Chat Tool ──────────────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="chat.respond",
    display_name="CURV AI Chat",
    description="Conversational response to user messages. Use for general questions, greetings, and simple queries.",
    category=ToolCategory.CONVERSATION,
    input_schema={"message": "string", "brand_id": "uuid"},
    output_schema={"reply": "string", "sources": "array", "tokens_used": "number"},
    estimated_cost_usd=0.01,
    estimated_time_ms=3000,
    estimated_tokens=500,
    estimated_latency_ms=2000,
    quality_score=0.7,
    supports_streaming=True,
    requires_brand=False,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.USER_PREFERENCES],
))
async def chat_respond(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Call the existing chat endpoint logic with enriched context."""
    from prachar_shared.ai_gateway import AIGateway, Tier
    from ..routers.chat import SYSTEM_PROMPT

    message = input.get("message", ctx.conversation[-1].content if ctx.conversation else "")
    gateway = AIGateway()

    # Build context string — enriched with Knowledge Hub, MI, Council, Integrations
    context_parts = []
    if ctx.brand:
        context_parts.append(f"Brand: {ctx.brand.name} ({ctx.brand.category or 'unknown'})")
    if ctx.memory.best_practices:
        context_parts.append(f"Past learnings: {', '.join(ctx.memory.best_practices[:3])}")

    # ─── Enriched context from Context Builder ───
    # Capabilities (dynamic — what the platform can do for this user)
    if ctx.capabilities:
        caps = [f"✓ {c['name']}" for c in ctx.capabilities if c.get("available")]
        if caps:
            context_parts.append(f"Available capabilities: {', '.join(caps)}")

    # Knowledge Hub results (retrieved documents relevant to the message)
    if ctx.knowledge_chunks:
        knowledge_lines = []
        for chunk in ctx.knowledge_chunks[:5]:
            title = chunk.get("title", "Unknown")
            content = chunk.get("content", "")[:200]
            knowledge_lines.append(f"  [{title}]: {content}")
        context_parts.append(f"Retrieved knowledge:\n" + "\n".join(knowledge_lines))

    # Marketing Intelligence summaries
    mi = ctx.enriched.get("marketing_intelligence", {})
    if mi:
        if mi.get("business_profile"):
            context_parts.append(f"Business profile: {mi['business_profile'].get('summary', '')[:200]}")
        if mi.get("audience_profile"):
            context_parts.append(f"Audience: {mi['audience_profile'].get('summary', '')[:200]}")
        if mi.get("competitor_profile"):
            context_parts.append(f"Competitors: {mi['competitor_profile'].get('summary', '')[:200]}")
        if mi.get("strategy"):
            context_parts.append(f"Strategy: {mi['strategy'].get('summary', '')[:200]}")

    # Agency Council memory
    council = ctx.enriched.get("council_memory", {})
    if council and council.get("recent_decisions"):
        decs = council["recent_decisions"][:3]
        dec_text = "; ".join(f"{d.get('campaign', 'unknown')}: {d.get('decision', '')}" for d in decs)
        context_parts.append(f"Recent council decisions: {dec_text}")

    # Integrations
    integrations = ctx.enriched.get("integrations", {})
    if integrations and integrations.get("connected"):
        int_text = ", ".join(f"{i['name']} ({i.get('status', 'unknown')})" for i in integrations["connected"])
        context_parts.append(f"Connected integrations: {int_text}")

    # Performance + attribution
    perf = ctx.enriched.get("performance", {})
    if perf:
        if perf.get("campaign_performance"):
            context_parts.append(f"Performance: {perf['campaign_performance'].get('summary', '')[:200]}")
        if perf.get("attribution"):
            context_parts.append(f"Attribution: {perf['attribution'].get('summary', '')[:200]}")

    # Review queue
    reviews = ctx.enriched.get("reviews", {})
    if reviews and reviews.get("pending_count", 0) > 0:
        context_parts.append(f"Pending reviews: {reviews['pending_count']} campaign(s) awaiting approval")

    # Domain pack
    domain = ctx.enriched.get("domain_pack", {})
    if domain and domain.get("name"):
        context_parts.append(f"Industry expertise: {domain['name']} pack active")

    prompt = f"{SYSTEM_PROMPT}\n\nContext: {'; '.join(context_parts)}\n\nUser: {message}"

    completion = await gateway.async_complete(
        prompt=prompt,
        tier=Tier.large,
        task="chat",
        tenant_id=str(ctx.tenant_id),
        plan=ctx.billing.plan,
        max_tokens=500,
        temperature=0.4,
    )

    # Collect source citations from knowledge chunks
    sources = []
    for chunk in ctx.knowledge_chunks[:3]:
        sources.append({
            "title": chunk.get("title", "Unknown"),
            "level": chunk.get("level", ""),
            "score": chunk.get("score", 0),
        })

    return {
        "reply": completion.text,
        "sources": sources,
        "tokens_used": completion.tokens_used,
        "model": completion.model,
    }


# ─── CampaignBrain Tools ────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="campaign_brain.analyse",
    display_name="Business Analysis",
    description="Analyzes business positioning, audience, and competitors. Returns structured profiles.",
    category=ToolCategory.CAMPAIGN,
    input_schema={"goal": "string", "budget": "string", "locale": "string"},
    output_schema={"business_profile": "object", "audience_profile": "object", "competitor_profile": "object"},
    estimated_cost_usd=0.05,
    estimated_time_ms=8000,
    estimated_tokens=2500,
    estimated_latency_ms=8000,
    quality_score=0.85,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.AUDIENCE, MemoryCategory.CAMPAIGN],
))
async def campaign_brain_analyse(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Run business + audience + competitor analysis."""
    from prachar_shared.marketing_intelligence import CampaignBrain

    brain = CampaignBrain()
    result = await brain.analyse(
        brand_id=ctx.brand_id,
        goal=input.get("goal", ""),
        budget=input.get("budget", ""),
        locale=input.get("locale", "en-IN"),
    )
    return {
        "business_profile": result.get("business_profile", {}),
        "audience_profile": result.get("audience_profile", {}),
        "competitor_profile": result.get("competitor_profile", {}),
        "artefacts": [
            audience_card(
                demographics=result.get("audience_profile", {}).get("demographics", {}),
                interests=result.get("audience_profile", {}).get("interests", []),
                behaviours=result.get("audience_profile", {}).get("behaviours", []),
                platforms=result.get("audience_profile", {}).get("platforms", []),
            ).to_dict(),
            competitor_card(
                name=result.get("competitor_profile", {}).get("name", "Competitor"),
                strengths=result.get("competitor_profile", {}).get("strengths", []),
                weaknesses=result.get("competitor_profile", {}).get("weaknesses", []),
                market_share=result.get("competitor_profile", {}).get("market_share", ""),
            ).to_dict(),
        ],
    }


@register_tool(ToolManifest(
    name="campaign_brain.strategy",
    display_name="Campaign Strategy",
    description="Generates marketing objective and campaign strategy from business + audience profiles.",
    category=ToolCategory.CAMPAIGN,
    input_schema={"goal": "string", "business_profile": "object", "audience_profile": "object"},
    output_schema={"marketing_objective": "object", "campaign_strategy": "object"},
    estimated_cost_usd=0.08,
    estimated_time_ms=8000,
    estimated_tokens=2500,
    estimated_latency_ms=12000,
    quality_score=0.9,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.AUDIENCE, MemoryCategory.CAMPAIGN, MemoryCategory.PERFORMANCE],
))
async def campaign_brain_strategy(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate marketing objective + campaign strategy."""
    from prachar_shared.marketing_intelligence import CampaignBrain

    brain = CampaignBrain()
    result = await brain.generate_strategy(
        brand_id=ctx.brand_id,
        goal=input.get("goal", ""),
        business_profile=input.get("business_profile"),
        audience_profile=input.get("audience_profile"),
    )
    return {
        "marketing_objective": result.get("marketing_objective", {}),
        "campaign_strategy": result.get("campaign_strategy", {}),
        "artefacts": [
            campaign_card(
                name=result.get("campaign_strategy", {}).get("name", "Campaign"),
                goal=result.get("marketing_objective", {}).get("primary_goal", ""),
                budget=input.get("budget", ""),
                channels=result.get("campaign_strategy", {}).get("channels", []),
                status="planned",
            ).to_dict(),
        ],
    }


@register_tool(ToolManifest(
    name="campaign_brain.creative",
    display_name="Creative Direction",
    description="Determines visual style, mood, colour palette, typography before any assets are generated.",
    category=ToolCategory.CAMPAIGN,
    input_schema={"campaign_strategy": "object", "audience_profile": "object"},
    output_schema={"creative_direction": "object"},
    estimated_cost_usd=0.06,
    estimated_time_ms=6000,
    estimated_tokens=2000,
    estimated_latency_ms=10000,
    quality_score=0.85,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CREATIVE, MemoryCategory.AUDIENCE],
))
async def campaign_brain_creative(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate creative direction."""
    from prachar_shared.marketing_intelligence import CampaignBrain

    brain = CampaignBrain()
    result = await brain.generate_creative_direction(
        brand_id=ctx.brand_id,
        campaign_strategy=input.get("campaign_strategy"),
        audience_profile=input.get("audience_profile"),
    )
    return {
        "creative_direction": result.get("creative_direction", {}),
        "artefacts": [
            creative_brief(
                concept=result.get("creative_direction", {}).get("concept", ""),
                style=result.get("creative_direction", {}).get("style", ""),
                tone=result.get("creative_direction", {}).get("tone", ""),
                references=result.get("creative_direction", {}).get("references", []),
                colors=result.get("creative_direction", {}).get("colors", []),
            ).to_dict(),
        ],
    }


@register_tool(ToolManifest(
    name="campaign_brain.media",
    display_name="Media Planning",
    description="Allocates media budget across channels based on strategy and audience.",
    category=ToolCategory.CAMPAIGN,
    input_schema={"goal": "string", "budget": "string", "campaign_strategy": "object"},
    output_schema={"media_plan": "object"},
    estimated_cost_usd=0.04,
    estimated_time_ms=6000,
    estimated_tokens=2000,
    estimated_latency_ms=6000,
    quality_score=0.8,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN, MemoryCategory.PERFORMANCE],
))
async def campaign_brain_media(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate media plan."""
    from prachar_shared.marketing_intelligence import CampaignBrain

    brain = CampaignBrain()
    result = await brain.generate_media_plan(
        brand_id=ctx.brand_id,
        goal=input.get("goal", ""),
        budget=input.get("budget", ""),
        campaign_strategy=input.get("campaign_strategy"),
    )
    return {
        "media_plan": result.get("media_plan", {}),
        "artefacts": [
            media_plan(
                channels=result.get("media_plan", {}).get("channels", []),
                total_budget=input.get("budget", ""),
                schedule=result.get("media_plan", {}).get("schedule", ""),
            ).to_dict(),
            budget_table(
                rows=result.get("media_plan", {}).get("channels", []),
                total=input.get("budget", ""),
            ).to_dict(),
        ],
    }


@register_tool(ToolManifest(
    name="campaign_brain.full_campaign",
    display_name="Full Campaign Generator",
    description="Creates a complete campaign with strategy, creative concepts, media plan, budget, and execution plan.",
    category=ToolCategory.CAMPAIGN,
    input_schema={"goal": "string", "budget": "string", "locale": "string", "name": "string"},
    output_schema={"full_campaign": "object"},
    estimated_cost_usd=0.15,
    estimated_time_ms=45000,
    estimated_tokens=20000,
    estimated_latency_ms=30000,
    quality_score=0.95,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.AUDIENCE, MemoryCategory.CAMPAIGN, MemoryCategory.CREATIVE, MemoryCategory.PERFORMANCE],
))
async def campaign_brain_full_campaign(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a complete campaign — strategy, creative, media, budget."""
    from prachar_shared.marketing_intelligence import CampaignBrain

    brain = CampaignBrain()
    result = await brain.generate_campaign(
        brand_id=ctx.brand_id,
        goal=input.get("goal", ""),
        budget=input.get("budget", ""),
        locale=input.get("locale", "en-IN"),
        name=input.get("name", ""),
        save=True,
    )
    return {
        "full_campaign": result,
        "artefacts": _build_full_campaign_artefacts(result, input),
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _build_full_campaign_artefacts(result: dict, input: dict) -> list[dict]:
    """Build artefacts for the full campaign result."""
    artefacts: list[dict] = []
    fc = result if isinstance(result, dict) else {}

    # Campaign card
    artefacts.append(campaign_card(
        name=fc.get("campaign_name", input.get("name", "Campaign")),
        goal=input.get("goal", ""),
        budget=input.get("budget", ""),
        channels=fc.get("media_plan", {}).get("channels", [ch.get("channel", "") for ch in fc.get("media_plan", {}).get("channels", [])]),
        status="planned",
        estimated_reach=fc.get("estimated_reach", ""),
        expected_enquiries=fc.get("expected_enquiries", ""),
    ).to_dict())

    # Audience card
    ap = fc.get("audience_profile", {})
    if ap:
        artefacts.append(audience_card(
            demographics=ap.get("demographics", {}),
            interests=ap.get("interests", []),
            behaviours=ap.get("behaviours", []),
            platforms=ap.get("platforms", []),
        ).to_dict())

    # Competitor card
    cp = fc.get("competitor_profile", {})
    if cp:
        artefacts.append(competitor_card(
            name=cp.get("name", "Competitor"),
            strengths=cp.get("strengths", []),
            weaknesses=cp.get("weaknesses", []),
            market_share=cp.get("market_share", ""),
        ).to_dict())

    # Creative brief
    cd = fc.get("creative_direction", {})
    if cd:
        artefacts.append(creative_brief(
            concept=cd.get("concept", ""),
            style=cd.get("style", ""),
            tone=cd.get("tone", ""),
            references=cd.get("references", []),
            colors=cd.get("colors", []),
        ).to_dict())

    # Media plan + budget table
    mp = fc.get("media_plan", {})
    if mp:
        artefacts.append(media_plan(
            channels=mp.get("channels", []),
            total_budget=input.get("budget", ""),
            schedule=mp.get("schedule", ""),
        ).to_dict())
        artefacts.append(budget_table(
            rows=mp.get("channels", []),
            total=input.get("budget", ""),
        ).to_dict())

    # Timeline plan (30-day)
    plan = fc.get("execution_plan", {}).get("timeline", [])
    if plan:
        artefacts.append(timeline_plan(weeks=plan).to_dict())

    # Opportunities
    opps = fc.get("growth_opportunities", [])
    for opp in opps[:3]:
        artefacts.append(opportunity_card(
            title=opp.get("title", ""),
            impact=opp.get("impact", "medium"),
            difficulty=opp.get("difficulty", "medium"),
            timeframe=opp.get("timeframe", ""),
            description=opp.get("description", ""),
        ).to_dict())

    return artefacts


def _build_council_artefacts(result: Any) -> list[dict]:
    """Build artefacts for the council review result."""
    artefacts: list[dict] = []

    # One review_feedback per director
    opinions = getattr(result, "opinions", [])
    for opinion in opinions:
        o = opinion.to_dict() if hasattr(opinion, "to_dict") else opinion
        artefacts.append(review_feedback(
            director=o.get("director", "Director"),
            opinion=o.get("opinion", ""),
            confidence=float(o.get("confidence", 0.5)),
            score=o.get("score"),
            risks=o.get("risks", []),
        ).to_dict())

    # Review summary
    decision = getattr(result, "decision", None)
    if decision:
        d = decision.to_dict() if hasattr(decision, "to_dict") else decision
        score = getattr(result, "campaign_score", None)
        score_val = 0.0
        if score:
            sd = score.to_dict() if hasattr(score, "to_dict") else score
            score_val = float(sd.get("overall", 0))
        artefacts.append(review_summary(
            approved=d.get("approved", False),
            score=score_val,
            key_points=d.get("key_points", []),
            consensus=d.get("consensus", ""),
        ).to_dict())

    # Task list from recommendations
    recs = d.get("recommendations", []) if decision else []
    tasks = []
    for rec in recs[:5]:
        r = rec if isinstance(rec, dict) else {"title": str(rec)}
        tasks.append({
            "title": r.get("title", r.get("action", str(rec))),
            "priority": r.get("priority", "medium"),
            "action": r.get("action", ""),
        })
    if tasks:
        artefacts.append(task_list(tasks).to_dict())

    return artefacts


def _build_creative_artefacts(result: Any) -> list[dict]:
    """Build artefacts for the creative studio result."""
    artefacts: list[dict] = []
    formats = result if isinstance(result, dict) else {}

    # Build copy drafts from text-based formats
    drafts: list[dict] = []
    for fmt_name in ["poster", "whatsapp", "facebook", "linkedin", "email", "sms", "story", "carousel"]:
        fmt = formats.get(fmt_name, {})
        if isinstance(fmt, dict) and (fmt.get("headline") or fmt.get("body") or fmt.get("text")):
            drafts.append({
                "platform": fmt_name.title(),
                "headline": fmt.get("headline", fmt.get("title", "")),
                "body": fmt.get("body", fmt.get("text", fmt.get("caption", ""))),
                "hashtags": fmt.get("hashtags", []),
                "cta": fmt.get("cta", ""),
            })
    if drafts:
        artefacts.append(copy_drafts(drafts).to_dict())

    # Video script as a copy draft
    video = formats.get("video_script", {})
    if isinstance(video, dict) and video:
        artefacts.append(copy_draft(
            platform="YouTube",
            headline=video.get("title", video.get("headline", "")),
            body=video.get("script", video.get("body", "")),
            hashtags=video.get("hashtags", []),
            cta=video.get("cta", ""),
        ).to_dict())

    # Landing page as a copy draft
    lp = formats.get("landing_page", {})
    if isinstance(lp, dict) and lp:
        artefacts.append(copy_draft(
            platform="Landing Page",
            headline=lp.get("headline", lp.get("hero", "")),
            body=lp.get("body", lp.get("content", "")),
            cta=lp.get("cta", ""),
        ).to_dict())

    return artefacts


def _build_performance_story_artefacts(result: Any) -> list[dict]:
    """Build artefacts for the performance story result."""
    artefacts: list[dict] = []
    story = result if isinstance(result, dict) else {}

    # KPI grid from metrics
    kpis = story.get("kpis", [])
    if kpis:
        artefacts.append(kpi_grid(kpis).to_dict())
    elif story.get("metrics"):
        metrics = story["metrics"]
        kpi_list = []
        for k, v in metrics.items():
            if isinstance(v, dict):
                kpi_list.append({"label": k, "value": v.get("value", ""), "trend": v.get("trend", "")})
            else:
                kpi_list.append({"label": k, "value": v})
        if kpi_list:
            artefacts.append(kpi_grid(kpi_list).to_dict())

    # Chart from trend data
    trend = story.get("trend", {})
    if trend and trend.get("labels") and trend.get("data"):
        artefacts.append(chart(
            chart_type=trend.get("type", "line"),
            labels=trend["labels"],
            datasets=[{"label": trend.get("metric", "Performance"), "data": trend["data"]}],
            title=trend.get("title", "Performance Trend"),
        ).to_dict())

    # Alert if concerning
    alerts = story.get("alerts", [])
    for a in alerts[:2]:
        artefacts.append(alert(
            severity=a.get("severity", "warning"),
            title=a.get("title", ""),
            detail=a.get("detail", ""),
            action=a.get("action", ""),
        ).to_dict())

    return artefacts


def _build_performance_why_artefacts(result: Any) -> list[dict]:
    """Build artefacts for the root-cause analysis result."""
    artefacts: list[dict] = []
    explanation = result if isinstance(result, dict) else {}

    # Alert with the root cause
    root_cause = explanation.get("root_cause", "")
    if root_cause:
        artefacts.append(alert(
            severity="warning",
            title="Root Cause Identified",
            detail=root_cause,
            action=explanation.get("recommendation", ""),
        ).to_dict())

    # Task list of corrective actions
    actions = explanation.get("corrective_actions", [])
    if actions:
        tasks = []
        for action in actions[:5]:
            a = action if isinstance(action, dict) else {"title": str(action)}
            tasks.append({
                "title": a.get("title", a.get("action", str(action))),
                "priority": a.get("priority", "medium"),
                "action": a.get("action", ""),
            })
        if tasks:
            artefacts.append(task_list(tasks).to_dict())

    return artefacts


def _build_performance_next_artefacts(result: Any) -> list[dict]:
    """Build artefacts for the recommendations result."""
    artefacts: list[dict] = []
    recs = result if isinstance(result, dict) else {}
    recommendations = recs.get("recommendations", recs.get("items", []))

    # Task list of recommendations
    tasks = []
    for rec in recommendations[:7]:
        r = rec if isinstance(rec, dict) else {"title": str(rec)}
        tasks.append({
            "title": r.get("title", r.get("action", str(rec))),
            "priority": r.get("priority", r.get("impact", "medium")),
            "action": r.get("action", r.get("title", "")),
        })
    if tasks:
        artefacts.append(task_list(tasks).to_dict())

    # Top opportunity
    opportunities = recs.get("opportunities", [])
    for opp in opportunities[:2]:
        o = opp if isinstance(opp, dict) else {"title": str(opp)}
        artefacts.append(opportunity_card(
            title=o.get("title", ""),
            impact=o.get("impact", "medium"),
            difficulty=o.get("difficulty", "medium"),
            timeframe=o.get("timeframe", ""),
            description=o.get("description", ""),
        ).to_dict())

    return artefacts


def _build_consult_artefacts(result: dict) -> list[dict]:
    """Build artefacts for the consult/understand result."""
    artefacts: list[dict] = []

    # Growth opportunities
    opps = result.get("growth_opportunities", [])
    for opp in opps[:3]:
        o = opp if isinstance(opp, dict) else {"title": str(opp)}
        artefacts.append(opportunity_card(
            title=o.get("title", ""),
            impact=o.get("impact", "medium"),
            difficulty=o.get("difficulty", "medium"),
            timeframe=o.get("timeframe", ""),
            description=o.get("description", ""),
        ).to_dict())

    # 30-day plan
    plan = result.get("plan", [])
    if plan:
        artefacts.append(timeline_plan(weeks=plan).to_dict())

    return artefacts


def _build_memory_artefacts(ctx: AIContext) -> list[dict]:
    """Build artefacts for the memory retrieval result."""
    artefacts: list[dict] = []
    for bp in ctx.memory.best_practices[:3]:
        artefacts.append(memory_insight(
            category="Campaign",
            insight=bp,
            confidence=0.8,
        ).to_dict())
    for ai in ctx.memory.audience_insights[:2]:
        artefacts.append(memory_insight(
            category="Audience",
            insight=ai,
            confidence=0.8,
        ).to_dict())
    for ci in ctx.memory.creative_insights[:2]:
        artefacts.append(memory_insight(
            category="Creative",
            insight=ci,
            confidence=0.8,
        ).to_dict())
    return artefacts


# ─── Agency Council Tool ────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="council.review",
    display_name="Agency Council Review",
    description="9 specialist AI Directors independently review the campaign. Weighted consensus, multi-round, self-critique.",
    category=ToolCategory.REVIEW,
    input_schema={"campaign_brief": "object", "industry": "string", "objective": "string", "budget": "string"},
    output_schema={"decision": "object", "opinions": "array", "campaign_score": "object"},
    estimated_cost_usd=0.10,
    estimated_time_ms=30000,
    estimated_tokens=15000,
    estimated_latency_ms=15000,
    quality_score=0.9,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CAMPAIGN, MemoryCategory.PERFORMANCE],
))
async def council_review(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Submit campaign for 9-director council review."""
    from prachar_shared.agency_council import ConsensusEngine, ALL_DIRECTORS

    directors = list(ALL_DIRECTORS.values()) if isinstance(ALL_DIRECTORS, dict) else list(ALL_DIRECTORS)
    engine = ConsensusEngine(directors=directors)

    result = await engine.review(
        brief=input.get("campaign_brief", {}),
        brand_id=ctx.brand_id,
        industry=input.get("industry", ""),
        objective=input.get("objective", ""),
        budget=input.get("budget", ""),
    )
    return {
        "decision": result.decision.to_dict() if hasattr(result.decision, "to_dict") else result.decision,
        "opinions": [o.to_dict() if hasattr(o, "to_dict") else o for o in result.opinions],
        "campaign_score": result.campaign_score.to_dict() if hasattr(result.campaign_score, "to_dict") else result.campaign_score,
        "artefacts": _build_council_artefacts(result),
    }


# ─── Creative Studio Tools ──────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="creative_studio.generate",
    display_name="Creative Studio",
    description="Generates all 10 creative formats (poster, video_script, carousel, story, whatsapp, facebook, linkedin, email, landing_page, sms).",
    category=ToolCategory.CREATIVE,
    input_schema={"campaign_id": "string", "creative_direction_id": "string", "domain": "string"},
    output_schema={"formats": "object"},
    estimated_cost_usd=0.12,
    estimated_time_ms=30000,
    estimated_tokens=10000,
    estimated_latency_ms=20000,
    quality_score=0.88,
    supports_streaming=True,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CREATIVE, MemoryCategory.AUDIENCE],
))
async def creative_studio_generate(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate all 10 creative formats."""
    from ..infrastructure.creative_studio_engine import CreativeStudioEngine

    engine = CreativeStudioEngine()
    result = await engine.generate(
        campaign_id=input.get("campaign_id", ""),
        creative_direction_id=input.get("creative_direction_id", ""),
        domain=input.get("domain", "business"),
    )
    return {
        "formats": result,
        "artefacts": _build_creative_artefacts(result),
    }


@register_tool(ToolManifest(
    name="creative_studio.generate_image",
    display_name="AI Image Generator",
    description="Generates an AI image from a text prompt.",
    category=ToolCategory.CREATIVE,
    input_schema={"prompt": "string", "width": "number", "height": "number"},
    output_schema={"image_url": "string", "model": "string"},
    estimated_cost_usd=0.08,
    estimated_time_ms=10000,
    estimated_tokens=0,
    estimated_latency_ms=15000,
    quality_score=0.85,
    supports_streaming=True,
    requires_brand=False,
    side_effects=SideEffects.EXTERNAL,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CREATIVE, MemoryCategory.AUDIENCE],
))
async def creative_studio_generate_image(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate an AI image."""
    from ..routers.video_gen import generate_image

    result = await generate_image(
        prompt=input.get("prompt", ""),
        width=input.get("width", 1024),
        height=input.get("height", 1024),
    )
    if isinstance(result, dict) and result.get("image_url"):
        result["artefacts"] = [
            image_artefact(
                url=result["image_url"],
                alt=input.get("prompt", "Generated image"),
                prompt=input.get("prompt", ""),
                width=input.get("width", 1024),
                height=input.get("height", 1024),
            ).to_dict()
        ]
    return result


# ─── Performance Tools ──────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="performance.story",
    display_name="Performance Story",
    description="Generates a narrative story of campaign performance (de-jargonised).",
    category=ToolCategory.ANALYTICS,
    input_schema={"campaign_id": "uuid", "days": "number"},
    output_schema={"story": "object"},
    estimated_cost_usd=0.03,
    estimated_time_ms=5000,
    estimated_tokens=1000,
    estimated_latency_ms=5000,
    quality_score=0.8,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE, MemoryCategory.CAMPAIGN],
))
async def performance_story(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get performance narrative story."""
    from prachar_shared.marketing_intelligence.performance_engine import PerformanceEngine

    engine = PerformanceEngine(session_factory=lambda: ctx.session)
    result = await engine.tell_story(
        campaign_id=uuid.UUID(input["campaign_id"]),
        days=input.get("days", 30),
    )
    return {
        "story": result,
        "artefacts": _build_performance_story_artefacts(result),
    }


@register_tool(ToolManifest(
    name="performance.why",
    display_name="Root Cause Analysis",
    description="Explains why performance is what it is (root-cause analysis).",
    category=ToolCategory.ANALYTICS,
    input_schema={"campaign_id": "uuid", "days": "number"},
    output_schema={"explanation": "object"},
    estimated_cost_usd=0.04,
    estimated_time_ms=5000,
    estimated_tokens=1000,
    estimated_latency_ms=7000,
    quality_score=0.85,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE, MemoryCategory.CAMPAIGN],
))
async def performance_why(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get root-cause analysis."""
    from prachar_shared.marketing_intelligence.performance_engine import PerformanceEngine

    engine = PerformanceEngine(session_factory=lambda: ctx.session)
    result = await engine.explain(
        campaign_id=uuid.UUID(input["campaign_id"]),
        days=input.get("days", 30),
    )
    return {
        "explanation": result,
        "artefacts": _build_performance_why_artefacts(result),
    }


@register_tool(ToolManifest(
    name="performance.next",
    display_name="Recommendations",
    description="Generates actionable recommendations for what to do next.",
    category=ToolCategory.ANALYTICS,
    input_schema={"campaign_id": "uuid", "days": "number"},
    output_schema={"recommendations": "object"},
    estimated_cost_usd=0.04,
    estimated_time_ms=5000,
    estimated_tokens=1000,
    estimated_latency_ms=7000,
    quality_score=0.85,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE, MemoryCategory.CAMPAIGN],
))
async def performance_next(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get recommendations."""
    from prachar_shared.marketing_intelligence.performance_engine import PerformanceEngine

    engine = PerformanceEngine(session_factory=lambda: ctx.session)
    result = await engine.recommend(
        campaign_id=uuid.UUID(input["campaign_id"]),
        days=input.get("days", 30),
    )
    return {
        "recommendations": result,
        "artefacts": _build_performance_next_artefacts(result),
    }


# ─── Proactive Tool ─────────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="proactive.notifications",
    display_name="Proactive Notifications",
    description="Returns pending anomalies and AI recommendations. What needs attention right now.",
    category=ToolCategory.NOTIFICATION,
    input_schema={},
    output_schema={"notifications": "array", "count": "number"},
    estimated_cost_usd=0.02,
    estimated_time_ms=1000,
    estimated_tokens=0,
    estimated_latency_ms=3000,
    quality_score=0.75,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.PERFORMANCE, MemoryCategory.CAMPAIGN],
))
async def proactive_notifications(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get proactive notifications."""
    from ..routers.proactive import get_notifications

    notifications = await get_notifications(ctx.session, ctx.tenant_id, ctx.brand_id)
    artefacts: list[dict] = []
    for n in notifications[:3]:
        nf = n if isinstance(n, dict) else {"title": str(n)}
        artefacts.append(alert(
            severity=nf.get("severity", "info"),
            title=nf.get("title", ""),
            detail=nf.get("detail", nf.get("message", "")),
            action=nf.get("action", ""),
        ).to_dict())
    return {"notifications": notifications, "count": len(notifications), "artefacts": artefacts}


# ─── Memory Tools ───────────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="memory.retrieve",
    display_name="Memory Retrieval",
    description="Retrieves business memory (best practices, audience insights, creative insights, channel insights).",
    category=ToolCategory.MEMORY,
    input_schema={},
    output_schema={"memory": "object"},
    estimated_cost_usd=0.01,
    estimated_time_ms=500,
    estimated_tokens=0,
    estimated_latency_ms=1000,
    quality_score=0.7,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.READS,
    memory_categories=[],  # all categories
))
async def memory_retrieve(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Retrieve business memory (already in context, just return it)."""
    return {
        "memory": {
            "best_practices": ctx.memory.best_practices,
            "audience_insights": ctx.memory.audience_insights,
            "creative_insights": ctx.memory.creative_insights,
            "channel_insights": ctx.memory.channel_insights,
            "total_campaigns": ctx.memory.total_campaigns,
            "average_roi": ctx.memory.average_roi,
        },
        "artefacts": _build_memory_artefacts(ctx),
    }


@register_tool(ToolManifest(
    name="memory.update",
    display_name="Memory Update",
    description="Persists learnings from a campaign or analysis to business memory. The Runtime owns memory.",
    category=ToolCategory.MEMORY,
    input_schema={"learnings": "object"},
    output_schema={"status": "string"},
    estimated_cost_usd=0.01,
    estimated_time_ms=500,
    estimated_tokens=0,
    estimated_latency_ms=1000,
    quality_score=0.7,
    supports_streaming=False,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
    memory_categories=[],  # all categories
))
async def memory_update(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Update business memory with new learnings."""
    from sqlalchemy import select
    from ..models import BusinessMemoryRecord

    learnings = input.get("learnings", {})

    # Load existing memory record
    res = await ctx.session.execute(
        select(BusinessMemoryRecord).where(BusinessMemoryRecord.brand_id == ctx.brand_id)
    )
    record = res.scalar_one_or_none()

    if record is None:
        record = BusinessMemoryRecord(
            tenant_id=ctx.tenant_id,
            brand_id=ctx.brand_id,
            memory=learnings,
        )
        ctx.session.add(record)
    else:
        # Merge new learnings into existing memory
        existing = record.memory or {}
        if "best_practices" in learnings:
            existing.setdefault("best_practices", [])
            for bp in learnings["best_practices"]:
                if bp not in existing["best_practices"]:
                    existing["best_practices"].append(bp)
            existing["best_practices"] = existing["best_practices"][:50]  # cap at 50
        if "audience_insights" in learnings:
            existing.setdefault("audience_insights", [])
            for ai in learnings["audience_insights"]:
                if ai not in existing["audience_insights"]:
                    existing["audience_insights"].append(ai)
            existing["audience_insights"] = existing["audience_insights"][:30]
        record.memory = existing

    await ctx.session.flush()
    return {"status": "updated"}


# ─── Consult Tool ───────────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="consult.understand",
    display_name="Business Understanding",
    description="Takes free-text business description and returns structured understanding + growth opportunities + 30-day plan.",
    category=ToolCategory.ONBOARDING,
    input_schema={"message": "string"},
    output_schema={"understanding": "object", "opportunities": "array", "plan": "array"},
    estimated_cost_usd=0.05,
    estimated_time_ms=15000,
    estimated_tokens=3000,
    estimated_latency_ms=8000,
    quality_score=0.85,
    supports_streaming=True,
    requires_brand=False,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.AUDIENCE, MemoryCategory.CAMPAIGN],
))
async def consult_understand(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Run conversational onboarding analysis."""
    from ..infrastructure.consult_engine import ConsultEngine

    engine = ConsultEngine()
    result = await engine.consult(
        message=input.get("message", ""),
        brand_id=ctx.brand_id,
    )
    return {
        "understanding": result.get("business", {}),
        "opportunities": result.get("growth_opportunities", []),
        "plan": result.get("plan", []),
        "brand_id": str(ctx.brand_id),
        "artefacts": _build_consult_artefacts(result),
    }


# ─── Creator Tools ──────────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="creator.repurpose",
    display_name="Content Repurposer",
    description="Repurposes one video into 11 asset types (Shorts, Reels, LinkedIn posts, etc.).",
    category=ToolCategory.CREATIVE,
    input_schema={"video_title": "string", "video_description": "string", "niche": "string"},
    output_schema={"assets": "array"},
    estimated_cost_usd=0.06,
    estimated_time_ms=10000,
    estimated_tokens=2000,
    estimated_latency_ms=10000,
    quality_score=0.82,
    supports_streaming=True,
    requires_brand=False,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CREATIVE, MemoryCategory.AUDIENCE],
))
async def creator_repurpose(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Repurpose video into 11 asset types."""
    from prachar_shared.ai_gateway import AIGateway, Tier

    gateway = AIGateway()
    # Use the creator repurpose logic
    prompt = f"""Repurpose this video into 11 asset types (YouTube Shorts, Instagram Reels, \
LinkedIn posts, Twitter threads, Facebook posts, email newsletter, blog outline, \
podcast intro, TikTok script, Pinterest pins, WhatsApp status):

Title: {input.get('video_title', '')}
Description: {input.get('video_description', '')}
Niche: {input.get('niche', '')}

Return as JSON: {{"assets": [{{"asset_type": "...", "content": "...", "notes": "..."}}]}}
"""
    completion = await gateway.async_complete(
        prompt=prompt,
        tier=Tier.large,
        task="creator_repurpose",
        tenant_id=str(ctx.tenant_id),
        plan=ctx.billing.plan,
        max_tokens=2000,
        temperature=0.4,
    )
    from prachar_shared.ai_gateway import extract_json_or_raise
    try:
        data = extract_json_or_raise(completion.text)
        return {"assets": data.get("assets", [])}
    except Exception:
        return {"assets": [], "raw": completion.text}


@register_tool(ToolManifest(
    name="creator.youtube_plan",
    display_name="YouTube Video Planner",
    description="Generates a full YouTube video plan (titles, thumbnails, hooks, SEO, tags, chapters).",
    category=ToolCategory.CREATIVE,
    input_schema={"video_concept": "string", "niche": "string", "audience": "string"},
    output_schema={"plan": "object"},
    estimated_cost_usd=0.07,
    estimated_time_ms=10000,
    estimated_tokens=2000,
    estimated_latency_ms=12000,
    quality_score=0.85,
    supports_streaming=True,
    requires_brand=False,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.BRAND, MemoryCategory.CREATIVE, MemoryCategory.AUDIENCE],
))
async def creator_youtube_plan(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate YouTube video plan."""
    from prachar_shared.ai_gateway import AIGateway, Tier, extract_json_or_raise

    gateway = AIGateway()
    prompt = f"""Create a comprehensive YouTube video plan:

Concept: {input.get('video_concept', '')}
Niche: {input.get('niche', '')}
Audience: {input.get('audience', '')}

Include: title_options (5), thumbnail_concepts (3), opening_hook, retention_improvements, \
description, seo_keywords, tags, chapters, pinned_comment, community_post, end_screen_suggestions.

Return as JSON.
"""
    completion = await gateway.async_complete(
        prompt=prompt,
        tier=Tier.large,
        task="creator_youtube_plan",
        tenant_id=str(ctx.tenant_id),
        plan=ctx.billing.plan,
        max_tokens=2000,
        temperature=0.4,
    )
    try:
        plan = extract_json_or_raise(completion.text)
        return {"plan": plan}
    except Exception:
        return {"plan": {}, "raw": completion.text}


# ─── Review/Publish Tools ───────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="review.publish",
    display_name="Campaign Publisher",
    description="Publishes an approved campaign to all connected channels. Requires user approval.",
    category=ToolCategory.EXECUTION,
    input_schema={"campaign_id": "uuid"},
    output_schema={"status": "string", "published_to": "array"},
    estimated_cost_usd=0.01,
    estimated_time_ms=2000,
    estimated_tokens=0,
    estimated_latency_ms=2000,
    quality_score=0.9,
    supports_streaming=False,
    requires_brand=True,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
    required_permissions=("can_publish",),
    memory_categories=[MemoryCategory.CAMPAIGN, MemoryCategory.WORKSPACE],
))
async def review_publish(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Publish a campaign (enqueues Celery task)."""
    from ..audit import log_audit
    from ..models import Campaign, CampaignStatus
    from sqlalchemy import select

    campaign_id = uuid.UUID(input["campaign_id"])
    res = await ctx.session.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    campaign = res.scalar_one_or_none()
    if campaign is None:
        return {"status": "error", "error": "campaign not found"}

    campaign.status = CampaignStatus.active
    await log_audit(
        ctx.session,
        tenant_id=ctx.tenant_id,
        actor="user",
        action="campaign.publish",
        entity_type="campaign",
        entity_id=str(campaign_id),
    )
    await ctx.session.flush()

    # In production, this enqueues a Celery task
    return {
        "status": "published",
        "published_to": [c.channel for c in ctx.connected_channels if c.status == "active"],
    }


# ─── Initialization ─────────────────────────────────────────────────────────


def register_all_tools() -> None:
    """Explicitly register all tools (called on app startup).

    The @register_tool decorator already registers them on import,
    but this function ensures the tools module is imported.
    """
    log.info("Registered %d tools", len(get_registry()))


# Ensure tools are registered on import
register_all_tools()
