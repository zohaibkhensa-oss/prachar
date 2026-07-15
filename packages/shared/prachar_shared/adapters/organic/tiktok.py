from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

from ...config import get_settings
from ...contracts import (
    ChannelProfile,
    MetricEvent,
    PolicyResult,
    PublishedRef,
    TokenSet,
)
from ...policy.claims_gate import claims_gate
from ..registry import register_organic
from .base import ChannelAdapter

logger = logging.getLogger(__name__)

_TT_OAUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
_TT_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_TT_DISPLAY_API = "https://open.tiktokapis.com/v2"
_TT_CONTENT_API = "https://open.tiktokapis.com/v2/post/publish/"

_TT_SCOPES = [
    "video.publish",
    "video.list",
    "user.info.basic",
    "video.upload",
]

_MAX_RETRIES = 3
_RETRY_STATUS = {401, 403, 429}

_CAPTION_MAX = 2200
_HASHTAGS_TOTAL_MAX = 100


def _has_creds() -> bool:
    s = get_settings()
    return bool(s.tiktok_client_key.strip() and s.tiktok_client_secret.strip())


async def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    token: str | None = None,
) -> httpx.Response:
    """HTTP request with graceful retry on 401/403/429."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            req_headers = dict(headers or {})
            if token:
                req_headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.request(
                    method,
                    url,
                    headers=req_headers,
                    params=params,
                    json=json_body,
                    data=data,
                )
            if resp.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES - 1:
                logger.warning(
                    "tiktok request retry status=%s attempt=%s url=%s",
                    resp.status_code,
                    attempt,
                    url,
                )
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("tiktok request error attempt=%s: %s", attempt, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(
        f"tiktok request failed after {_MAX_RETRIES} attempts: {last_exc}"
    )


@register_organic
class TikTokAdapter(ChannelAdapter):
    """TikTok Content Posting API organic adapter (spec 05)."""

    channel = "tiktok"

    # ---- OAuth ----
    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_key = s.tiktok_client_key or "TIKTOK_CLIENT_KEY_PLACEHOLDER"
        params = {
            "client_key": client_key,
            "scope": ",".join(_TT_SCOPES),
            "response_type": "code",
            "redirect_uri": "https://example.com/oauth/tiktok/callback",
            "state": state,
        }
        return f"{_TT_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        if not _has_creds():
            raise NotImplementedError(
                "TikTok OAuth exchange requires TIKTOK_CLIENT_KEY and "
                "TIKTOK_CLIENT_SECRET in settings."
            )
        s = get_settings()
        resp = asyncio.run(
            _request(
                "POST",
                _TT_TOKEN_URL,
                data={
                    "client_key": s.tiktok_client_key,
                    "client_secret": s.tiktok_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": "https://example.com/oauth/tiktok/callback",
                },
            )
        )
        resp.raise_for_status()
        body = resp.json()
        expires_in = int(body.get("expires_in", 3600))
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=body.get("scope", ",".join(_TT_SCOPES)).split(","),
        )

    # ---- profile ----
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        resp = asyncio.run(
            _request(
                "GET",
                f"{_TT_DISPLAY_API}/user/info/",
                params={"fields": "open_id,username,display_name,follower_count"},
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        body = resp.json().get("data", {})
        return ChannelProfile(
            channel=self.channel,
            handle=body.get("username", "") or body.get("open_id", ""),
            display_name=body.get("display_name", "") or body.get("username", ""),
            follower_count=body.get("follower_count"),
            metadata={"open_id": body.get("open_id", "")},
        )

    # ---- schema ----
    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "caption": {"type": "string", "maxLength": _CAPTION_MAX},
                "hashtags": {"type": "array", "items": {"type": "string"}},
                "video_url": {"type": "string"},
                "sound_id": {"type": "string"},
                "duet_enabled": {"type": "boolean"},
                "stitch_enabled": {"type": "boolean"},
                "comment_enabled": {"type": "boolean"},
                "schedule_at": {"type": "string", "format": "date-time"},
            },
            "required": ["caption", "video_url"],
        }

    # ---- policy ----
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        blocked: list[str] = []
        warnings: list[str] = []

        caption = str(payload.get("caption", ""))
        hashtags = payload.get("hashtags", []) or []

        if len(caption) > _CAPTION_MAX:
            blocked.append(f"caption exceeds {_CAPTION_MAX} characters")
        hashtags_total = sum(len(str(t)) for t in hashtags)
        if hashtags_total > _HASHTAGS_TOTAL_MAX:
            blocked.append(
                f"hashtags total chars exceed {_HASHTAGS_TOTAL_MAX}: {hashtags_total}"
            )

        cg = claims_gate(caption)
        if cg.blocked_reasons:
            blocked.extend(cg.blocked_reasons)
        if cg.warnings:
            warnings.extend(cg.warnings)

        # banned-content heuristic: no external URL shortener spam in caption.
        banned_tokens = ("bit.ly", "tinyurl.com", "amzn.to")
        if any(tok in caption.lower() for tok in banned_tokens):
            blocked.append("caption contains banned link shortener")

        return PolicyResult(
            passed=not blocked,
            blocked_reasons=blocked,
            warnings=warnings,
        )

    # ---- publish ----
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        video_url = str(payload.get("video_url", ""))
        if not video_url:
            raise ValueError("tiktok publish payload requires video_url")
        post_body: dict[str, Any] = {
            "post_info": {
                "title": str(payload.get("caption", "")),
                "privacy_level": payload.get("privacy_level", "PUBLIC_TO_EVERYONE"),
                "disable_duet": not bool(payload.get("duet_enabled", True)),
                "disable_stitch": not bool(payload.get("stitch_enabled", True)),
                "disable_comment": not bool(payload.get("comment_enabled", True)),
            },
            "video_url": video_url,
        }
        if payload.get("sound_id"):
            post_body["post_info"]["sound_id"] = str(payload["sound_id"])
        if payload.get("schedule_at"):
            post_body["post_info"]["schedule_at"] = str(payload["schedule_at"])

        resp = asyncio.run(
            _request(
                "POST",
                f"{_TT_CONTENT_API}video/init/",
                json_body=post_body,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        body = resp.json().get("data", {})
        publish_id = str(body.get("publish_id", ""))
        return PublishedRef(
            channel=self.channel,
            native_id=publish_id,
            url=None,
            published_at=datetime.now(UTC),
        )

    # ---- metrics ----
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        start = int(since.timestamp())
        end = int(time.time())
        resp = asyncio.run(
            _request(
                "POST",
                f"{_TT_DISPLAY_API}/video/query/",
                json_body={
                    "start_time": start,
                    "end_time": end,
                    "fields": [
                        "view_count",
                        "like_count",
                        "share_count",
                        "comment_count",
                    ],
                },
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        videos = resp.json().get("data", {}).get("videos", [])
        events: list[MetricEvent] = []
        ts = datetime.now(UTC)
        for v in videos:
            vid = str(v.get("video_id", ""))
            for metric, key in (
                ("video_views", "view_count"),
                ("likes", "like_count"),
                ("shares", "share_count"),
                ("comments", "comment_count"),
            ):
                events.append(
                    MetricEvent(
                        channel=self.channel,
                        entity_type="video",
                        entity_id=vid,
                        metric=metric,
                        value=float(v.get(key, 0)),
                        ts=ts,
                    )
                )
        return events
