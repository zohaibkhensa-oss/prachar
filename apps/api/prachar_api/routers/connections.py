from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from prachar_shared.config import get_settings
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Connection
from ..schemas import ConnectionOut

log = logging.getLogger("prachar_api.connections")

router = APIRouter(prefix="/connections", tags=["connections"])

# ─── OAuth state signing ─────────────────────────────────────────────────────
# OAuth state is a signed JWT-like token containing:
#   - nonce: random unique value (CSRF protection)
#   - brand_id: the brand to connect
#   - tenant_id: the tenant that initiated the flow
#   - user_id: the user who initiated
#   - exp: expiration timestamp (10 minutes)
#   - pkce_verifier: optional PKCE code_verifier (for X/Twitter)
# This prevents CSRF/account-linking attacks and allows the callback to
# retrieve the PKCE verifier without server-side session storage.

_STATE_TTL_SECONDS = 600  # 10 minutes


def _sign_state(payload: dict) -> str:
    """Sign a state payload using HMAC-SHA256 with the JWT secret."""
    s = get_settings()
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=").decode()
    sig = hmac.new(s.jwt_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify_state(state: str) -> dict:
    """Verify and decode a signed state token."""
    s = get_settings()
    try:
        body, sig = state.rsplit(".", 1)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid state format") from None

    expected_sig = hmac.new(s.jwt_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid state signature")

    try:
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid state payload") from None

    if time.time() > payload.get("exp", 0):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "state expired")

    return payload


# ─── OAuth URL builders for each channel ─────────────────────────────────────

# The web URL for the frontend (for redirect URIs)
WEB_URL = get_settings().web_url or "http://localhost:3002"


def _redirect_uri(channel: str) -> str:
    from prachar_shared.adapters.organic.base import redirect_uri_for
    return redirect_uri_for(channel)


def _build_google_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.google_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("google"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/business.manage https://www.googleapis.com/auth/webmasters https://www.googleapis.com/auth/yt-analytics.readonly",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def _build_youtube_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.google_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("youtube"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube https://www.googleapis.com/auth/yt-analytics.readonly",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"


def _build_meta_oauth(state: str) -> str:
    s = get_settings()
    app_id = s.meta_app_id or "placeholder"
    params = {
        "client_id": app_id,
        "redirect_uri": _redirect_uri("facebook"),
        "response_type": "code",
        "scope": "pages_manage_posts,pages_read_engagement,instagram_basic,instagram_content_publish,ads_management",
        "state": state,
    }
    return f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"


def _build_instagram_oauth(state: str) -> str:
    s = get_settings()
    app_id = s.meta_app_id or "placeholder"
    params = {
        "client_id": app_id,
        "redirect_uri": _redirect_uri("instagram"),
        "response_type": "code",
        "scope": "instagram_basic,instagram_content_publish,pages_show_list",
        "state": state,
    }
    return f"https://api.instagram.com/oauth/authorize?{urlencode(params)}"


def _build_tiktok_oauth(state: str) -> str:
    s = get_settings()
    client_key = s.tiktok_client_key or "placeholder"
    params = {
        "client_key": client_key,
        "redirect_uri": _redirect_uri("tiktok"),
        "response_type": "code",
        "scope": "user.info.basic,video.publish,video.list",
        "state": state,
    }
    return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"


def _build_linkedin_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.linkedin_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("linkedin"),
        "response_type": "code",
        "scope": "w_member_social,rw_organization,rw_ads",
        "state": state,
    }
    return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"


def _build_x_oauth(state: str, pkce_verifier: str | None = None) -> str:
    s = get_settings()
    client_id = s.x_client_id or "placeholder"
    # PKCE: use S256 (secure) — verifier is embedded in the signed state token
    # so the callback can retrieve it without server-side session storage.
    if not pkce_verifier:
        # This shouldn't happen — start_oauth generates and passes it
        pkce_verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(pkce_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("x"),
        "response_type": "code",
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"https://twitter.com/i/oauth2/authorize?{urlencode(params)}"


def _build_pinterest_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.pinterest_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("pinterest"),
        "response_type": "code",
        "scope": "boards:read,pins:read,ads:read",
        "state": state,
    }
    return f"https://www.pinterest.com/oauth/?{urlencode(params)}"


def _build_whatsapp_oauth(state: str) -> str:
    # WhatsApp Business uses Meta's same OAuth flow
    return _build_meta_oauth(state)


def _build_telegram_oauth(state: str) -> str:
    # Telegram uses bot tokens, not OAuth — redirect to BotFather instructions
    return "https://t.me/botfather"


def _build_line_oauth(state: str) -> str:
    s = get_settings()
    channel_id = s.line_channel_id or "placeholder"
    params = {
        "response_type": "code",
        "client_id": channel_id,
        "redirect_uri": _redirect_uri("line"),
        "state": state,
        "scope": "profile openid",
    }
    return f"https://access.line.me/oauth2/v2.1/authorize?{urlencode(params)}"


def _build_vk_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.vk_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("vk"),
        "response_type": "code",
        "state": state,
        "scope": "wall,ads,stats",
    }
    return f"https://oauth.vk.com/authorize?{urlencode(params)}"


