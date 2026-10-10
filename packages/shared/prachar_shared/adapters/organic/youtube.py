from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx

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

_YT_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
_YT_TOKEN_URL = "https://oauth2.googleapis.com/token"
_YT_DATA_API = "https://www.googleapis.com/youtube/v3"
_YT_ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"

_YT_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
]
_MAX_RETRIES = 3
_RETRY_STATUS = {401, 403, 429}

_TITLE_MAX = 100
_TAGS_TOTAL_MAX = 500


def _settings():
    from ...config import get_settings

    return get_settings()


def _has_creds() -> bool:
    s = _settings()
    return bool(_client_id(s) and _client_secret(s))


async def _upload_video(
    access_token: str,
    video_url: str,
    snippet: dict[str, Any],
    privacy: str = "private",
) -> str:
    """Resumable upload to YouTube Data API v3.

    1. Download the file from ``video_url`` (e.g. an S3 presigned URL).
    2. POST metadata to open a resumable session → Location header.
    3. PUT the binary to that session URL → returns video id.
    """
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=30.0)) as client:
        dl = await client.get(video_url)
        dl.raise_for_status()
        video_bytes = dl.content
        if not video_bytes:
            raise ValueError("downloaded video is empty")

        init = await client.post(
            # uploads route through www.googleapis.com, not upload.googleapis.com
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"part": "snippet,status", "uploadType": "resumable"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(len(video_bytes)),
            },
            json={
                "snippet": snippet,
                "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
            },
        )
        if init.status_code != 200:
            raise RuntimeError(
                f"youtube resumable upload init failed {init.status_code}: "
                f"{init.text[:500]}"
            )
        upload_url = init.headers.get("Location") or init.headers.get("location")
        if not upload_url:
            raise RuntimeError("youtube resumable upload: no Location header")

        up = await client.put(
            upload_url,
            content=video_bytes,
            headers={"Content-Type": "video/*"},
        )
        if up.status_code != 200:
            raise RuntimeError(
                f"youtube binary upload failed {up.status_code}: {up.text[:500]}"
            )
        video_id = up.json().get("id")
        if not video_id:
            raise RuntimeError("youtube upload returned no video id")
        return str(video_id)


def _client_id(s) -> str:
    # YouTube shares the Google OAuth app when dedicated creds aren't set —
    # the auth URL builder already uses google_client_id.
    return (s.youtube_client_id or s.google_client_id or "").strip()


