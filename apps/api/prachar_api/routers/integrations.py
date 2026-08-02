"""Integration Centre — API for managing all platform integrations.

First-class capability: users can see, connect, disconnect, sync, and
monitor all their integrations from a single place.

Endpoints:
- GET /integrations — list all available + connected integrations
- POST /integrations/{name}/connect — start OAuth flow or validate credentials
- POST /integrations/{name}/callback — OAuth callback
- DELETE /integrations/{name} — disconnect
- POST /integrations/{name}/sync — trigger a sync
- GET /integrations/{name}/health — check connection health
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import CurrentUser, SessionDep
from ..models import Connection
from ..audit import log_audit

# Import all integrations to trigger registration
from prachar_shared.integrations import (
    IntegrationCapability,
    IntegrationInfo,
    get_integration_registry,
)
from prachar_shared.integrations.google_analytics import GoogleAnalytics4
from prachar_shared.integrations.wordpress import WordPress
from prachar_shared.integrations.shopify import Shopify
from prachar_shared.integrations.mailchimp import Mailchimp
from prachar_shared.integrations.hubspot import HubSpot

log = logging.getLogger("prachar.api.integrations")
router = APIRouter(prefix="/integrations", tags=["integrations"])


# ─── Schemas ────────────────────────────────────────────────────────────────


class IntegrationOut(BaseModel):
    """Integration info + connection status."""
    name: str
    display_name: str
    category: str
    icon: str = ""
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    auth_type: str = "oauth"
    scopes: list[str] = Field(default_factory=list)
    docs_url: str = ""
    setup_guide: str = ""
    # Connection status (null if not connected)
    connected: bool = False
    connection_id: str | None = None
    status: str | None = None  # connected, disconnected, error, expired
    last_sync: str | None = None
    last_error: str | None = None


class ConnectRequest(BaseModel):
    """Request to connect an integration."""
    # For OAuth: code, redirect_uri
    code: str | None = None
    redirect_uri: str | None = None
    # For API key / app password:
    site_url: str | None = None
    username: str | None = None
    app_password: str | None = None
    api_key: str | None = None
    # For GA4:
    property_id: str | None = None
    # Brand to associate with
    brand_id: str | None = None


class SyncResponse(BaseModel):
    success: bool
    synced_count: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_ms: float = 0.0


# ─── Endpoints ──────────────────────────────────────────────────────────────


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    user: CurrentUser,
    session: SessionDep,
) -> list[IntegrationOut]:
    """List all available integrations with their connection status."""
    registry = get_integration_registry()
    all_info = registry.all_integrations()

    # Get user's connections
    res = await session.execute(
        select(Connection).where(Connection.tenant_id == user.tenant_id)
    )
    connections = {c.channel: c for c in res.scalars().all()}

    result: list[IntegrationOut] = []
    for name, info in all_info.items():
        conn = connections.get(name)
        caps = [
            c.name for c in IntegrationCapability
            if c != IntegrationCapability.NONE and info.capabilities & c
        ]
        result.append(IntegrationOut(
            name=info.name,
            display_name=info.display_name,
            category=info.category,
            icon=info.icon,
            description=info.description,
            capabilities=caps,
            auth_type=info.auth_type,
            scopes=info.scopes,
            docs_url=info.docs_url,
            setup_guide=info.setup_guide,
            connected=conn is not None and conn.status == "active",
            connection_id=str(conn.id) if conn else None,
            status=conn.status if conn else None,
            last_sync=conn.metadata.get("last_sync") if conn and conn.metadata else None,
            last_error=conn.metadata.get("last_error") if conn and conn.metadata else None,
        ))

    # Sort: connected first, then by category
    result.sort(key=lambda x: (not x.connected, x.category, x.display_name))
    return result


@router.post("/{name}/connect", response_model=dict)
async def connect_integration(
    name: str,
    body: ConnectRequest,
    user: CurrentUser,
    session: SessionDep,
    request: Request,
) -> dict:
    """Connect an integration by exchanging credentials/tokens."""
    registry = get_integration_registry()
    integration_cls = registry.get(name)
    if integration_cls is None:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    integration = integration_cls()
    info = integration_cls.info()

    try:
        # Authenticate based on auth type
        if info.auth_type == "oauth":
            if not body.code:
                # Return the OAuth URL for the frontend to redirect to
                # (GA4-specific, but the pattern applies to other OAuth integrations)
                if name == "google_analytics":
                    ga4 = GoogleAnalytics4()
                    # In production, these come from settings
                    client_id = request.headers.get("X-Google-Client-Id", "")
                    redirect_uri = body.redirect_uri or ""
                    auth_url = ga4.auth_url(
                        state=str(body.brand_id or user.tenant_id),
                        client_id=client_id,
                        redirect_uri=redirect_uri,
                    )
                    return {"auth_url": auth_url, "auth_type": "oauth"}
                raise HTTPException(status_code=400, detail="OAuth code is required")
            tokens = integration.authenticate(
                code=body.code,
                redirect_uri=body.redirect_uri,
            )
        elif info.auth_type == "app_password":
            tokens = integration.authenticate(
                site_url=body.site_url,
                username=body.username,
                app_password=body.app_password,
            )
        elif info.auth_type == "api_key":
            tokens = integration.authenticate(api_key=body.api_key)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported auth type: {info.auth_type}")

        # Test the connection
        is_healthy = integration.test_connection(tokens)
        if not is_healthy:
            raise HTTPException(status_code=401, detail="Connection test failed — check credentials")

        # Check if connection already exists
        existing = await session.execute(
            select(Connection).where(
                Connection.tenant_id == user.tenant_id,
                Connection.channel == name,
            )
        )
        existing_conn = existing.scalar_one_or_none()

        if existing_conn:
            # Update existing connection
            existing_conn.status = "active"
            existing_conn.metadata = {
                "access_token": tokens.access_token,
                "refresh_token": tokens.refresh_token,
                "expires_at": tokens.expires_at.isoformat(),
                "scopes": tokens.scopes,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_sync": None,
                "last_error": None,
            }
            if body.property_id:
                existing_conn.metadata["property_id"] = body.property_id
            if body.site_url:
                existing_conn.metadata["site_url"] = body.site_url
            conn = existing_conn
        else:
            # Create new connection
            conn = Connection(
                tenant_id=user.tenant_id,
                brand_id=uuid.UUID(body.brand_id) if body.brand_id else None,
                channel=name,
                status="active",
                metadata={
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_at": tokens.expires_at.isoformat(),
                    "scopes": tokens.scopes,
                    "connected_at": datetime.now(timezone.utc).isoformat(),
                    "last_sync": None,
                    "last_error": None,
                    **({"property_id": body.property_id} if body.property_id else {}),
                    **({"site_url": body.site_url} if body.site_url else {}),
                },
            )
            session.add(conn)

        await session.commit()

        await log_audit(
            session,
            tenant_id=user.tenant_id,
            actor=str(user.id),
            action="integration.connected",
            entity_type="integration",
            entity_id=name,
            payload={"status": "active"},
        )
        await session.commit()

        return {
            "status": "connected",
            "integration": name,
            "connection_id": str(conn.id),
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to connect %s: %s", name, e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Connection failed: {e}")


@router.delete("/{name}", response_model=dict)
async def disconnect_integration(
    name: str,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Disconnect an integration."""
    res = await session.execute(
        select(Connection).where(
            Connection.tenant_id == user.tenant_id,
            Connection.channel == name,
        )
    )
    conn = res.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not connected")

    conn.status = "disconnected"
    await session.commit()

    await log_audit(
        session,
        tenant_id=user.tenant_id,
        actor=str(user.id),
        action="integration.disconnected",
        entity_type="integration",
        entity_id=name,
        payload={},
    )
    await session.commit()

    return {"status": "disconnected", "integration": name}


