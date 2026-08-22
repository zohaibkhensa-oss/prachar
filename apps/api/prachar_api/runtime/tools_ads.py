"""Ads network tools — let the Orb manage paid ad campaigns across networks.

These tools let the Orb:
  • List ad network connections
  • Create ad campaigns on any connected ad network
  • Pause/resume campaigns
  • Fetch real ad campaign stats (impressions, clicks, spend, conversions)
  • Upload creatives to ad networks
  • Update budget and bid settings

Architecture Freeze: Plugs into existing Tool Registry + AdNetworkAdapter interface.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from .context import AIContext
from .registry import SideEffects, ToolCategory, ToolManifest, register_tool
from .tools_channels import _load_tokens

log = logging.getLogger("prachar.runtime.tools_ads")


# ─── ads.list — List connected ad networks ───────────────────────────────────


@register_tool(ToolManifest(
    name="ads.list",
    display_name="Connected Ad Networks",
    description=(
        "List all connected ad networks (Google Ads, Meta Ads, TikTok Ads, "
        "LinkedIn Ads, etc.) for the current brand. Returns network name, "
        "status, and connection health. Use when the user asks 'what ad "
        "accounts am I connected to'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={},
    output_schema={"networks": "array", "count": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=300,
    estimated_tokens=100,
    estimated_latency_ms=300,
    quality_score=0.95,
    requires_brand=True,
    side_effects=SideEffects.READS,
))
async def ads_list(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """List connected ad networks."""
    try:
        from ..models import Connection

        session = ctx.session
        if session is None:
            return {"networks": [], "count": 0}

        # Ad networks have channel names ending in "_ads"
        res = await session.execute(
            select(Connection).where(
                Connection.brand_id == ctx.brand_id,
                Connection.channel.like("%_ads"),
            )
        )
        connections = res.scalars().all()

        networks = [
            {
                "network": str(c.channel),
                "status": str(c.status),
                "connected_at": c.created_at.isoformat() if c.created_at else None,
                "has_tokens": bool(c.oauth_tokens_enc),
            }
            for c in connections
        ]
        return {"networks": networks, "count": len(networks)}
    except Exception as exc:  # noqa: BLE001
        log.exception("ads.list failed: %s", exc)
        return {"error": f"ads list failed: {exc}", "networks": [], "count": 0}


# ─── ads.stats — Fetch real campaign stats from an ad network ────────────────


@register_tool(ToolManifest(
    name="ads.stats",
    display_name="Ad Campaign Stats",
    description=(
        "Fetch real performance stats for an ad campaign on a connected ad "
        "network (Google Ads, Meta Ads, TikTok Ads, etc.). Returns impressions, "
        "clicks, spend, conversions, and ROAS. Use when the user asks 'how are "
        "my Google Ads performing' or 'what's my Meta Ads spend this week'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={
        "network": "string (e.g. google_ads, meta_ads, tiktok_ads)",
        "campaign_id": "string (the native campaign ID)",
        "days": "number (optional, default 7)",
    },
    output_schema={"network": "string", "campaign_id": "string", "metrics": "array", "total_spend": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=3000,
    estimated_tokens=200,
    estimated_latency_ms=3000,
    quality_score=0.9,
    requires_brand=True,
    side_effects=SideEffects.EXTERNAL,
))
async def ads_stats(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Fetch ad campaign stats via the network adapter."""
    try:
        network = (input.get("network") or "").strip().lower()
        campaign_id = (input.get("campaign") or input.get("campaign_id") or "").strip()
        if not network or not campaign_id:
            return {"error": "network and campaign_id are required", "metrics": []}

        days = int(input.get("days", 7))
        since = datetime.now(UTC) - timedelta(days=days)

        tokens = await _load_tokens(ctx, network)
        if tokens is None:
            return {
                "error": f"no active connection for {network}. Ask the user to connect it first.",
                "network": network,
                "metrics": [],
            }

        from prachar_shared.adapters.registry import get_ads

        try:
            adapter = get_ads(network)
        except KeyError:
            return {
                "error": f"no ads adapter registered for network '{network}'",
                "network": network,
                "metrics": [],
            }

        import asyncio
        result = adapter.stats(tokens, campaign_id, since)
        if asyncio.iscoroutine(result):
            events = await result
        else:
            events = result

        metrics = [
            {
                "metric": e.metric,
                "value": e.value,
                "timestamp": e.ts.isoformat() if hasattr(e, "ts") and e.ts else None,
            }
            for e in events
        ]

        # Calculate totals
        total_spend = sum(e.value for e in events if e.metric in ("cost", "spend", "spend_in_dollar"))
        total_impressions = sum(e.value for e in events if e.metric == "impressions")
        total_clicks = sum(e.value for e in events if e.metric == "clicks")
        total_conversions = sum(e.value for e in events if e.metric == "conversions")

        return {
            "network": network,
            "campaign_id": campaign_id,
            "metrics": metrics,
            "total_spend": round(total_spend, 2),
            "total_impressions": int(total_impressions),
            "total_clicks": int(total_clicks),
            "total_conversions": int(total_conversions),
            "period": f"last {days} days",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("ads.stats failed: %s", exc)
        return {"error": f"ads stats failed: {exc}", "network": network if "network" in dir() else "", "metrics": []}


# ─── ads.create_campaign — Create a campaign on an ad network ────────────────


@register_tool(ToolManifest(
    name="ads.create_campaign",
    display_name="Create Ad Campaign",
    description=(
        "Create a new ad campaign on a connected ad network (Google Ads, "
        "Meta Ads, TikTok Ads, etc.). Requires user approval. Pass the "
        "campaign details (name, objective, budget, targeting). Use after "
        "generating a campaign strategy with campaign_brain.strategy."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={
        "network": "string (e.g. google_ads, meta_ads)",
        "campaign": "object (name, objective, budget_daily, currency, targeting)",
    },
    output_schema={"network": "string", "campaign_id": "string", "status": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=5000,
    estimated_tokens=0,
    estimated_latency_ms=5000,
    quality_score=0.85,
    requires_brand=True,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
    required_permissions=("can_publish",),
))
async def ads_create_campaign(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Create an ad campaign via the network adapter."""
    try:
        network = (input.get("network") or "").strip().lower()
        campaign = input.get("campaign", {})
        if not network or not campaign:
            return {"error": "network and campaign are required", "status": "failed"}

        tokens = await _load_tokens(ctx, network)
        if tokens is None:
            return {
                "error": f"no active connection for {network}",
                "network": network,
                "status": "failed",
            }

        from prachar_shared.adapters.registry import get_ads

        try:
            adapter = get_ads(network)
        except KeyError:
            return {
                "error": f"no ads adapter for network '{network}'",
                "network": network,
                "status": "failed",
            }

        import asyncio
        result = adapter.create_campaign(tokens, campaign)
        if asyncio.iscoroutine(result):
            campaign_id = await result
        else:
            campaign_id = result

        # Audit
        from ..audit import log_audit
        await log_audit(
            ctx.session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="ads.campaign_created",
            entity_type="ad_campaign",
            entity_id=str(campaign_id),
            payload={"network": network, "campaign_name": campaign.get("name", "")},
        )

        return {
            "network": network,
            "campaign_id": campaign_id,
            "status": "created",
            "message": f"Campaign '{campaign.get('name', '')}' created on {network} with ID {campaign_id}.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("ads.create_campaign failed: %s", exc)
        return {"error": f"create campaign failed: {exc}", "network": network if "network" in dir() else "", "status": "failed"}


# ─── ads.pause — Pause a campaign on an ad network ───────────────────────────


@register_tool(ToolManifest(
    name="ads.pause",
    display_name="Pause Ad Campaign",
    description=(
        "Pause a running ad campaign on a connected ad network. "
        "Requires user approval. Use when the user says 'pause my Google "
        "Ads campaign' or 'stop that Meta Ads campaign'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={
        "network": "string",
        "campaign_id": "string",
    },
    output_schema={"network": "string", "campaign_id": "string", "status": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=2000,
    estimated_tokens=0,
    estimated_latency_ms=2000,
    quality_score=0.9,
    requires_brand=True,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
    required_permissions=("can_publish",),
))
async def ads_pause(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Pause an ad campaign via the network adapter."""
    try:
        network = (input.get("network") or "").strip().lower()
        campaign_id = (input.get("campaign_id") or "").strip()
        if not network or not campaign_id:
            return {"error": "network and campaign_id are required", "status": "failed"}

        tokens = await _load_tokens(ctx, network)
        if tokens is None:
            return {"error": f"no active connection for {network}", "status": "failed"}

        from prachar_shared.adapters.registry import get_ads

        try:
            adapter = get_ads(network)
        except KeyError:
            return {"error": f"no ads adapter for '{network}'", "status": "failed"}

        import asyncio
        result = adapter.pause(tokens, campaign_id)
        if asyncio.iscoroutine(result):
            await result

        # Audit
        from ..audit import log_audit
        await log_audit(
            ctx.session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="ads.campaign_paused",
            entity_type="ad_campaign",
            entity_id=campaign_id,
            payload={"network": network},
        )

        return {
            "network": network,
            "campaign_id": campaign_id,
            "status": "paused",
            "message": f"Campaign {campaign_id} on {network} has been paused.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("ads.pause failed: %s", exc)
        return {"error": f"pause failed: {exc}", "status": "failed"}


# ─── ads.set_budget — Update budget/bid for a campaign ───────────────────────


@register_tool(ToolManifest(
    name="ads.set_budget",
    display_name="Update Ad Budget",
    description=(
        "Update the daily budget and bid strategy for an ad campaign on a "
        "connected ad network. Requires user approval. Use when the user "
        "says 'increase my Google Ads budget to $50/day' or 'change my Meta "
        "Ads bid strategy'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={
        "network": "string",
        "campaign_id": "string",
        "budget": "number (daily budget in account currency)",
        "bid": "object (bid strategy settings)",
    },
    output_schema={"network": "string", "campaign_id": "string", "status": "string", "budget": "number"},
    estimated_cost_usd=0.0,
    estimated_time_ms=2000,
    estimated_tokens=0,
    estimated_latency_ms=2000,
    quality_score=0.9,
    requires_brand=True,
    requires_user_approval=True,
    side_effects=SideEffects.EXTERNAL,
    required_permissions=("can_publish",),
))
async def ads_set_budget(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Update budget and bid for an ad campaign."""
    try:
        network = (input.get("network") or "").strip().lower()
        campaign_id = (input.get("campaign_id") or "").strip()
        budget = float(input.get("budget", 0))
        bid = input.get("bid", {})
        if not network or not campaign_id:
            return {"error": "network and campaign_id are required", "status": "failed"}

        tokens = await _load_tokens(ctx, network)
        if tokens is None:
            return {"error": f"no active connection for {network}", "status": "failed"}

        from prachar_shared.adapters.registry import get_ads

        try:
            adapter = get_ads(network)
        except KeyError:
            return {"error": f"no ads adapter for '{network}'", "status": "failed"}

        import asyncio
        result = adapter.set_budget_bid(tokens, campaign_id, budget, bid)
        if asyncio.iscoroutine(result):
            await result

        # Audit
        from ..audit import log_audit
        await log_audit(
            ctx.session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="ads.budget_updated",
            entity_type="ad_campaign",
            entity_id=campaign_id,
            payload={"network": network, "budget": budget, "bid": bid},
        )

        return {
            "network": network,
            "campaign_id": campaign_id,
            "status": "updated",
            "budget": budget,
            "message": f"Budget for campaign {campaign_id} on {network} updated to {budget}/day.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("ads.set_budget failed: %s", exc)
        return {"error": f"set budget failed: {exc}", "status": "failed"}
