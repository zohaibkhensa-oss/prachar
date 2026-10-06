"""Phase 2 Tool Registrations — new orb tools for the CURV AI runtime.

Registers additional tools that the orb can call, building on the existing
tool set in ``tools.py``. Each tool follows the same manifest + decorator
pattern so the Planner can discover and reason about them uniformly.

Constitution Rule 6: Every tool must expose a Tool Manifest.
Constitution Rule 7: The Planner reasons from manifests. Never hard-code.
"""
from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from .context import AIContext
from .memory_categories import MemoryCategory
from .registry import (
    SideEffects,
    ToolCategory,
    ToolManifest,
    register_tool,
)

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
        "Generate a promotional video from a text prompt. "
        "Supports 5-60 seconds. For videos >15s, multiple clips are "
        "generated and stitched together with ffmpeg. "
        "Uses fal.ai Kling (primary) with Gemini Veo fallback. "
        "Returns a playable video URL."
    ),
    category=ToolCategory.CREATIVE,
    input_schema={
        "prompt": "string (description of the video to generate)",
        "duration": "number (optional, default 5, max 60)",
        "aspect_ratio": "string (optional, default 16:9 — options: 16:9, 9:16, 1:1)",
    },
    output_schema={"video_url": "string", "status": "string", "duration": "number"},
    estimated_cost_usd=0.15,
    estimated_time_ms=60000,
    estimated_tokens=0,
    estimated_latency_ms=60000,
    quality_score=0.8,
    requires_user_approval=False,
    side_effects=SideEffects.WRITES,
    soft_timeout_ms=600_000,    # 10 min soft timeout
    hard_timeout_ms=1_200_000,  # 20 min hard timeout (3 clips × ~5min + stitching)
    supports_retry=False,       # Don't retry — each clip costs money
))
async def video_gen_generate(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate a promotional video via the video generation pipeline.

    For videos >15s, generates multiple 10s clips and stitches them
    together using ffmpeg into a single seamless video.
    """
    try:

        prompt = (input.get("prompt") or "").strip()
        if not prompt:
            return {"error": "prompt is required", "video_url": "", "status": "failed", "duration": 0}

        duration = input.get("duration", 5)
        try:
            duration_sec = int(duration)
        except (TypeError, ValueError):
            duration_sec = 5
        duration_sec = max(5, min(60, duration_sec))

        aspect_ratio = (input.get("aspect_ratio") or "16:9").strip() or "16:9"

        # ─── Single clip (≤15s) ───────────────────────────────────────────
        if duration_sec <= 15:
            video_url = await _generate_single_clip(
                prompt=_truncate_prompt(prompt),
                duration_sec=duration_sec,
                aspect_ratio=aspect_ratio,
            )
            if not video_url:
                return {
                    "error": "no video generation service configured (set FAL_KEY or GEMINI_API_KEY)",
                    "video_url": "",
                    "status": "failed",
                    "duration": duration_sec,
                }

            from .artefacts import video_preview
            artefact = video_preview(
                title=prompt[:80],
                url=video_url,
                thumbnail_url="",
                duration=f"{duration_sec}s",
            )

            # ─── Loop 1: Store as Creative for evolution loop ───────────
            try:
                from .creative_lineage import store_generated_creative
                await store_generated_creative(
                    tenant_id=ctx.tenant_id,
                    brand_id=ctx.brand_id,
                    creative_type="video",
                    url=video_url,
                    prompt=prompt,
                    model="wan-3.0",
                    metadata={"duration": duration_sec, "aspect_ratio": aspect_ratio},
                )
            except Exception:
                pass  # non-blocking

            return {
                "video_url": video_url,
                "status": "completed",
                "duration": duration_sec,
                "artefacts": [artefact.to_dict()],
            }

        # ─── Multi-clip stitching (>15s) ──────────────────────────────────
        # Grok Imagine 1.5 supports up to 15s per clip; Kling supports 10s.
        # Use 15s per clip to minimize cost and generation time.
        clip_duration = 15
        num_clips = (duration_sec + clip_duration - 1) // clip_duration  # ceil division
        log.info("video_gen.generate: multi-clip mode — %d clips × %ds = %ds total",
                 num_clips, clip_duration, num_clips * clip_duration)

        # Generate scene prompts — break the main prompt into scenes
        scene_prompts = _split_into_scenes(prompt, num_clips)

        clip_urls: list[str] = []
        for i, scene_prompt in enumerate(scene_prompts):
            log.info("video_gen.generate: generating clip %d/%d: %s", i + 1, num_clips, scene_prompt[:80])
            clip_url = await _generate_single_clip(
                prompt=scene_prompt,
                duration_sec=clip_duration,
                aspect_ratio=aspect_ratio,
            )
            if clip_url:
                clip_urls.append(clip_url)
            else:
                log.warning("video_gen.generate: clip %d failed, skipping", i + 1)

        if not clip_urls:
            return {
                "error": "all clip generations failed (set FAL_KEY or GEMINI_API_KEY)",
                "video_url": "",
                "status": "failed",
                "duration": duration_sec,
            }

        # If only one clip succeeded, return it directly
        if len(clip_urls) == 1:
            from .artefacts import video_preview
            artefact = video_preview(
                title=prompt[:80],
                url=clip_urls[0],
                thumbnail_url="",
                duration=f"{clip_duration}s",
            )
            return {
                "video_url": clip_urls[0],
                "status": "completed",
                "duration": clip_duration,
                "artefacts": [artefact.to_dict()],
            }

        # Stitch clips together with ffmpeg
        final_url = await _stitch_clips_with_ffmpeg(clip_urls, ctx)
        if not final_url:
            # Fallback: return the first clip if stitching fails
            from .artefacts import video_preview
            artefact = video_preview(
                title=prompt[:80],
                url=clip_urls[0],
                thumbnail_url="",
                duration=f"{clip_duration}s",
            )
            return {
                "video_url": clip_urls[0],
                "status": "completed",
                "duration": clip_duration,
                "artefacts": [artefact.to_dict()],
                "warning": "stitching failed, returning first clip only",
            }

        actual_duration = len(clip_urls) * clip_duration
        from .artefacts import video_preview
        artefact = video_preview(
            title=prompt[:80],
            url=final_url,
            thumbnail_url="",
            duration=f"{actual_duration}s",
        )

        # ─── Loop 1: Store stitched video as Creative for evolution loop ──
        try:
            from .creative_lineage import store_generated_creative
            await store_generated_creative(
                tenant_id=ctx.tenant_id,
                brand_id=ctx.brand_id,
                creative_type="video",
                url=final_url,
                prompt=prompt,
                model="wan-3.0-stitched",
                metadata={"duration": actual_duration, "clips": len(clip_urls), "aspect_ratio": aspect_ratio},
            )
        except Exception:
            pass  # non-blocking

        return {
            "video_url": final_url,
            "status": "completed",
            "duration": actual_duration,
            "artefacts": [artefact.to_dict()],
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("video_gen.generate failed: %s", exc)
        return {
            "error": f"video generation failed: {exc}",
            "video_url": "",
            "status": "failed",
            "duration": 0,
        }


async def _generate_single_clip(prompt: str, duration_sec: int, aspect_ratio: str) -> str:
    """Generate a single video clip. Returns the video URL or empty string."""
    from prachar_shared.config import get_settings

    from ..routers.video_gen import (
        VideoGenRequest,
        _call_fal_video,
        _call_gemini_veo,
        _get_gemini_api_key,
    )

    # Clamp to valid range for single clip
    duration_sec = max(5, min(15, duration_sec))

    req = VideoGenRequest(
        prompt=prompt,
        quality="lite",
        duration=str(duration_sec),
        aspect_ratio=aspect_ratio,
        video_type="landscape" if aspect_ratio == "16:9" else "reel",
    )

    # fal.ai Grok Imagine 1.5 (primary — best value, native audio, 1-15s)
    fal_key = get_settings().fal_key.strip()
    if fal_key:
        try:
            req_copy = req.model_copy()
            req_copy.model = "grok"  # Grok Imagine 1.5 — supports 1-15s with native audio
            resp = await _call_fal_video(fal_key, req_copy, prompt, aspect_ratio)
            return resp.video_url
        except Exception as exc:  # noqa: BLE001
            log.error("video_gen.generate fal.ai failed: %s", str(exc)[:300])

    # Gemini Veo fallback (supports 4, 6, or 8s)
    gemini_key = _get_gemini_api_key()
    if gemini_key:
        try:
            resp = await _call_gemini_veo(
                api_key=gemini_key,
                prompt=prompt,
                quality="lite",
                duration_sec=duration_sec,
                aspect_ratio=aspect_ratio,
                with_audio=True,
            )
            return resp.video_url
        except Exception as exc:  # noqa: BLE001
            log.error("video_gen.generate Gemini failed: %s", str(exc)[:300])

    return ""


def _split_into_scenes(prompt: str, num_scenes: int) -> list[str]:
    """Split a single prompt into N scene prompts for multi-clip generation.

    If the prompt describes a sequence (SCENE 1, SCENE 2, etc.), we split
    by those markers. Otherwise we keep the overall context but add
    scene-specific framing, truncating to stay under Fal's 2500-char limit.
    """
    if num_scenes <= 1:
        return [_truncate_prompt(prompt)]

    # Try to split by SCENE markers (e.g. "SCENE 1", "SCENE 2")
    import re
    scene_splits = re.split(r'\bSCENE\s+\d+\s*[-:.\s]', prompt, flags=re.IGNORECASE)
    scene_splits = [s.strip() for s in scene_splits if s.strip()]

    scenes: list[str] = []
    if len(scene_splits) >= num_scenes:
        # We have enough explicit scenes — use them directly
        for i in range(num_scenes):
            scene_context = _SCENE_HINTS[i % len(_SCENE_HINTS)]
            scenes.append(_truncate_prompt(f"{scene_splits[i]}. {scene_context}"))
    else:
        # No explicit scenes — use the full prompt with varied camera angles
        # But truncate the base prompt to leave room for the scene hint
        base = _truncate_prompt(prompt, max_chars=2200)
        for i in range(num_scenes):
            scene_context = _SCENE_HINTS[i % len(_SCENE_HINTS)]
            scenes.append(_truncate_prompt(f"{base}. {scene_context}"))
    return scenes


def _truncate_prompt(prompt: str, max_chars: int = 2400) -> str:
    """Truncate a prompt to stay under Fal.ai's 2500-character limit."""
    if len(prompt) <= max_chars:
        return prompt
    # Try to cut at a sentence boundary
    truncated = prompt[:max_chars - 3]
    last_period = truncated.rfind(". ")
    if last_period > (max_chars - 3) * 0.7:
        return truncated[:last_period + 1]
    return truncated + "..."


# Scene hints for multi-clip variety — cycling through camera angles/moods
_SCENE_HINTS = [
    "Wide establishing shot, cinematic lighting",
    "Medium shot, dynamic camera movement",
    "Close-up detail shot, shallow depth of field",
    "Slow pan across the scene, golden hour lighting",
    "Aerial drone perspective, sweeping motion",
    "Low angle shot, dramatic perspective",
    "Overhead top-down view, clean composition",
    "Tracking shot following the subject, energetic",
]


async def _stitch_clips_with_ffmpeg(clip_urls: list[str], ctx: AIContext) -> str:
    """Download clips, stitch with ffmpeg, upload to storage. Returns URL."""
    import asyncio
    import os
    import tempfile

    import httpx

    from ..routers.video_gen import _store_video_bytes

    if len(clip_urls) < 2:
        return clip_urls[0] if clip_urls else ""

    tmpdir = tempfile.mkdtemp(prefix="video_stitch_")
    try:
        # Download all clips
        clip_paths: list[str] = []
        for i, url in enumerate(clip_urls):
            clip_path = os.path.join(tmpdir, f"clip_{i:03d}.mp4")
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                    resp = await client.get(url, timeout=120)
                    resp.raise_for_status()
                    await asyncio.to_thread(Path(clip_path).write_bytes, resp.content)
                clip_paths.append(clip_path)
            except Exception as exc:
                log.warning("failed to download clip %d: %s", i, str(exc)[:200])

        if len(clip_paths) < 2:
            return clip_urls[0] if clip_urls else ""

        # Create ffmpeg concat file
        concat_file = os.path.join(tmpdir, "concat.txt")
        await asyncio.to_thread(
            Path(concat_file).write_text, "".join(f"file '{p}'\n" for p in clip_paths)
        )

        # Stitch with ffmpeg (re-encode for compatibility)
        output_path = os.path.join(tmpdir, "stitched.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "fast",
            "-movflags", "+faststart",
            output_path,
        ]
        log.info("video_gen.generate: stitching %d clips with ffmpeg", len(clip_paths))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            log.error("ffmpeg stitching failed: %s", stderr.decode()[:500])
            return ""

        # Read the stitched video
        video_bytes = await asyncio.to_thread(Path(output_path).read_bytes)

        # Store and get URL
        final_url = await _store_video_bytes(video_bytes, "stitched_video.mp4")
        log.info("video_gen.generate: stitched video stored at %s", final_url[:80])
        return final_url

    except Exception as exc:
        log.error("video stitching failed: %s", str(exc)[:300])
        return ""
    finally:
        # Clean up temp files
        import shutil
        with contextlib.suppress(Exception):
            shutil.rmtree(tmpdir)


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
        from ..models import ConsensusDecisionRecord, CouncilSessionRecord

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
        from datetime import date, timedelta

        from sqlalchemy import func, select

        from ..models import Campaign, CampaignPerformance

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
        from .automation import build_automation_context, get_automation_engine

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


# ─── A/B Testing Tool ────────────────────────────────────────────────────────


@register_tool(ToolManifest(
    name="creative.ab_test",
    display_name="A/B Test Creatives",
    description=(
        "Generate multiple creative variants with different psychological hooks "
        "(pain point, social proof, curiosity, offer, urgency) and run an A/B test. "
        "Use when the user says 'A/B test this ad' or 'test different versions' or "
        "'which creative performs better'. Returns variant IDs for tracking."
    ),
    category=ToolCategory.CREATIVE,
    input_schema={
        "prompt": "string (base creative prompt to test variants of)",
        "creative_type": "string (image, video, or copy — default: image)",
        "num_variants": "number (optional, default 3, max 5)",
    },
    output_schema={"status": "string", "variant_group": "string", "variants": "array"},
    estimated_cost_usd=0.30,
    estimated_time_ms=60000,
    estimated_tokens=500,
    estimated_latency_ms=60000,
    quality_score=0.95,
    requires_brand=True,
    requires_user_approval=False,
    side_effects=SideEffects.WRITES,
    memory_categories=[MemoryCategory.CREATIVE],
))
async def creative_ab_test(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Generate A/B test variants of a creative."""
    from .ab_testing import create_variant_test

    prompt = (input.get("prompt") or "").strip()
    if not prompt:
        return {"error": "prompt is required", "status": "failed"}

    creative_type = input.get("creative_type", "image")
    num_variants = min(int(input.get("num_variants", 3)), 5)

    try:
        result = await create_variant_test(
            tenant_id=ctx.tenant_id,
            brand_id=ctx.brand_id,
            base_prompt=prompt,
            creative_type=creative_type,
            num_variants=num_variants,
        )
        return result
    except Exception as exc:  # noqa: BLE001
        log.exception("creative.ab_test failed: %s", exc)
        return {"error": f"A/B test failed: {exc}", "status": "failed"}


@register_tool(ToolManifest(
    name="creative.evaluate_test",
    display_name="Evaluate A/B Test",
    description=(
        "Evaluate an ongoing A/B test — compare variant performance, declare a "
        "winner if statistical significance is reached, and promote the winner. "
        "Use when the user says 'check A/B test results' or 'which variant won'."
    ),
    category=ToolCategory.CREATIVE,
    input_schema={
        "variant_group": "string (the variant_group ID from creative.ab_test)",
    },
    output_schema={"status": "string", "winner": "string", "lift": "number", "confidence": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=5000,
    estimated_tokens=0,
    estimated_latency_ms=5000,
    quality_score=0.9,
    requires_brand=True,
    requires_user_approval=False,
    side_effects=SideEffects.READS,
    memory_categories=[MemoryCategory.CREATIVE],
))
async def creative_evaluate_test(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an A/B test and promote the winner if significant."""
    from .ab_testing import evaluate_variant_test, promote_winner

    variant_group = (input.get("variant_group") or "").strip()
    if not variant_group:
        return {"error": "variant_group is required", "status": "failed"}

    try:
        test_result = await evaluate_variant_test(
            tenant_id=ctx.tenant_id,
            brand_id=ctx.brand_id,
            variant_group=variant_group,
        )

        if test_result.is_significant:
            promotion = await promote_winner(
                tenant_id=ctx.tenant_id,
                test_result=test_result,
            )
            return {
                "status": "winner_promoted",
                "winner": str(test_result.winner_id),
                "winner_ctr": test_result.winner_ctr,
                "lift": test_result.lift,
                "confidence": test_result.confidence,
                "promotion": promotion,
                "variants": [
                    {"id": str(v.creative_id), "ctr": v.ctr, "impressions": v.impressions}
                    for v in test_result.variants
                ],
            }
        else:
            return {
                "status": "insufficient_data",
                "confidence": test_result.confidence,
                "is_significant": False,
                "variants": [
                    {"id": str(v.creative_id), "ctr": v.ctr, "impressions": v.impressions}
                    for v in test_result.variants
                ],
                "message": "Not enough data to declare a winner. Need at least 100 impressions per variant.",
            }
    except Exception as exc:  # noqa: BLE001
        log.exception("creative.evaluate_test failed: %s", exc)
        return {"error": f"evaluation failed: {exc}", "status": "failed"}
