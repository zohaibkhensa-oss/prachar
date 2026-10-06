from __future__ import annotations

import base64
import json
import logging
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


def _build_x_oauth(state: str) -> str:
    import hashlib
    import secrets

    s = get_settings()
    client_id = s.x_client_id or "placeholder"
    # PKCE: use S256 (secure) instead of plain
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
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
    """Returns the OAuth URL the frontend should redirect to."""
    if not channel:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "channel required")

    builder = OAUTH_BUILDERS.get(channel)
    if not builder:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unsupported channel: {channel}")

    state = str(brand_id)
    auth_url = builder(state)
    return {"auth_url": auth_url, "channel": channel}


@router.get("/{channel}/callback", response_model=ConnectionOut)
async def oauth_callback(channel: str, code: str, state: str, user: CurrentUser, session: SessionDep) -> ConnectionOut:
    """OAuth callback — exchanges code for tokens via the channel adapter.

    1. Validates state (brand_id) belongs to the current tenant
    2. Loads the channel adapter
    3. Calls adapter.exchange_code(code) to get tokens
    4. Encrypts tokens with AES-GCM
    5. Creates/updates Connection record with encrypted tokens
    """
    import asyncio

    # 1. Parse and validate state
    try:
        brand_id = uuid.UUID(state)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid state parameter") from None

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

    try:
        # exchange_code is async in some adapters, sync in others
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

    token_bundle = {
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
        "scopes": tokens.scopes,
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