def _client_secret(s) -> str:
    return (s.youtube_client_secret or s.google_client_secret or "").strip()


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
                    "youtube request retry status=%s attempt=%s url=%s",
                    resp.status_code,
                    attempt,
                    url,
                )
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("youtube request error attempt=%s: %s", attempt, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(
        f"youtube request failed after {_MAX_RETRIES} attempts: {last_exc}"
    )


@register_organic
class YouTubeAdapter(ChannelAdapter):
    """YouTube Data API v3 + Analytics API organic adapter (spec 05)."""

    channel = "youtube"

    # ---- OAuth ----
    def auth_url(self, state: str) -> str:
        s = _settings()
        client_id = _client_id(s) or "YOUTUBE_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(_YT_SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_YT_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        if not _has_creds():
            raise NotImplementedError(
                "YouTube OAuth exchange requires YOUTUBE_CLIENT_ID and "
                "YOUTUBE_CLIENT_SECRET in settings."
            )
        s = _settings()
        resp = asyncio.run(
            _request(
                "POST",
                _YT_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": _client_id(s),
                    "client_secret": _client_secret(s),
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
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
            scopes=body.get("scope", " ".join(_YT_SCOPES)).split(" "),
        )

    # ---- profile ----
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        resp = asyncio.run(
            _request(
                "GET",
                f"{_YT_DATA_API}/channels",
                params={"part": "snippet,statistics", "mine": "true"},
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        body = resp.json()
        items = body.get("items", [])
        if not items:
            return ChannelProfile(
                channel=self.channel,
                handle="unknown",
                display_name="unknown",
                metadata={},
            )
        ch = items[0]
        snippet = ch.get("snippet", {})
        stats = ch.get("statistics", {})
        channel_id = ch.get("id", "")
        return ChannelProfile(
            channel=self.channel,
            handle=snippet.get("customUrl", channel_id),
            display_name=snippet.get("title", channel_id),
            follower_count=int(stats.get("subscriberCount", 0)) or None,
            metadata={
                "video_count": int(stats.get("videoCount", 0)),
                "view_count": int(stats.get("viewCount", 0)),
                "channel_id": channel_id,
            },
        )

    # ---- schema ----
    def generate_schema(self) -> dict[str, Any]:
        """JSON schema for a YouTube content item (spec 05)."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": _TITLE_MAX},
                "description": {"type": "string"},
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "thumbnail_variants": {
                    "type": "array",
                    "items": {"type": "object"},
                    "minItems": 2,
                    "maxItems": 2,
                },
                "pinned_comment": {"type": "string"},
                "playlist_id": {"type": "string"},
            },
            "required": [
                "title",
                "description",
                "tags",
                "thumbnail_variants",
                "pinned_comment",
                "playlist_id",
            ],
        }

    # ---- policy ----
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        blocked: list[str] = []
        warnings: list[str] = []

        title = str(payload.get("title", ""))
        description = str(payload.get("description", ""))
        tags = payload.get("tags", []) or []

        if len(title) > _TITLE_MAX:
            blocked.append(f"title too long: {len(title)} > {_TITLE_MAX}")
        if not title.strip():
            blocked.append("title must not be empty")

        tags_total = sum(len(str(t)) for t in tags)
        if tags_total > _TAGS_TOTAL_MAX:
            blocked.append(
                f"tags total chars too long: {tags_total} > {_TAGS_TOTAL_MAX}"
            )

        # claims_gate over title + description.
        for field, _label in ((title, "title"), (description, "description")):
            cg = claims_gate(field)
            if cg.blocked_reasons:
                blocked.extend(cg.blocked_reasons)
            if cg.warnings:
                warnings.extend(cg.warnings)

        # misleading metadata: title must not be all-caps clickbait.
        if title and title.isupper():
            warnings.append("title is all-caps (possible misleading metadata)")

        return PolicyResult(
            passed=not blocked,
            blocked_reasons=blocked,
            warnings=warnings,
        )

    # ---- publish ----
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        """Publish a video.

        Two paths:
        - ``video_url`` present → resumable upload (videos.insert). Downloads
          the file bytes, opens a resumable session, PUTs the binary.
        - ``video_id`` only → metadata update on an existing upload.
        """
        snippet = {
            "title": str(payload.get("title", "")) or "Untitled",
            "description": str(payload.get("description", "")),
            "tags": payload.get("tags", []) or [],
            "categoryId": str(payload.get("category_id", "22")),
        }
        video_url = str(payload.get("video_url") or "")
        if video_url:
            native_id = asyncio.run(
                _upload_video(
                    tokens.access_token,
                    video_url,
                    snippet,
                    privacy=str(payload.get("privacy", "private")),
                )
            )
        else:
            video_id = str(payload.get("video_id") or payload.get("native_id") or "")
            if not video_id:
                raise ValueError("youtube publish payload requires video_url or video_id")
            body = {"id": video_id, "snippet": snippet}
            resp = asyncio.run(
                _request(
                    "PUT",
                    f"{_YT_DATA_API}/videos",
                    params={"part": "snippet"},
                    json_body=body,
                    token=tokens.access_token,
                )
            )
            resp.raise_for_status()
            native_id = video_id
        return PublishedRef(
            channel=self.channel,
            native_id=native_id,
            url=f"https://www.youtube.com/watch?v={native_id}",
            published_at=datetime.now(UTC),
        )

    # ---- verification ----
    def verify(self, tokens: TokenSet) -> dict[str, Any]:
        """Lightweight liveness check: fetch the authenticated channel's
        snippet. Returns {ok, channel_title, subscriber_count} or {ok: False}."""
        resp = asyncio.run(
            _request(
                "GET",
                f"{_YT_DATA_API}/channels",
                params={"part": "snippet,statistics", "mine": "true"},
                token=tokens.access_token,
            )
        )
        if resp.status_code != 200:
            return {"ok": False, "status": resp.status_code}
        items = resp.json().get("items") or []
        if not items:
            return {"ok": True, "channel_title": None}
        it = items[0]
        return {
            "ok": True,
            "channel_title": it["snippet"].get("title"),
            "subscriber_count": it.get("statistics", {}).get("subscriberCount"),
            "video_count": it.get("statistics", {}).get("videoCount"),
        }

    # ---- metrics ----
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        end = datetime.now(UTC).date().isoformat()
        start = since.astimezone(UTC).date().isoformat()
        # Include revenue metrics (estimatedRevenue, grossRevenue) — requires
        # the yt-analytics-monetary.readonly scope. If the channel isn't
        # monetised or the scope wasn't granted, the API returns 0 / omits
        # the columns and we gracefully skip them.
        metrics_str = (
            "views,impressions,impressionsCtr,estimatedWatchTimeMinutes,"
            "estimatedRevenue,grossRevenue,subscribersGained,subscribersLost"
        )
        params = {
            "ids": "channel==MINE",
            "startDate": start,
            "endDate": end,
            "metrics": metrics_str,
        }
        resp = asyncio.run(
            _request(
                "GET",
                _YT_ANALYTICS_API,
                params=params,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("rows", [])
        column_headers = [h.get("name", "") for h in data.get("columnHeaders", [])]
        events: list[MetricEvent] = []
        if rows:
            row = rows[0]
            mapping = dict(zip(column_headers, row, strict=False))
            metric_names = {
                "views": "views",
                "impressions": "impressions",
                "impressionsCtr": "ctr",
                "estimatedWatchTimeMinutes": "watch_time_minutes",
                "estimatedRevenue": "estimated_revenue",
                "grossRevenue": "gross_revenue",
                "subscribersGained": "subscribers_gained",
                "subscribersLost": "subscribers_lost",
            }
            for raw, canonical in metric_names.items():
                if raw in mapping and mapping[raw] is not None:
                    events.append(
                        MetricEvent(
                            channel=self.channel,
                            entity_type="channel",
                            entity_id="self",
                            metric=canonical,
                            value=float(mapping[raw]),
                        )
                    )
        return events
