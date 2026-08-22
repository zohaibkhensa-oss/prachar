"""Channel adapter tools — wire the Orb directly to organic + ads channel adapters.

These tools let the Orb:
  • List connected channels and their status
  • Fetch live metrics (views, revenue, reach, etc.) from any connected channel
  • Fetch channel profile (handle, followers, display name)
  • Publish content to a connected channel (requires user approval)

Architecture Freeze: These plug into the existing Tool Registry + ChannelAdapter
interfaces. No new abstractions.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from .context import AIContext
from .registry import SideEffects, ToolCategory, ToolManifest, register_tool

log = logging.getLogger("prachar.runtime.tools_channels")


# ─── Helper: load + decrypt OAuth tokens for a connection ────────────────────


async def _load_tokens(ctx: AIContext, channel: str) -> Any:
    """Load and decrypt OAuth tokens for the current brand + channel."""
    from ..models import Connection
    from prachar_shared.contracts import TokenSet
    from prachar_shared.security import decrypt_token

    session = ctx.session
    if session is None:
        return None

    res = await session.execute(
        select(Connection).where(
            Connection.brand_id == ctx.brand_id,
            Connection.channel == channel,
            Connection.status == "active",
        )
    )
    conn = res.scalar_one_or_none()
    if not conn or not conn.oauth_tokens_enc:
        return None

    try:
        raw = decrypt_token(conn.oauth_tokens_enc)
        data = json.loads(raw)
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            scopes=data.get("scopes", []),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("decrypt tokens failed for %s: %s", channel, exc)
        return None


# ─── channel.list — List all connected channels ──────────────────────────────


@register_tool(ToolManifest(
    name="channel.list",
    display_name="Connected Channels",
    description=(
        "List all connected social media channels and ad networks for the "
        "current brand. Returns channel name, status, and whether metrics "
        "are available. Use when the user asks 'what channels am I connected to'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={},
    output_schema={"channels": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=300,
    estimated_tokens=100,
    estimated_latency_ms=300,
    quality_score=0.95,
    requires_brand=True,
    side_effects=SideEffects.READS,
))
async def channel_list(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """List connected channels from the Connection table."""
    try:
        from ..models import Connection

        session = ctx.session
        if session is None:
            return {"channels": [], "count": 0}

        res = await session.execute(
            select(Connection).where(Connection.brand_id == ctx.brand_id)
        )
        connections = res.scalars().all()

        channels = [
            {
                "channel": str(c.channel),
                "status": str(c.status),
                "connected_at": c.created_at.isoformat() if c.created_at else None,
                "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                "has_tokens": bool(c.oauth_tokens_enc),
            }
            for c in connections
        ]
        return {"channels": channels, "count": len(channels)}
    except Exception as exc:  # noqa: BLE001
        log.exception("channel.list failed: %s", exc)
        return {"error": f"channel list failed: {exc}", "channels": [], "count": 0}


# ─── channel.metrics — Fetch live metrics from a connected channel ───────────


@register_tool(ToolManifest(
    name="channel.metrics",
    display_name="Channel Metrics",
    description=(
        "Fetch live metrics from a connected channel (YouTube, Instagram, "
        "Facebook, TikTok, LinkedIn, etc.). Returns views, impressions, "
        "reach, watch time, revenue, and other channel-specific metrics. "
        "Use when the user asks 'what's my YouTube revenue' or 'how are my "
        "Instagram insights'. Pass days=7 for this week, days=30 for this month."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={
        "channel": "string (e.g. youtube, instagram, facebook, tiktok, linkedin)",
        "days": "number (optional, default 7)",
    },
    output_schema={"channel": "string", "metrics": "array", "period": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=3000,
    estimated_tokens=200,
    estimated_latency_ms=3000,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.EXTERNAL,
))
async def channel_metrics(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Fetch live metrics from a connected channel via its adapter."""
    try:
        channel = (input.get("channel") or "").strip().lower()
        if not channel:
            return {"error": "channel is required", "metrics": [], "channel": ""}

        days = int(input.get("days", 7))
        since = datetime.now(UTC) - timedelta(days=days)

        tokens = await _load_tokens(ctx, channel)
        if tokens is None:
            return {
                "error": f"no active connection for {channel}. Ask the user to connect it first.",
                "channel": channel,
                "metrics": [],
                "period": f"last {days} days",
            }

        from prachar_shared.adapters.registry import get_organic

        try:
            adapter = get_organic(channel)
        except KeyError:
            return {
                "error": f"no adapter registered for channel '{channel}'",
                "channel": channel,
                "metrics": [],
                "period": f"last {days} days",
            }

        # Adapters may be sync or async
        import asyncio
        result = adapter.metrics(tokens, since)
        if asyncio.iscoroutine(result):
            events = await result
        else:
            events = result

        metrics = [
            {
                "metric": e.metric,
                "value": e.value,
                "entity_type": e.entity_type,
                "entity_id": e.entity_id,
                "timestamp": e.ts.isoformat() if hasattr(e, "ts") and e.ts else None,
            }
            for e in events
        ]
        return {
            "channel": channel,
            "metrics": metrics,
            "period": f"last {days} days",
            "count": len(metrics),
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("channel.metrics failed: %s", exc)
        return {
            "error": f"channel metrics failed: {exc}",
            "channel": channel if "channel" in dir() else "",
            "metrics": [],
            "period": f"last {days} days" if "days" in dir() else "",
        }


# ─── channel.profile — Fetch channel profile (handle, followers) ─────────────


@register_tool(ToolManifest(
    name="channel.profile",
    display_name="Channel Profile",
    description=(
        "Fetch the connected account's profile (handle, display name, "
        "follower count) from a channel. Use when the user asks 'what's my "
        "YouTube channel name' or 'how many Instagram followers do I have'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={"channel": "string"},
    output_schema={"channel": "string", "profile": "object"},
    estimated_cost_usd=0.0,
    estimated_time_ms=2000,
    estimated_tokens=100,
    estimated_latency_ms=2000,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.EXTERNAL,
))
async def channel_profile(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Fetch channel profile via the adapter."""
    try:
        channel = (input.get("channel") or "").strip().lower()
        if not channel:
            return {"error": "channel is required", "profile": {}, "channel": ""}

        tokens = await _load_tokens(ctx, channel)
        if tokens is None:
            return {
                "error": f"no active connection for {channel}",
                "channel": channel,
                "profile": {},
            }

        from prachar_shared.adapters.registry import get_organic

        try:
            adapter = get_organic(channel)
        except KeyError:
            return {
                "error": f"no adapter for channel '{channel}'",
                "channel": channel,
                "profile": {},
            }

        import asyncio
        result = adapter.fetch_profile(tokens)
        if asyncio.iscoroutine(result):
            profile = await result
        else:
            profile = result

        return {
            "channel": channel,
            "profile": {
                "handle": profile.handle,
                "display_name": profile.display_name,
                "follower_count": profile.follower_count,
                "metadata": profile.metadata,
            },
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("channel.profile failed: %s", exc)
        return {"error": f"channel profile failed: {exc}", "channel": channel if "channel" in dir() else "", "profile": {}}


# ─── channel.publish — Publish content to a connected channel ────────────────


@register_tool(ToolManifest(
    name="channel.publish",
    display_name="Publish to Channel",
    description=(
        "Publish content to a connected social media channel (YouTube, "
        "Instagram, Facebook, TikTok, LinkedIn, etc.). Requires user approval. "
        "The payload must match the channel's content schema. Use after "
        "generating content with creative_studio.generate."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={
        "channel": "string",
        "payload": "object (content to publish — message, link, media, etc.)",
    },
    output_schema={"channel": "string", "published": "boolean", "url": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=5000,
    estimated_tokens=0,
    estimated_latency_ms=5000,
    quality_score=0.85,
    requires_brand=True,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
    required_permissions=("can_publish",),
    memory_categories=[],
))
async def channel_publish(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Publish content to a channel via its adapter."""
    try:
        channel = (input.get("channel") or "").strip().lower()
        payload = input.get("payload", {})
        if not channel or not payload:
            return {"error": "channel and payload are required", "published": False}

        tokens = await _load_tokens(ctx, channel)
        if tokens is None:
            return {
                "error": f"no active connection for {channel}",
                "channel": channel,
                "published": False,
            }

        from prachar_shared.adapters.registry import get_organic

        try:
            adapter = get_organic(channel)
        except KeyError:
            return {
                "error": f"no adapter for channel '{channel}'",
                "channel": channel,
                "published": False,
            }

        # Run policy gate first
        policy = adapter.policy_gate(payload)
        if not policy.passed:
            return {
                "channel": channel,
                "published": False,
                "blocked_reasons": policy.blocked_reasons,
                "warnings": policy.warnings,
            }

        import asyncio
        result = adapter.publish(tokens, payload)
        if asyncio.iscoroutine(result):
            ref = await result
        else:
            ref = result

        # Audit log
        from ..audit import log_audit
        await log_audit(
            ctx.session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="channel.publish",
            entity_type="connection",
            entity_id=channel,
            payload={"native_id": ref.native_id, "url": ref.url},
        )

        return {
            "channel": channel,
            "published": True,
            "native_id": ref.native_id,
            "url": ref.url,
            "published_at": ref.published_at.isoformat(),
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("channel.publish failed: %s", exc)
        return {"error": f"publish failed: {exc}", "channel": channel if "channel" in dir() else "", "published": False}
