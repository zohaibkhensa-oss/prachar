from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep
from ..models import Actor, Billing, Plan, Role, Tenant, User
from ..schemas import LoginIn, RefreshIn, RegisterIn, TokenOut, UserOut
from ..security import create_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _budget_for_plan(plan: Plan) -> int:
    from prachar_shared.config import get_settings

    s = get_settings()
    return {
        Plan.starter: s.ai_budget_starter_inr,
        Plan.growth: s.ai_budget_growth_inr,
        Plan.agency: s.ai_budget_agency_inr,
    }[plan]


def _tokens(user: User) -> dict:
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    extra = {"tenant_id": str(user.tenant_id), "role": role_str, "email": user.email}
    return {
        "access_token": create_token(user.id, "access", extra),
        "refresh_token": create_token(user.id, "refresh", extra),
        "token_type": "bearer",
        "user": UserOut.model_validate(user).model_dump(),
    }


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, request: Request, session: SessionDep) -> TokenOut:
    # tenants table has no RLS; create tenant first.
    tenant = Tenant(name=body.tenant_name, plan=body.plan)
    session.add(tenant)
    await session.flush()
    # Now set RLS context for the rest of the transaction.
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant.id)}
    )
    user = User(
        tenant_id=tenant.id,
        email=body.email,
        role=Role.owner,
        pw_hash=hash_password(body.password),
    )
    session.add(user)
    billing = Billing(tenant_id=tenant.id, provider="stripe", ai_budget_month=_budget_for_plan(body.plan))
    session.add(billing)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "email already registered") from exc
    await log_audit(
        session, tenant_id=tenant.id, actor=Actor.user, action="register",
        entity_type="user", entity_id=user.id, payload={"email": user.email},
    )
    await session.commit()
    return TokenOut(**_tokens(user))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, session: SessionDep) -> TokenOut:
    # RLS prevents reading users without tenant context; use SECURITY DEFINER
    # function auth_lookup() which bypasses RLS to find the user by email.
    res = await session.execute(
        text("SELECT id, tenant_id, pw_hash, role, is_active FROM auth_lookup(:email)"),
        {"email": body.email},
    )
    row = res.fetchone()
    if row is None or not verify_password(body.password, row[2]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not row[4]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user inactive")
    # Now set RLS context for the audit log.
    tenant_id = row[1]
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    # Build a minimal user-like object for _tokens.
    user_id = row[0]
    role_str = row[3]

    class _U:
        pass

    _U.id = user_id
    _U.tenant_id = tenant_id
    _U.role = role_str
    _U.email = body.email
    await log_audit(
        session, tenant_id=tenant_id, actor=Actor.user, action="login",
        entity_type="user", entity_id=user_id,
    )
    await session.commit()
    return TokenOut(**_tokens(_U()))


@router.post("/refresh", response_model=TokenOut)
async def refresh(body: RefreshIn, request: Request, session: SessionDep) -> TokenOut:
    try:
        payload = decode_token(body.refresh_token, kind="refresh")
        user_id = uuid.UUID(payload["sub"])
        tenant_id_str = payload.get("tenant_id")
    except (ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid refresh token") from exc
    if not tenant_id_str:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing tenant claim")
    # Set RLS context from the refresh token's tenant claim.
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": tenant_id_str}
    )
    res = await session.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found")
    await session.commit()
    return TokenOut(**_tokens(user))


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
