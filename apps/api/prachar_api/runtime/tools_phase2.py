"""Phase 2 Tool Registrations — new orb tools for the CURV AI runtime.

Registers additional tools that the orb can call, building on the existing
tool set in ``tools.py``. Each tool follows the same manifest + decorator
pattern so the Planner can discover and reason about them uniformly.

Constitution Rule 6: Every tool must expose a Tool Manifest.
Constitution Rule 7: The Planner reasons from manifests. Never hard-code.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select, func

from .registry import (
    SideEffects,
    ToolCategory,
    ToolManifest,
    register_tool,
)
from .context import AIContext

log = logging.getLogger("prachar.runtime.tools_phase2")


# ─── knowledge.search — Search the Business Knowledge Hub ───────────────────


@register_tool(ToolManifest(
    name="knowledge.search",
    display_name="Knowledge Hub Search",
    description=(
        "Search the Business Knowledge Hub using semantic similarity. "
        "Returns the top matching chunks with source title, level, "
        "content snippet, and relevance score."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={"query": "string", "level": "string (optional)"},
    output_schema={"results": "array", "count": "number"},
    estimated_cost_usd=0.01,
    estimated_time_ms=2000,
    estimated_tokens=300,
    estimated_latency_ms=2000,
    quality_score=0.85,
    requires_brand=False,
    side_effects=SideEffects.READS,
))
async def knowledge_search(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Search knowledge chunks via cosine similarity over embeddings."""
    try:
        from prachar_shared.knowledge import EmbeddingGenerator, cosine_similarity
        from ..models import KnowledgeChunkRecord, KnowledgeEmbeddingRecord, KnowledgeSourceRecord

        query = (input.get("query") or "").strip()
        if not query:
            return {"results": [], "count": 0}

        level_filter = (input.get("level") or "").strip().lower() or None
        session = ctx.session
        if session is None:
            return {"error": "no database session available"}

        # Generate the query embedding.
        gen = EmbeddingGenerator()
        query_vec = await gen.embed_async(query) if hasattr(gen, "embed_async") else gen.embed(query)

        # Fetch embedded chunks (optionally filtered by level via join to source).
        stmt = (
            select(
                KnowledgeEmbeddingRecord,
                KnowledgeChunkRecord,
                KnowledgeSourceRecord,
            )
            .join(
                KnowledgeChunkRecord,
                KnowledgeChunkRecord.id == KnowledgeEmbeddingRecord.chunk_id,
            )
            .join(
                KnowledgeSourceRecord,
                KnowledgeSourceRecord.id == KnowledgeEmbeddingRecord.source_id,
            )
            .where(KnowledgeEmbeddingRecord.embedding.isnot(None))
        )
        if level_filter:
            stmt = stmt.where(KnowledgeSourceRecord.level == level_filter)

        result = await session.execute(stmt)
        rows = result.all()

        scored: list[tuple[float, dict[str, Any]]] = []
        for emb, chunk, source in rows:
            vec = emb.embedding
            if not vec:
                continue
            score = cosine_similarity(query_vec, vec)
            snippet = (chunk.content or "")[:300]
            scored.append((score, {
                "source_title": source.title,
                "level": source.level,
                "content_snippet": snippet,
                "score": round(score, 4),
            }))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [item for _, item in scored[:5]]
        return {"results": top, "count": len(top)}
    except Exception as exc:  # noqa: BLE001
        log.exception("knowledge.search failed: %s", exc)
        return {"error": f"knowledge search failed: {exc}", "results": [], "count": 0}


# ─── integrations.list — List connected integrations ───────────────────────


