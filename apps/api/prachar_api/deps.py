from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import Tenant, User
from .security import decode_token


async def get_tenant_plan(session: AsyncSession, user: User) -> str:
    """Look up the tenant's plan from the DB.

    The User model only stores ``tenant_id`` (no relationship), so callers
    must query the Tenant row to read the plan. Falls back to "agency"
    when the tenant row is missing (defensive — should not happen in
    practice but keeps endpoints working for seeded/test users).
    """
    res = await session.execute(select(Tenant).where(Tenant.id == user.tenant_id))
    tenant = res.scalar_one_or_none()
    return str(tenant.plan) if tenant is not None else "agency"


async def _get_session_dep(request: Request):
    async for s in get_session(request):
        yield s


SessionDep = Annotated[AsyncSession, Depends(_get_session_dep)]


def _extract_bearer(authorization: str | None) -> str | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


async def current_user(
    request: Request,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    # Try Authorization header first, then fall back to query param (for SSE/EventSource)
    token = _extract_bearer(authorization)
    if not token:
        token = request.query_params.get("token", "")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        payload = decode_token(token, kind="access")
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad subject") from exc
    # RLS context already set by TenantMiddleware using the token's tenant claim.
    res = await session.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: str):
    async def _check(user: CurrentUser) -> User:
        if str(user.role) not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "insufficient role")
        return user

    return _check