@router.post("/{name}/sync", response_model=SyncResponse)
async def sync_integration(
    name: str,
    user: CurrentUser,
    session: SessionDep,
) -> SyncResponse:
    """Trigger a sync for a connected integration."""
    registry = get_integration_registry()
    integration_cls = registry.get(name)
    if integration_cls is None:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    res = await session.execute(
        select(Connection).where(
            Connection.tenant_id == user.tenant_id,
            Connection.channel == name,
        )
    )
    conn = res.scalar_one_or_none()
    if not conn or conn.status != "active":
        raise HTTPException(status_code=400, detail="Integration not connected")

    from prachar_shared.contracts import TokenSet
    metadata = conn.metadata or {}
    tokens = TokenSet(
        access_token=metadata.get("access_token", ""),
        refresh_token=metadata.get("refresh_token"),
        expires_at=datetime.fromisoformat(metadata["expires_at"]) if "expires_at" in metadata else datetime.now(timezone.utc),
        scopes=metadata.get("scopes", []),
    )

    integration = integration_cls()

    # For WordPress, set the site URL on the integration
    if name == "wordpress" and metadata.get("site_url"):
        integration._site_url = metadata["site_url"]

    try:
        result = integration.sync(tokens)

        # Update last_sync
        conn.metadata = {
            **metadata,
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "last_error": "; ".join(result.errors) if result.errors else None,
        }
        await session.commit()

        await log_audit(
            session,
            tenant_id=user.tenant_id,
            actor=str(user.id),
            action="integration.synced",
            entity_type="integration",
            entity_id=name,
            payload={"synced_count": result.synced_count, "success": result.success},
        )
        await session.commit()

        return SyncResponse(
            success=result.success,
            synced_count=result.synced_count,
            errors=result.errors,
            duration_ms=result.duration_ms,
        )
    except Exception as e:
        log.error("Sync failed for %s: %s", name, e, exc_info=True)
        return SyncResponse(success=False, errors=[str(e)])


@router.get("/{name}/health", response_model=dict)
async def integration_health(
    name: str,
    user: CurrentUser,
    session: SessionDep,
) -> dict:
    """Check the health of a connected integration."""
    registry = get_integration_registry()
    integration_cls = registry.get(name)
    if integration_cls is None:
        raise HTTPException(status_code=404, detail=f"Integration '{name}' not found")

    res = await session.execute(
        select(Connection).where(
            Connection.tenant_id == user.tenant_id,
            Connection.channel == name,
        )
    )
    conn = res.scalar_one_or_none()
    if not conn:
        return {"name": name, "status": "disconnected"}

    from prachar_shared.contracts import TokenSet
    metadata = conn.metadata or {}
    tokens = TokenSet(
        access_token=metadata.get("access_token", ""),
        refresh_token=metadata.get("refresh_token"),
        expires_at=datetime.fromisoformat(metadata["expires_at"]) if "expires_at" in metadata else datetime.now(timezone.utc),
        scopes=metadata.get("scopes", []),
    )

    integration = integration_cls()
    if name == "wordpress" and metadata.get("site_url"):
        integration._site_url = metadata["site_url"]

    health = integration.health(tokens)
    return health.to_dict()
