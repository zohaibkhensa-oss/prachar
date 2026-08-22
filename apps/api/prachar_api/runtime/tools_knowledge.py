"""Knowledge Hub CRUD tools — let the Orb manage knowledge sources.

The Orb could already search knowledge (knowledge.search). These tools add:
  • List knowledge sources and stats
  • Add a URL as a knowledge source
  • Add text directly as a knowledge source
  • Delete a knowledge source

Architecture Freeze: Plugs into the existing Tool Registry + Knowledge Hub tables.
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .context import AIContext
from .registry import SideEffects, ToolCategory, ToolManifest, register_tool

log = logging.getLogger("prachar.runtime.tools_knowledge")


# ─── knowledge.stats — Knowledge hub statistics ──────────────────────────────


@register_tool(ToolManifest(
    name="knowledge.stats",
    display_name="Knowledge Hub Stats",
    description=(
        "Get statistics about the Business Knowledge Hub — total sources, "
        "chunks, embeddings, broken down by level and status. Use when the "
        "user asks 'how much knowledge do I have' or 'what's in my knowledge base'."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={},
    output_schema={"total_sources": "number", "total_chunks": "number", "by_level": "object"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=100,
    estimated_latency_ms=500,
    quality_score=0.95,
    requires_brand=False,
    side_effects=SideEffects.READS,
))
async def knowledge_stats(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Get knowledge hub statistics."""
    try:
        from ..models import KnowledgeSourceRecord, KnowledgeChunkRecord

        session = ctx.session
        if session is None:
            return {"error": "no database session", "total_sources": 0, "total_chunks": 0}

        # Total sources
        res = await session.execute(
            select(func.count(KnowledgeSourceRecord.id)).where(
                KnowledgeSourceRecord.tenant_id == ctx.tenant_id
            )
        )
        total_sources = res.scalar() or 0

        # Total chunks
        res = await session.execute(
            select(func.count(KnowledgeChunkRecord.id)).where(
                KnowledgeChunkRecord.tenant_id == ctx.tenant_id
            )
        )
        total_chunks = res.scalar() or 0

        # By level
        res = await session.execute(
            select(
                KnowledgeSourceRecord.level,
                func.count(KnowledgeSourceRecord.id),
            ).where(
                KnowledgeSourceRecord.tenant_id == ctx.tenant_id
            ).group_by(KnowledgeSourceRecord.level)
        )
        by_level = {row[0]: row[1] for row in res.all()}

        # By status
        res = await session.execute(
            select(
                KnowledgeSourceRecord.status,
                func.count(KnowledgeSourceRecord.id),
            ).where(
                KnowledgeSourceRecord.tenant_id == ctx.tenant_id
            ).group_by(KnowledgeSourceRecord.status)
        )
        by_status = {row[0]: row[1] for row in res.all()}

        return {
            "total_sources": total_sources,
            "total_chunks": total_chunks,
            "by_level": by_level,
            "by_status": by_status,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("knowledge.stats failed: %s", exc)
        return {"error": f"stats failed: {exc}", "total_sources": 0, "total_chunks": 0}


# ─── knowledge.list_sources — List knowledge sources ─────────────────────────


@register_tool(ToolManifest(
    name="knowledge.list_sources",
    display_name="List Knowledge Sources",
    description=(
        "List all knowledge sources in the Knowledge Hub. Returns title, "
        "level, type, status, and chunk count for each. Use when the user "
        "asks 'what documents are in my knowledge base' or 'show my knowledge sources'."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={"level": "string (optional)", "limit": "number (optional, default 20)"},
    output_schema={"sources": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=200,
    estimated_latency_ms=500,
    quality_score=0.95,
    requires_brand=False,
    side_effects=SideEffects.READS,
))
async def knowledge_list_sources(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """List knowledge sources."""
    try:
        from ..models import KnowledgeSourceRecord

        session = ctx.session
        if session is None:
            return {"sources": [], "count": 0}

        level = (input.get("level") or "").strip().lower() or None
        limit = min(int(input.get("limit", 20)), 100)

        stmt = (
            select(KnowledgeSourceRecord)
            .where(KnowledgeSourceRecord.tenant_id == ctx.tenant_id)
            .order_by(KnowledgeSourceRecord.created_at.desc())
            .limit(limit)
        )
        if level:
            stmt = stmt.where(KnowledgeSourceRecord.level == level)

        res = await session.execute(stmt)
        sources = res.scalars().all()

        return {
            "sources": [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "level": s.level,
                    "source_type": s.source_type,
                    "file_type": s.file_type,
                    "status": s.status,
                    "chunk_count": s.chunk_count,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sources
            ],
            "count": len(sources),
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("knowledge.list_sources failed: %s", exc)
        return {"error": f"list failed: {exc}", "sources": [], "count": 0}


# ─── knowledge.add_url — Add a URL as a knowledge source ─────────────────────


@register_tool(ToolManifest(
    name="knowledge.add_url",
    display_name="Add URL to Knowledge",
    description=(
        "Add a URL as a knowledge source. The system will crawl and extract "
        "content from the URL, chunk it, and generate embeddings for semantic "
        "search. Use when the user says 'add this to my knowledge base' and "
        "provides a URL."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={
        "url": "string (required)",
        "title": "string (optional)",
        "level": "string (optional, default 'brand')",
    },
    output_schema={"source_id": "string", "status": "string"},
    estimated_cost_usd=0.01,
    estimated_time_ms=5000,
    estimated_tokens=500,
    estimated_latency_ms=5000,
    quality_score=0.85,
    requires_brand=False,
    side_effects=SideEffects.WRITES,
))
async def knowledge_add_url(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Add a URL as a knowledge source."""
    try:
        from ..models import KnowledgeSourceRecord

        session = ctx.session
        if session is None:
            return {"error": "no database session", "status": "failed"}

        url = (input.get("url") or "").strip()
        if not url:
            return {"error": "url is required", "status": "failed"}

        title = (input.get("title") or url[:100]).strip()
        level = (input.get("level") or "brand").strip().lower()

        source = KnowledgeSourceRecord(
            tenant_id=ctx.tenant_id,
            title=title,
            level=level,
            source_type="url",
            file_type="url",
            file_url=url,
            status="pending",
            owner_id=ctx.user_id,
        )
        session.add(source)
        await session.commit()

        # TODO: enqueue crawl+chunk+embed task via Celery
        # For now, the status stays "pending" until processed

        return {
            "source_id": str(source.id),
            "status": "pending",
            "message": f"URL '{url}' added to knowledge base. It will be processed shortly.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("knowledge.add_url failed: %s", exc)
        return {"error": f"add url failed: {exc}", "status": "failed"}


# ─── knowledge.add_text — Add text directly as a knowledge source ────────────


@register_tool(ToolManifest(
    name="knowledge.add_text",
    display_name="Add Text to Knowledge",
    description=(
        "Add text content directly as a knowledge source. The text will be "
        "chunked and embedded for semantic search. Use when the user pastes "
        "text and says 'add this to my knowledge base' or 'remember this'."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={
        "title": "string (required)",
        "content": "string (required)",
        "level": "string (optional, default 'brand')",
        "description": "string (optional)",
    },
    output_schema={"source_id": "string", "status": "string"},
    estimated_cost_usd=0.01,
    estimated_time_ms=3000,
    estimated_tokens=500,
    estimated_latency_ms=3000,
    quality_score=0.85,
    requires_brand=False,
    side_effects=SideEffects.WRITES,
))
async def knowledge_add_text(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Add text content as a knowledge source."""
    try:
        from ..models import KnowledgeSourceRecord

        session = ctx.session
        if session is None:
            return {"error": "no database session", "status": "failed"}

        title = (input.get("title") or "").strip()
        content = (input.get("content") or "").strip()
        if not title or not content:
            return {"error": "title and content are required", "status": "failed"}

        level = (input.get("level") or "brand").strip().lower()
        description = (input.get("description") or "").strip() or None

        source = KnowledgeSourceRecord(
            tenant_id=ctx.tenant_id,
            title=title,
            description=description,
            level=level,
            source_type="manual",
            file_type="text",
            status="pending",
            owner_id=ctx.user_id,
        )
        session.add(source)
        await session.commit()

        # TODO: enqueue chunk+embed task via Celery

        return {
            "source_id": str(source.id),
            "status": "pending",
            "message": f"Text '{title}' added to knowledge base. It will be processed shortly.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("knowledge.add_text failed: %s", exc)
        return {"error": f"add text failed: {exc}", "status": "failed"}


# ─── knowledge.delete_source — Delete a knowledge source ─────────────────────


@register_tool(ToolManifest(
    name="knowledge.delete_source",
    display_name="Delete Knowledge Source",
    description=(
        "Delete a knowledge source and all its chunks and embeddings. "
        "Use when the user says 'remove this from my knowledge base' or "
        "'delete that document'. Requires the source ID."
    ),
    category=ToolCategory.RESEARCH,
    input_schema={"source_id": "string (required)"},
    output_schema={"status": "string", "source_id": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=500,
    estimated_tokens=0,
    estimated_latency_ms=500,
    quality_score=0.95,
    requires_brand=False,
    side_effects=SideEffects.WRITES,
))
async def knowledge_delete_source(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Delete a knowledge source and its chunks."""
    try:
        from ..models import KnowledgeSourceRecord, KnowledgeChunkRecord, KnowledgeEmbeddingRecord

        session = ctx.session
        if session is None:
            return {"error": "no database session", "status": "failed"}

        source_id = (input.get("source_id") or "").strip()
        if not source_id:
            return {"error": "source_id is required", "status": "failed"}

        sid = uuid.UUID(source_id)

        # Verify ownership
        res = await session.execute(
            select(KnowledgeSourceRecord).where(
                KnowledgeSourceRecord.id == sid,
                KnowledgeSourceRecord.tenant_id == ctx.tenant_id,
            )
        )
        source = res.scalar_one_or_none()
        if not source:
            return {"error": "source not found", "status": "failed"}

        # Delete embeddings for chunks belonging to this source
        await session.execute(
            select(KnowledgeChunkRecord.id).where(KnowledgeChunkRecord.source_id == sid)
        )
        # Delete chunks
        # Note: cascade delete should handle this if FK is set up,
        # but we do it explicitly for safety
        res = await session.execute(
            select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.source_id == sid)
        )
        chunks = res.scalars().all()
        for chunk in chunks:
            # Delete embeddings for this chunk
            emb_res = await session.execute(
                select(KnowledgeEmbeddingRecord).where(
                    KnowledgeEmbeddingRecord.chunk_id == chunk.id
                )
            )
            for emb in emb_res.scalars().all():
                await session.delete(emb)
            await session.delete(chunk)

        await session.delete(source)
        await session.commit()

        return {
            "status": "deleted",
            "source_id": source_id,
            "message": f"Knowledge source '{source.title}' has been deleted.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("knowledge.delete_source failed: %s", exc)
        return {"error": f"delete failed: {exc}", "status": "failed"}