def _build_reddit_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.reddit_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "response_type": "code",
        "state": state,
        "redirect_uri": _redirect_uri("reddit"),
        "duration": "permanent",
        "scope": "submit read identity",
    }
    return f"https://www.reddit.com/api/v1/authorize?{urlencode(params)}"


def _build_naver_oauth(state: str) -> str:
    s = get_settings()
    client_id = s.naver_client_id or "placeholder"
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": _redirect_uri("naver"),
        "state": state,
    }
    return f"https://nid.naver.com/oauth2.0/authorize?{urlencode(params)}"


# Channel → OAuth URL builder mapping
OAUTH_BUILDERS = {
    "google": _build_google_oauth,
    "youtube": _build_youtube_oauth,
    "facebook": _build_meta_oauth,
    "instagram": _build_instagram_oauth,
    "meta": _build_meta_oauth,
    "tiktok": _build_tiktok_oauth,
    "linkedin": _build_linkedin_oauth,
    "x": _build_x_oauth,
    "twitter": _build_x_oauth,
    "pinterest": _build_pinterest_oauth,
    "whatsapp": _build_whatsapp_oauth,
    "telegram": _build_telegram_oauth,
    "line": _build_line_oauth,
    "vk": _build_vk_oauth,
    "reddit": _build_reddit_oauth,
    "naver": _build_naver_oauth,
}


@router.get("", response_model=list[ConnectionOut])
async def list_connections(user: CurrentUser, session: SessionDep) -> list[ConnectionOut]:
    res = await session.execute(
        select(Connection).where(Connection.tenant_id == user.tenant_id)
    )
    return [ConnectionOut.model_validate(c) for c in res.scalars().all()]


@router.post("/{channel}/oauth", status_code=status.HTTP_200_OK)
async def start_oauth(channel: str, brand_id: uuid.UUID, user: CurrentUser) -> dict:
    """Returns the OAuth URL the frontend should redirect to.

    Generates a cryptographically secure signed state token containing:
    - nonce (CSRF protection)
    - brand_id (which brand to connect)
    - tenant_id (tenant that initiated)
    - user_id (user who initiated)
    - exp (10-minute expiration)
    - pkce_verifier (for X/Twitter PKCE flow)
    """
    if not channel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "channel required")

    builder = OAUTH_BUILDERS.get(channel)
    if builder is None:
        # Fall back to the channel adapter's own auth_url (gsc, gmb, etc.)
        try:
            import asyncio

            from prachar_shared.adapters.registry import get_organic
            adapter_channel = "facebook" if channel == "meta" else channel
            adapter = get_organic(adapter_channel)

            state_payload = {
                "nonce": secrets.token_urlsafe(16),
                "brand_id": str(brand_id),
                "tenant_id": str(user.tenant_id),
                "user_id": str(user.id),
                "exp": int(time.time()) + _STATE_TTL_SECONDS,
            }
            state = _sign_state(state_payload)
            url = adapter.auth_url(state)
            if asyncio.iscoroutine(url):
                url = await url
            return {"auth_url": url, "channel": channel}
        except KeyError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"unsupported channel: {channel}"
            ) from None

    # Generate PKCE verifier for X/Twitter (embedded in state for callback retrieval)
    pkce_verifier = secrets.token_urlsafe(64) if channel in ("x", "twitter") else None

    # Build signed state token
    state_payload = {
        "nonce": secrets.token_urlsafe(16),
        "brand_id": str(brand_id),
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.id),
        "exp": int(time.time()) + _STATE_TTL_SECONDS,
    }
    if pkce_verifier:
        state_payload["pkce_verifier"] = pkce_verifier

    state = _sign_state(state_payload)

    # X/Twitter builder needs the verifier to generate the challenge
    if channel in ("x", "twitter"):
        auth_url = _build_x_oauth(state, pkce_verifier=pkce_verifier)
    else:
        auth_url = builder(state)
    return {"auth_url": auth_url, "channel": channel}


