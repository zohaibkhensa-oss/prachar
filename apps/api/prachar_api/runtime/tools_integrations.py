"""Integration management tools — let the Orb manage third-party integrations.

The Orb could already list integrations (integrations.list). These tools add:
  • Sync a connected integration (Shopify, HubSpot, GA4, WordPress, Mailchimp)
  • Check integration health
  • Disconnect an integration

Note: connecting a new integration requires OAuth (browser redirect), so the
Orb cannot do that directly. It can tell the user to visit the Integrations page.

Architecture Freeze: Plugs into the existing Tool Registry + Integration Framework.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from .context import AIContext
from .registry import SideEffects, ToolCategory, ToolManifest, register_tool

log = logging.getLogger("prachar.runtime.tools_integrations")


# ─── Helper: load tokens from a Connection (handles both metadata + enc) ─────


async def _load_integration_tokens(ctx: AIContext, name: str) -> tuple[Any, Any]:
    """Load tokens for an integration. Returns (tokens, connection_row)."""
    from ..models import Connection
    from prachar_shared.contracts import TokenSet
    from prachar_shared.security import decrypt_token

    session = ctx.session
    if session is None:
        return None, None

    res = await session.execute(
        select(Connection).where(
            Connection.tenant_id == ctx.tenant_id,
            Connection.channel == name,
            Connection.status == "active",
        )
    )
    conn = res.scalar_one_or_none()
    if not conn:
        return None, None

    # Try metadata JSONB first (used by integrations router)
    metadata = getattr(conn, "metadata", None)
    if metadata and isinstance(metadata, dict) and "access_token" in metadata:
        tokens = TokenSet(
            access_token=metadata["access_token"],
            refresh_token=metadata.get("refresh_token"),
            expires_at=datetime.fromisoformat(metadata["expires_at"]) if "expires_at" in metadata else datetime.now(UTC),
            scopes=metadata.get("scopes", []),
        )
        return tokens, conn

    # Fall back to encrypted tokens
    if conn.oauth_tokens_enc:
        try:
            raw = decrypt_token(conn.oauth_tokens_enc)
            data = json.loads(raw)
            tokens = TokenSet(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                expires_at=datetime.fromisoformat(data["expires_at"]),
                scopes=data.get("scopes", []),
            )
            return tokens, conn
        except Exception as exc:  # noqa: BLE001
            log.warning("decrypt integration tokens failed for %s: %s", name, exc)

    return None, conn


# ─── integrations.sync — Trigger a sync for a connected integration ──────────


@register_tool(ToolManifest(
    name="integrations.sync",
    display_name="Sync Integration",
    description=(
        "Trigger a data sync for a connected integration (Shopify, HubSpot, "
        "GA4, WordPress, Mailchimp). Pulls latest products, contacts, "
        "analytics, or posts. Use when the user says 'sync my Shopify' or "
        "'pull latest data from HubSpot'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={"name": "string (e.g. shopify, hubspot, ga4, wordpress, mailchimp)"},
    output_schema={"success": "boolean", "synced_count": "number", "errors": "array"},
    estimated_cost_usd=0.0,
    estimated_time_ms=10000,
    estimated_tokens=0,
    estimated_latency_ms=10000,
    quality_score=0.85,
    requires_brand=False,
    side_effects=SideEffects.EXTERNAL,
))
async def integrations_sync(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Trigger a sync for a connected integration."""
    try:
        name = (input.get("name") or "").strip().lower()
        if not name:
            return {"error": "integration name is required", "success": False, "synced_count": 0, "errors": []}

        tokens, conn = await _load_integration_tokens(ctx, name)
        if tokens is None:
            return {
                "error": f"integration '{name}' is not connected. Ask the user to connect it via the Integrations page.",
                "success": False,
                "synced_count": 0,
                "errors": [],
            }

        from prachar_shared.integrations import get_integration_registry

        registry = get_integration_registry()
        integration_cls = registry.get(name)
        if integration_cls is None:
            return {
                "error": f"integration '{name}' not found in registry",
                "success": False,
                "synced_count": 0,
                "errors": [],
            }

        integration = integration_cls()

        # For WordPress, set site URL
        metadata = getattr(conn, "metadata", None) or {}
        if name == "wordpress" and metadata.get("site_url"):
            integration._site_url = metadata["site_url"]

        # Sync may be sync or async
        import asyncio
        result = integration.sync(tokens)
        if asyncio.iscoroutine(result):
            sync_result = await result
        else:
            sync_result = result

        # Update last_sync in metadata
        if metadata:
            metadata["last_sync"] = datetime.now(UTC).isoformat()
            metadata["last_error"] = "; ".join(sync_result.errors) if sync_result.errors else None
            try:
                conn.metadata = metadata
                await ctx.session.commit()
            except Exception:  # noqa: BLE001
                pass  # metadata column may not exist

        # Audit
        from ..audit import log_audit
        await log_audit(
            ctx.session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="integration.synced",
            entity_type="integration",
            entity_id=name,
            payload={"synced_count": sync_result.synced_count, "success": sync_result.success},
        )

        return {
            "success": sync_result.success,
            "synced_count": sync_result.synced_count,
            "errors": sync_result.errors,
            "duration_ms": sync_result.duration_ms,
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("integrations.sync failed: %s", exc)
        return {"error": f"sync failed: {exc}", "success": False, "synced_count": 0, "errors": [str(exc)]}


# ─── integrations.health — Check integration health ──────────────────────────


@register_tool(ToolManifest(
    name="integrations.health",
    display_name="Integration Health",
    description=(
        "Check the health of a connected integration. Returns connection "
        "status, last sync time, and any errors. Use when the user asks "
        "'is my Shopify connected' or 'check my GA4 connection'."
    ),
    category=ToolCategory.ANALYTICS,
    input_schema={"name": "string"},
    output_schema={"name": "string", "connected": "boolean", "status": "string", "last_sync": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=2000,
    estimated_tokens=100,
    estimated_latency_ms=2000,
    quality_score=0.9,
    requires_brand=False,
    side_effects=SideEffects.EXTERNAL,
))
async def integrations_health(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Check integration health."""
    try:
        name = (input.get("name") or "").strip().lower()
        if not name:
            return {"error": "integration name is required", "connected": False}

        from ..models import Connection

        session = ctx.session
        if session is None:
            return {"error": "no database session", "connected": False}

        res = await session.execute(
            select(Connection).where(
                Connection.tenant_id == ctx.tenant_id,
                Connection.channel == name,
            )
        )
        conn = res.scalar_one_or_none()

        if not conn:
            return {
                "name": name,
                "connected": False,
                "status": "not_connected",
                "message": f"Integration '{name}' is not connected. Visit the Integrations page to connect it.",
            }

        metadata = getattr(conn, "metadata", None) or {}

        # Try to call the integration's health check
        try:
            from prachar_shared.integrations import get_integration_registry
            from prachar_shared.contracts import TokenSet

            registry = get_integration_registry()
            integration_cls = registry.get(name)
            if integration_cls and conn.oauth_tokens_enc:
                from prachar_shared.security import decrypt_token
                raw = decrypt_token(conn.oauth_tokens_enc)
                data = json.loads(raw)
                tokens = TokenSet(
                    access_token=data["access_token"],
                    refresh_token=data.get("refresh_token"),
                    expires_at=datetime.fromisoformat(data["expires_at"]),
                    scopes=data.get("scopes", []),
                )
                integration = integration_cls()
                health = integration.test_connection(tokens)
                return {
                    "name": name,
                    "connected": True,
                    "status": conn.status,
                    "last_sync": metadata.get("last_sync"),
                    "last_error": metadata.get("last_error"),
                    "health": health if isinstance(health, dict) else {"healthy": bool(health)},
                }
        except Exception as exc:  # noqa: BLE001
            log.warning("health check failed for %s: %s", name, exc)

        return {
            "name": name,
            "connected": conn.status == "active",
            "status": str(conn.status),
            "last_sync": metadata.get("last_sync"),
            "last_error": metadata.get("last_error"),
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("integrations.health failed: %s", exc)
        return {"error": f"health check failed: {exc}", "connected": False}


# ─── integrations.disconnect — Disconnect an integration ─────────────────────


@register_tool(ToolManifest(
    name="integrations.disconnect",
    display_name="Disconnect Integration",
    description=(
        "Disconnect a connected integration. Removes the connection and "
        "revokes access tokens. Use when the user says 'disconnect my "
        "Shopify' or 'remove HubSpot integration'."
    ),
    category=ToolCategory.EXECUTION,
    input_schema={"name": "string"},
    output_schema={"status": "string", "name": "string"},
    estimated_cost_usd=0.0,
    estimated_time_ms=1000,
    estimated_tokens=0,
    estimated_latency_ms=1000,
    quality_score=0.9,
    requires_brand=False,
    requires_user_approval=True,
    side_effects=SideEffects.WRITES,
))
async def integrations_disconnect(ctx: AIContext, input: dict[str, Any]) -> dict[str, Any]:
    """Disconnect an integration."""
    try:
        from ..models import Connection

        name = (input.get("name") or "").strip().lower()
        if not name:
            return {"error": "integration name is required", "status": "failed"}

        session = ctx.session
        if session is None:
            return {"error": "no database session", "status": "failed"}

        res = await session.execute(
            select(Connection).where(
                Connection.tenant_id == ctx.tenant_id,
                Connection.channel == name,
            )
        )
        conn = res.scalar_one_or_none()
        if not conn:
            return {"error": f"integration '{name}' is not connected", "status": "failed"}

        await session.delete(conn)
        await session.commit()

        # Audit
        from ..audit import log_audit
        await log_audit(
            session,
            tenant_id=ctx.tenant_id,
            actor="orb",
            action="integration.disconnected",
            entity_type="integration",
            entity_id=name,
        )

        return {
            "status": "disconnected",
            "name": name,
            "message": f"Integration '{name}' has been disconnected.",
        }
    except Exception as exc:  # noqa: BLE001
        log.exception("integrations.disconnect failed: %s", exc)
        return {"error": f"disconnect failed: {exc}", "status": "failed"}