@register_tool(ToolManifest(
    name="integrations.list",
    display_name="Connected Integrations",
    description=(
        "List all connected integrations from the Business Knowledge Hub. "
        "Returns integration name, status, source count, and last sync time."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={},
    output_schema={"integrations": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=100,
    estimated_latency_ms=500,
    quality_score=0.9,
    side_effects=SideEffects.READS,
))
async def integrations_list(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """List integrations from knowledge_sources where source_type=integration."""
    try:
        from ..models import KnowledgeSourceRecord

        session = ctx.session
        if session is None:
            return {"error": "no database session available"}

        stmt = (
            select(
                KnowledgeSourceRecord.integration_name,
                KnowledgeSourceRecord.status,
                func.count(KnowledgeSourceRecord.id).label("source_count"),
                func.max(KnowledgeSourceRecord.processed_at).label("last_sync"),
            )
            .where(
                KnowledgeSourceRecord.source_type == "integration",
                KnowledgeSourceRecord.status == "ready",
            )
            .group_by(
                KnowledgeSourceRecord.integration_name,
                KnowledgeSourceRecord.status,
            )
        )
        result = await session.execute(stmt)
        rows = result.all()

        integrations = [
            {
                "name": row.integration_name or "unknown",
                "status": row.status,
                "source_count": row.source_count,
                "last_sync": row.last_sync.isoformat() if row.last_sync else None,
            }
            for row in rows
        ]
        return {"integrations": integrations, "count": len(integrations)}
    except Exception as exc:  # noqa: BLE001
        log.exception("integrations.list failed: %s", exc)
        return {"error": f"integrations list failed: {exc}", "integrations": [], "count": 0}


# ─── video_gen.generate — Generate a short promotional video ───────────────


@register_tool(ToolManifest(
    name="video_gen.generate",
    display_name="Video Generation",
    description=(
        "Generate a short promotional video from a text prompt. "
        "Uses Gemini Veo (primary) with fal.ai fallback. "
        "Requires approval — incurs GPU cost."
    ),
    category=ToolCategory.CREATIVE,
    input_schema={
        "prompt": "string",
        "duration": "number (optional, default 5)",
        "aspect_ratio": "string (optional, default 16:9)",
    },
    output_schema={"video_url": "string", "status": "string", "duration": "number"},
    estimated_cost_usd=0.15,
    estimated_time_ms=30000,
    estimated_tokens=0,
    estimated_latency_ms=30000,
    quality_score=0.8,
    requires_user_approval=True,
    side_effects=SideEffects.WRITES,
))
async def video_gen_generate(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a promotional video via the video generation pipeline."""
    try:
        from ..routers.video_gen import (
            VEO_MODELS,
            _get_gemini_api_key,
            _call_gemini_veo,
            _call_fal_video,
            _get_modal_video_url,
            _call_modal_video,
            VideoGenRequest,
        )
        from prachar_shared.config import get_settings

        prompt = (input.get("prompt") or "").strip()
        if not prompt:
            return {"error": "prompt is required", "video_url": "", "status": "failed", "duration": 0}

        duration = input.get("duration", 5)
        try:
            duration_sec = int(duration)
        except (TypeError, ValueError):
            duration_sec = 5
        duration_sec = max(5, min(15, duration_sec))

        aspect_ratio = (input.get("aspect_ratio") or "16:9").strip() or "16:9"

        req = VideoGenRequest(
            prompt=prompt,
            quality="lite",
            duration=str(duration_sec),
            aspect_ratio=aspect_ratio,
            video_type="landscape",
        )

        # Gemini Veo (primary)
        gemini_key = _get_gemini_api_key()
        if gemini_key:
            try:
                log.info("video_gen.generate: using Gemini Veo lite")
                resp = await _call_gemini_veo(
                    api_key=gemini_key,
                    prompt=prompt,
                    quality="lite",
                    duration_sec=duration_sec,
                    aspect_ratio=aspect_ratio,
                    with_audio=True,
                )
                return {
                    "video_url": resp.video_url,
                    "status": "completed",
                    "duration": duration_sec,
                }
            except Exception as exc:  # noqa: BLE001
                log.error("video_gen.generate Gemini failed: %s", str(exc)[:300])

        # fal.ai fallback
        fal_key = get_settings().fal_key.strip()
        if fal_key:
            try:
                log.info("video_gen.generate: falling back to fal.ai")
                req_copy = req.model_copy()
                req_copy.model = "ltx"
                resp = await _call_fal_video(fal_key, req_copy, prompt, aspect_ratio)
                return {
                    "video_url": resp.video_url,
                    "status": "completed",
                    "duration": duration_sec,
                }
            except Exception as exc:  # noqa: BLE001
                log.error("video_gen.generate fal.ai failed: %s", str(exc)[:300])

        # Modal preview last resort
        modal_url = _get_modal_video_url()
        if modal_url:
            try:
                log.info("video_gen.generate: last resort Modal preview")
                resp = await _call_modal_video(modal_url, prompt, req)
                return {
                    "video_url": resp.video_url,
                    "status": "completed",
                    "duration": duration_sec,
                }
            except Exception as exc:  # noqa: BLE001
                log.error("video_gen.generate Modal failed: %s", str(exc)[:300])

        return {
            "error": "no video generation service configured",
            "video_url": "",
            "status": "failed",
            "duration": duration_sec,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("video_gen.generate failed: %s", exc)
        return {
            "error": f"video generation failed: {exc}",
            "video_url": "",
            "status": "failed",
            "duration": 0,
        }


# ─── audit.run — Run a brand audit ─────────────────────────────────────────


@register_tool(ToolManifest(
    name="audit.run",
    display_name="Brand Audit",
    description=(
        "Create and enqueue a brand audit job. Returns the audit ID and "
        "initial visibility score once the job is created."
    ),
    category=ToolCategory.ANALYSIS,
    input_schema={"website": "string (optional)"},
    output_schema={"audit_id": "string", "visibility_score": "number", "findings": "array"},
    estimated_cost_usd=0.05,
    estimated_time_ms=5000,
    estimated_tokens=500,
    estimated_latency_ms=5000,
    quality_score=0.85,
    requires_brand=True,
    side_effects=SideEffects.WRITES,
))
async def audit_run(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Create an AuditJob and enqueue the audit pipeline."""
    try:
        from ..models import AuditJob
        from ..routers.audits import _enqueue_audit_job

        session = ctx.session
        if session is None:
            return {"error": "no database session available"}

        website = (input.get("website") or "").strip()
        if not website and ctx.brand:
            website = ctx.brand.website or ""

        job = AuditJob(input=website or str(ctx.brand_id), status="pending")
        if website:
            # Extract domain for the domain column.
            domain = website.replace("https://", "").replace("http://", "").split("/")[0]
            job.domain = domain
        session.add(job)
        await session.commit()

        job_id_str = str(job.id)
        _enqueue_audit_job(job_id_str, job.input)

        return {
            "audit_id": job_id_str,
            "visibility_score": 0.0,
            "findings": [],
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("audit.run failed: %s", exc)
        return {
            "error": f"audit run failed: {exc}",
            "audit_id": "",
            "visibility_score": 0.0,
            "findings": [],
        }


# ─── review.list — List pending campaign reviews ──────────────────────────


@register_tool(ToolManifest(
    name="review.list",
    display_name="Pending Campaign Reviews",
    description=(
        "List campaigns with status in_review or changes_requested. "
        "Use to surface campaigns awaiting user action."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={},
    output_schema={"pending": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=100,
    estimated_latency_ms=500,
    quality_score=0.9,
    side_effects=SideEffects.READS,
))
async def review_list(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Query campaigns in review or with changes requested."""
    try:
        from ..models import Campaign
        from ..models.enums import CampaignStatus

        session = ctx.session
        if session is None:
            return {"error": "no database session available"}

        stmt = (
            select(Campaign)
            .where(
                Campaign.brand_id == ctx.brand_id,
                Campaign.status.in_([
                    CampaignStatus.in_review,
                    CampaignStatus.changes_requested,
                ]),
            )
            .order_by(Campaign.created_at.desc())
        )
        result = await session.execute(stmt)
        campaigns = result.scalars().all()

        pending = [
            {
                "id": str(c.id),
                "network": c.network,
                "objective": c.objective,
                "status": c.status,
                "budget_daily": c.budget_daily,
                "currency": c.currency,
            }
            for c in campaigns
        ]
        return {"pending": pending, "count": len(pending)}
    except Exception as exc:  # noqa: BLE001
        log.exception("review.list failed: %s", exc)
        return {"error": f"review list failed: {exc}", "pending": [], "count": 0}


# ─── council.history — Get recent Agency Council decisions ─────────────────


@register_tool(ToolManifest(
    name="council.history",
    display_name="Council Decision History",
    description=(
        "Retrieve recent Agency Council decisions including consensus "
        "outcome, campaign score, and approval status."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={"limit": "number (optional, default 5)"},
    output_schema={"decisions": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=200,
    estimated_latency_ms=500,
    quality_score=0.9,
    side_effects=SideEffects.READS,
))
async def council_history(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Query recent CouncilSessionRecord + ConsensusDecisionRecord."""
    try:
        from ..models import CouncilSessionRecord, ConsensusDecisionRecord

        session = ctx.session
        if session is None:
            return {"error": "no database session available"}

        limit = input.get("limit", 5)
        try:
            limit_int = int(limit)
        except (TypeError, ValueError):
            limit_int = 5
        limit_int = max(1, min(50, limit_int))

        stmt = (
            select(CouncilSessionRecord, ConsensusDecisionRecord)
            .join(
                ConsensusDecisionRecord,
                ConsensusDecisionRecord.council_session_id == CouncilSessionRecord.id,
            )
            .where(CouncilSessionRecord.tenant_id == ctx.tenant_id)
            .order_by(CouncilSessionRecord.created_at.desc())
            .limit(limit_int)
        )
        result = await session.execute(stmt)
        rows = result.all()

        decisions = [
            {
                "session_id": str(session_rec.id),
                "status": session_rec.status,
                "rounds_completed": session_rec.rounds_completed,
                "approval_status": decision_rec.approval_status,
                "overall_score": decision_rec.overall_score,
                "confidence": decision_rec.confidence,
                "decision": decision_rec.decision,
                "campaign_score": decision_rec.campaign_score,
                "completed_at": session_rec.completed_at.isoformat() if session_rec.completed_at else None,
            }
            for session_rec, decision_rec in rows
        ]
        return {"decisions": decisions, "count": len(decisions)}
    except Exception as exc:  # noqa: BLE001
        log.exception("council.history failed: %s", exc)
        return {"error": f"council history failed: {exc}", "decisions": [], "count": 0}


# ─── billing.usage — Get billing and usage info ────────────────────────────


@register_tool(ToolManifest(
    name="billing.usage",
    display_name="Billing & Usage",
    description=(
        "Return the current billing plan, token usage vs budget, and "
        "video generation usage vs limit."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={},
    output_schema={
        "plan": "string",
        "tokens_used": "number",
        "tokens_budget": "number",
        "videos_used": "number",
        "videos_limit": "number",
    },
    estimated_cost_usd=0.0,
    estimated_time_ms=100,
    estimated_tokens=50,
    estimated_latency_ms=100,
    quality_score=0.95,
    side_effects=SideEffects.READS,
))
async def billing_usage(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Read billing info from the assembled context."""
    try:
        billing = ctx.billing
        return {
            "plan": billing.plan,
            "tokens_used": billing.ai_tokens_used,
            "tokens_budget": billing.ai_budget,
            "videos_used": billing.videos_used,
            "videos_limit": billing.videos_limit,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("billing.usage failed: %s", exc)
        return {
            "error": f"billing usage failed: {exc}",
            "plan": "unknown",
            "tokens_used": 0,
            "tokens_budget": 0,
            "videos_used": 0,
            "videos_limit": 0,
        }


# ─── domain_pack.apply — Apply domain-specific intelligence ────────────────


@register_tool(ToolManifest(
    name="domain_pack.apply",
    display_name="Domain Pack Intelligence",
    description=(
        "Apply domain-specific intelligence from a Domain Pack. Returns "
        "the pack name and domain-specific recommendations."
    ),
    category=ToolCategory.ANALYSIS,
    input_schema={"pack_name": "string (optional)"},
    output_schema={"pack": "string", "recommendations": "array"},
    estimated_cost_usd=0.0,
    estimated_time_ms=200,
    estimated_tokens=200,
    estimated_latency_ms=200,
    quality_score=0.85,
    side_effects=SideEffects.READS,
))
async def domain_pack_apply(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Use the DomainPackRegistry to fetch domain-specific recommendations."""
    try:
        from prachar_shared.domain_packs import get_registry, register_all

        # Ensure packs are registered.
        register_all()
        registry = get_registry()

        pack_name = (input.get("pack_name") or "").strip().lower()

        # If no pack name given, infer from brand category/customer_type.
        if not pack_name and ctx.brand:
            pack_name = (ctx.brand.category or "").strip().lower() or ctx.brand.customer_type

        pack = registry.get(pack_name) if pack_name else None
        if pack is None:
            # Fall back to the first available pack or "business".
            pack = registry.get("business")
            if pack is None:
                all_packs = registry.all()
                if all_packs:
                    pack = all_packs[0]

        if pack is None:
            return {
                "error": "no domain packs registered",
                "pack": "",
                "recommendations": [],
            }

        # Build recommendations from the pack's prompt fragments and tools.
        recommendations: list[str] = []
        if getattr(pack, "recommendations_prompt", ""):
            recommendations.append(pack.recommendations_prompt)
        if getattr(pack, "opportunity_prompt", ""):
            recommendations.append(pack.opportunity_prompt)
        if getattr(pack, "campaign_prompt", ""):
            recommendations.append(pack.campaign_prompt)
        for tool in getattr(pack, "tools", []) or []:
            recommendations.append(f"{tool.label}: {tool.description}")

        return {
            "pack": pack.id or pack.label,
            "recommendations": recommendations,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("domain_pack.apply failed: %s", exc)
        return {
            "error": f"domain pack apply failed: {exc}",
            "pack": "",
            "recommendations": [],
        }


# ─── attribution.query — Query conversion and attribution data ──────────────


@register_tool(ToolManifest(
    name="attribution.query",
    display_name="Attribution & Conversions",
    description=(
        "Query conversion and attribution data across channels. "
        "Returns per-channel conversions, spend, revenue, ROAS, "
        "and touchpoint breakdowns."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={"days": "number (optional, default 30)"},
    output_schema={"channels": "array", "total_conversions": "number", "total_revenue": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=200,
    estimated_latency_ms=500,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.READS,
))
async def attribution_query(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Query campaign performance and attribution data."""
    try:
        from ..models import CampaignPerformance, Campaign
        from sqlalchemy import select, desc, func
        from datetime import date, timedelta

        session = ctx.session
        if session is None or ctx.brand_id is None:
            return {"channels": [], "total_conversions": 0, "total_revenue": 0}

        days = int(input.get("days", 30))
        since = date.today() - timedelta(days=days)

        res = await session.execute(
            select(
                CampaignPerformance.channel,
                func.sum(CampaignPerformance.conversions).label("conversions"),
                func.sum(CampaignPerformance.spend).label("spend"),
                func.sum(CampaignPerformance.revenue).label("revenue"),
                func.sum(CampaignPerformance.clicks).label("clicks"),
                func.avg(CampaignPerformance.roas).label("avg_roas"),
            )
            .join(Campaign, CampaignPerformance.campaign_id == Campaign.id)
            .where(Campaign.brand_id == ctx.brand_id, CampaignPerformance.date >= since)
            .group_by(CampaignPerformance.channel)
        )
        rows = res.all()

        channels = []
        total_conversions = 0
        total_spend = 0
        total_revenue = 0

        for row in rows:
            ch = row.channel or "unknown"
            conv = int(row.conversions or 0)
            spend = float(row.spend or 0)
            revenue = float(row.revenue or 0)
            roas = float(row.avg_roas or 0)
            channels.append({
                "channel": ch,
                "conversions": conv,
                "spend": spend,
                "revenue": revenue,
                "roas": round(roas, 2),
                "cpa": round(spend / conv, 2) if conv > 0 else 0,
            })
            total_conversions += conv
            total_spend += spend
            total_revenue += revenue

        return {
            "channels": sorted(channels, key=lambda c: c["revenue"], reverse=True),
            "total_conversions": total_conversions,
            "total_spend": round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "overall_roas": round(total_revenue / total_spend, 2) if total_spend > 0 else 0,
            "days": days,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("attribution.query failed: %s", exc)
        return {"error": f"attribution query failed: {exc}", "channels": [], "total_conversions": 0}


# ─── timeline.query — Query recent runtime actions/decisions ────────────────


@register_tool(ToolManifest(
    name="timeline.query",
    display_name="Recent Actions History",
    description=(
        "Query the workspace timeline for recent actions, decisions, "
        "and events. Returns what the AI has done recently — campaigns created, "
        "content published, approvals, performance updates, etc."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={"limit": "number (optional, default 10)", "entry_type": "string (optional)"},
    output_schema={"items": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=300,
    estimated_tokens=200,
    estimated_latency_ms=300,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.READS,
))
async def timeline_query(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Query the workspace timeline for recent entries."""
    try:
        from .timeline import TimelineService

        session = ctx.session
        if session is None or ctx.tenant_id is None:
            return {"items": [], "count": 0}

        limit = int(input.get("limit", 10))
        entry_type = input.get("entry_type")

        svc = TimelineService()
        entries, _ = await svc.list(
            session=session,
            tenant_id=ctx.tenant_id,
            brand_id=ctx.brand_id,
            limit=limit,
            entry_type=entry_type,
        )

        items = [
            {
                "title": e.title,
                "type": e.entry_type,
                "actor": e.actor,
                "summary": e.summary,
                "when": e.created_at,
                "replayable": e.replayable,
            }
            for e in entries
        ]
        return {"items": items, "count": len(items)}
    except Exception as exc:  # noqa: BLE001
        log.exception("timeline.query failed: %s", exc)
        return {"error": f"timeline query failed: {exc}", "items": [], "count": 0}


# ─── workflow.query — Query automation rules and tasks ──────────────────────


@register_tool(ToolManifest(
    name="workflow.query",
    display_name="Automation & Workflows",
    description=(
        "Query the current state of automation rules and tasks. "
        "Returns active rules, pending tasks, and recent automation history. "
        "Use this when the user asks about automation, workflows, "
        "scheduled tasks, or the weekly loop."
    ),
    category=ToolCategory.AUTOMATION,
    input_schema={"include_tasks": "boolean (optional, default true)"},
    output_schema={"rules": "array", "tasks": "array", "active_rules": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=200,
    estimated_tokens=150,
    estimated_latency_ms=200,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.READS,
))
async def workflow_query(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Query automation rules and tasks."""
    try:
        from .automation import get_automation_engine, build_automation_context

        engine = get_automation_engine()
        rules = engine.rules
        include_tasks = input.get("include_tasks", True)

        active_rules = [r for r in rules if r.enabled]

        result = {
            "rules": [
                {
                    "name": r.name,
                    "type": r.type.value,
                    "frequency": r.frequency.value,
                    "enabled": r.enabled,
                    "requires_approval": r.requires_approval,
                }
                for r in rules
            ],
            "active_rules": len(active_rules),
            "total_rules": len(rules),
        }

        if include_tasks:
            tasks = engine.tasks
            result["tasks"] = [
                {
                    "type": t.type.value,
                    "status": t.status.value,
                    "frequency": t.frequency.value,
                    "requires_approval": t.requires_approval,
                }
                for t in tasks[:10]
            ]
            result["pending_tasks"] = len(engine.get_pending_tasks())

            # Build live context if we have a session and brand
            if ctx.session and ctx.tenant_id and ctx.brand_id:
                live_ctx = await build_automation_context(
                    ctx.session, ctx.tenant_id, ctx.brand_id
                )
                result["live_context"] = live_ctx

        return result
    except Exception as exc:  # noqa: BLE001
        log.exception("workflow.query failed: %s", exc)
        return {"error": f"workflow query failed: {exc}", "rules": [], "active_rules": 0}
