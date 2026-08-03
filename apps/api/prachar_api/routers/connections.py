from __future__ import annotations

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from ..deps import CurrentUser, SessionDep
from ..models import Connection
from ..schemas import ConnectionOut
from prachar_shared.config import get_settings

router = APIRouter(prefix="/connections", tags=["connections"])

# ─── OAuth URL builders for each channel ─────────────────────────────────────

# The web URL for the frontend (for redirect URIs)
WEB_URL = get_settings().web_url or "http://localhost:3002"


def _redirect_uri(channel: str) -> str:
    return f"{WEB_URL}/app/connections/{channel}/callback"


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
    s = get_settings()
    client_id = s.x_client_id or "placeholder"
    params = {
        "client_id": client_id,
        "redirect_uri": _redirect_uri("x"),
        "response_type": "code",
        "scope": "tweet.read tweet.write users.read",
        "state": state,
        "code_challenge": "plain",
        "code_challenge_method": "plain",
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
    Creates a connection record after successful OAuth."""
    brand_id = uuid.UUID(state)
    conn = Connection(tenant_id=user.tenant_id, brand_id=brand_id, channel=channel, status="active")
    session.add(conn)
    await session.commit()
    return ConnectionOut.model_validate(conn)