@router.get("/{channel}/callback", response_model=ConnectionOut)
async def oauth_callback(channel: str, code: str, state: str, user: CurrentUser, session: SessionDep) -> ConnectionOut:
    """OAuth callback — exchanges code for tokens via the channel adapter.

    1. Verifies signed state (CSRF protection + brand/tenant binding)
    2. Loads the channel adapter
    3. Calls adapter.exchange_code(code) to get tokens
       - For X/Twitter, passes the PKCE verifier from the state token
    4. Encrypts tokens with AES-GCM
    5. Creates/updates Connection record with encrypted tokens
    """
    import asyncio

    # 1. Verify and decode signed state
    state_payload = _verify_state(state)

    brand_id = uuid.UUID(state_payload["brand_id"])

    # Verify the callback is for the same tenant/user that initiated
    if state_payload.get("tenant_id") != str(user.tenant_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "state tenant mismatch")

    # 2. Map channel names (facebook → meta, twitter → x)
    adapter_channel = channel
    if channel == "facebook":
        adapter_channel = "facebook"
    elif channel == "twitter":
        adapter_channel = "x"
    elif channel == "meta":
        adapter_channel = "facebook"  # Meta uses Facebook adapter

    # 3. Load adapter and exchange code for tokens
    try:
        from prachar_shared.adapters.registry import get_organic
        adapter = get_organic(adapter_channel)
    except KeyError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsupported channel: {channel}") from None

    # For X/Twitter, retrieve the PKCE verifier from the state
    pkce_verifier = state_payload.get("pkce_verifier")

    try:
        # exchange_code is async in some adapters, sync in others
        # For X/Twitter, pass the PKCE verifier if available
        if pkce_verifier and hasattr(adapter, 'set_pkce_verifier'):
            adapter.set_pkce_verifier(pkce_verifier)
        result = adapter.exchange_code(code)
        if asyncio.iscoroutine(result):
            tokens = await result
        else:
            tokens = result
    except NotImplementedError:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            f"token exchange not implemented for {channel} — set tokens manually",
        ) from None
    except Exception as exc:
        log.error("OAuth token exchange failed for %s: %s", channel, str(exc)[:200])
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"token exchange failed: {str(exc)[:200]}",
        ) from exc

    # 4. Encrypt tokens
    from prachar_shared.security import encrypt_token

    # Meta: discover ad accounts so the ads adapter can address act_{id}.
    token_metadata: dict = {}
    if adapter_channel == "facebook" and hasattr(adapter, "fetch_ad_accounts"):
        try:
            accounts = await adapter.fetch_ad_accounts(tokens)
            if accounts:
                token_metadata["ad_accounts"] = [
                    {
                        "id": a.get("id"),
                        "account_id": a.get("account_id"),
                        "name": a.get("name"),
                        "business": (a.get("business") or {}).get("name"),
                        "account_status": a.get("account_status"),
                    }
                    for a in accounts
                ]
                # Default to the first discovered account; selection UI can update later.
                token_metadata["ad_account_id"] = token_metadata["ad_accounts"][0]["account_id"]
        except Exception:
            log.warning("ad-account discovery failed for %s", channel)

    token_bundle = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
        "scopes": tokens.scopes,
        "metadata": token_metadata,
        "channel": channel,
    }
    encrypted = encrypt_token(json.dumps(token_bundle, default=str))

    # 5. Check for existing connection (upsert)
    from sqlalchemy import select as sa_select

    res = await session.execute(
        sa_select(Connection).where(
            Connection.tenant_id == user.tenant_id,
            Connection.brand_id == brand_id,
            Connection.channel == channel,
        )
    )
    existing = res.scalar_one_or_none()

    if existing:
        existing.oauth_tokens_enc = encrypted
        existing.scopes = tokens.scopes
        existing.expires_at = tokens.expires_at
        existing.status = "active"
        conn = existing
    else:
        conn = Connection(
            tenant_id=user.tenant_id,
            brand_id=brand_id,
            channel=channel,
            oauth_tokens_enc=encrypted,
            scopes=tokens.scopes,
            expires_at=tokens.expires_at,
            status="active",
        )
        session.add(conn)

    await session.commit()
    await session.refresh(conn)
    log.info("OAuth callback success: channel=%s brand=%s", channel, brand_id)
    return ConnectionOut.model_validate(conn)
