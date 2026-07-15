from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Connection
from ..schemas import ConnectionOut

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=list[ConnectionOut])
async def list_connections(user: CurrentUser, session: SessionDep) -> list[ConnectionOut]:
    res = await session.execute(
        select(Connection).where(Connection.tenant_id == user.tenant_id)
    )
    return [ConnectionOut.model_validate(c) for c in res.scalars().all()]


@router.post("/{channel}/oauth", status_code=status.HTTP_200_OK)
async def start_oauth(channel: str, brand_id: uuid.UUID, user: CurrentUser) -> dict:
    """Returns the OAuth URL the frontend should redirect to. Real adapter
    wiring lands in S2+; for S0 we return a placeholder."""
    if not channel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "channel required")
    return {"auth_url": f"https://example.com/oauth/{channel}?state={brand_id}", "channel": channel}


@router.get("/{channel}/callback", response_model=ConnectionOut)
async def oauth_callback(channel: str, code: str, state: str, user: CurrentUser, session: SessionDep) -> ConnectionOut:
    """OAuth callback — exchanges code for tokens via the channel adapter.
    S0 stub: creates a placeholder connection record."""
    brand_id = uuid.UUID(state)
    conn = Connection(tenant_id=user.tenant_id, brand_id=brand_id, channel=channel, status="active")
    session.add(conn)
    await session.commit()
    return ConnectionOut.model_validate(conn)
