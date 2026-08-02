from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from ..audit import log_audit
from ..deps import CurrentUser, SessionDep
from ..email_service import (
    EmailMessage,
    password_reset_email_html,
    verification_email_html,
    verification_success_html,
    send_email,
)
from ..models import Actor, Billing, Plan, Role, Tenant, User
from ..rate_limit import check_rate_limit, reset_rate_limit
from ..schemas import (
    ForgotPasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResendVerificationIn,
    ResetPasswordIn,
    TokenOut,
    UserOut,
    VerifyEmailIn,
)
from ..security import create_token, decode_token, hash_password, verify_password
from prachar_shared.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _budget_for_plan(plan: Plan) -> int:
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


def _make_action_token(user_id: uuid.UUID, action: str, ttl_hours: int = 24) -> str:
    """Create a short-lived JWT for email verification or password reset.

    Uses the JWT secret with a custom ``typ`` so it can't be confused with
    access/refresh tokens. The ``action`` claim distinguishes verify vs reset.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=ttl_hours)).timestamp()),
        "typ": action,  # "email_verify" or "password_reset"
    }
    s = get_settings()
    from jose import jwt as _jwt
    return _jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def _decode_action_token(token: str, expected_action: str) -> uuid.UUID:
    """Decode and validate an action token. Returns user_id."""
    from jose import JWTError, jwt as _jwt
    s = get_settings()
    try:
        payload = _jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError(f"invalid token: {exc}") from exc
    if payload.get("typ") != expected_action:
        raise ValueError("wrong token type")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise ValueError("invalid token subject") from exc


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, request: Request, session: SessionDep) -> TokenOut:
    # Rate limit: 5 registrations per hour per IP
    s = get_settings()
    check_rate_limit(request, "register", s.rate_limit_register_per_hour, 3600)

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
        email_verified=False,
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

    # Send verification email (async, non-blocking — failure doesn't break registration)
    try:
        token = _make_action_token(user.id, "email_verify", ttl_hours=24)
        verify_url = f"{s.web_url}/auth/verify?token={token}"
        await send_email(EmailMessage(
            to=body.email,
            subject="Verify your PRACHAR account",
            html=verification_email_html(verify_url, body.tenant_name),
        ))
    except Exception:
        pass  # Email failure shouldn't break registration

    return TokenOut(**_tokens(user))


@router.post("/login", response_model=TokenOut)
async def login(body: LoginIn, request: Request, session: SessionDep) -> TokenOut:
    # Rate limit: 10 login attempts per minute per IP
    s = get_settings()
    check_rate_limit(request, "login", s.rate_limit_login_per_min, 60)

    # RLS prevents reading users without tenant context; use SECURITY DEFINER
    # function auth_lookup() which bypasses RLS to find the user by email.
    res = await session.execute(
        text("SELECT id, tenant_id, pw_hash, role, is_active, email_verified FROM auth_lookup(:email)"),
        {"email": body.email},
    )
    row = res.fetchone()
    if row is None or not verify_password(body.password, row[2]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    if not row[4]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "user inactive")
    # Note: we allow login without email verification, but unverified users
    # see a banner in the UI prompting them to verify. This avoids lockout
    # if the email service is down.
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

    # Reset rate limit on successful login (don't punish legit users)
    from ..rate_limit import _get_client_ip
    try:
        reset_rate_limit(_get_client_ip(request), "login")
    except Exception:
        pass

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


# ─── Email verification ─────────────────────────────────────────────────────

@router.post("/verify-email")
async def verify_email(body: VerifyEmailIn, session: SessionDep) -> dict:
    """Verify a user's email using the token sent at registration.

    Returns HTML success page (for browser clicks) or JSON (for API clients).
    """
    try:
        user_id = _decode_action_token(body.token, "email_verify")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or expired verification link: {exc}")

    # Look up user via SECURITY DEFINER function (bypasses RLS)
    res = await session.execute(
        text("SELECT id, tenant_id, email_verified FROM auth_lookup_by_id(:uid)"),
        {"uid": str(user_id)},
    )
    row = res.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    if row[2]:
        return {"status": "already_verified", "message": "Email already verified"}

    # Set RLS context for the update + audit log
    tenant_id = row[1]
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    # Update email_verified flag
    await session.execute(
        text("UPDATE users SET email_verified = true WHERE id = :uid"),
        {"uid": str(user_id)},
    )
    await log_audit(
        session, tenant_id=tenant_id, actor=Actor.user, action="email_verified",
        entity_type="user", entity_id=user_id,
    )
    await session.commit()
    return {"status": "verified", "message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(body: ResendVerificationIn, request: Request, session: SessionDep) -> dict:
    """Resend the email verification link."""
    s = get_settings()
    # Rate limit: 3 per hour
    check_rate_limit(request, "resend_verify", 3, 3600)

    res = await session.execute(
        text("SELECT id, tenant_id, email_verified FROM auth_lookup(:email)"),
        {"email": body.email},
    )
    row = res.fetchone()
    if row is None:
        # Don't reveal whether email exists (security)
        return {"status": "sent", "message": "If the email exists, a verification link has been sent."}
    if row[2]:
        return {"status": "already_verified", "message": "Email is already verified."}

    user_id = row[0]
    token = _make_action_token(user_id, "email_verify", ttl_hours=24)
    verify_url = f"{s.web_url}/auth/verify?token={token}"
    await send_email(EmailMessage(
        to=body.email,
        subject="Verify your PRACHAR account",
        html=verification_email_html(verify_url),
    ))
    return {"status": "sent", "message": "If the email exists, a verification link has been sent."}


# ─── Password reset ─────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordIn, request: Request, session: SessionDep) -> dict:
    """Send a password reset link to the given email.

    Always returns the same response whether or not the email exists, to
    prevent email enumeration attacks.
    """
    s = get_settings()
    # Rate limit: 3 per hour per IP
    check_rate_limit(request, "forgot_password", s.rate_limit_password_reset_per_hour, 3600)

    res = await session.execute(
        text("SELECT id, tenant_id FROM auth_lookup(:email)"),
        {"email": body.email},
    )
    row = res.fetchone()
    if row is not None:
        user_id = row[0]
        token = _make_action_token(user_id, "password_reset", ttl_hours=1)
        reset_url = f"{s.web_url}/auth/reset-password?token={token}"
        try:
            await send_email(EmailMessage(
                to=body.email,
                subject="Reset your PRACHAR password",
                html=password_reset_email_html(reset_url),
            ))
        except Exception:
            pass  # Don't reveal email service errors
    return {"status": "sent", "message": "If the email exists, a password reset link has been sent."}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordIn, request: Request, session: SessionDep) -> dict:
    """Reset a user's password using a reset token."""
    # Rate limit: 5 per hour (allows retries if token validation fails)
    check_rate_limit(request, "reset_password", 5, 3600)

    try:
        user_id = _decode_action_token(body.token, "password_reset")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid or expired reset link: {exc}")

    # Look up user via SECURITY DEFINER function (bypasses RLS)
    res = await session.execute(
        text("SELECT id, tenant_id, is_active FROM auth_lookup_by_id(:uid)"),
        {"uid": str(user_id)},
    )
    row = res.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not row[2]:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Set RLS context
    tenant_id = row[1]
    await session.execute(
        text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
    )
    new_hash = hash_password(body.password)
    await session.execute(
        text("UPDATE users SET pw_hash = :ph WHERE id = :uid"),
        {"ph": new_hash, "uid": str(user_id)},
    )
    await log_audit(
        session, tenant_id=tenant_id, actor=Actor.user, action="password_reset",
        entity_type="user", entity_id=user_id,
    )
    await session.commit()
    return {"status": "ok", "message": "Password reset successfully. You can now log in with your new password."}
