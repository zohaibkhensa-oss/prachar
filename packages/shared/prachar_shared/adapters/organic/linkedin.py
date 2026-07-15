from __future__ import annotations

import asyncio
import logging
import re
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

_LI_OAUTH_BASE = "https://www.linkedin.com/oauth/v2/authorization"
_LI_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
_LI_API = "https://api.linkedin.com"
_LI_ANALYTICS = "https://api.linkedin.com/rest/organizationalEntityShareStatistics"

_LI_SCOPES = [
    "w_member_social",
    "r_organization_social",
    "r_organization_social",
    "rw_organization_admin",
]

_MAX_RETRIES = 3
_RETRY_STATUS = {401, 403, 429}

_TEXT_MAX = 3000

# Engagement-bait phrases (subset).
_ENGAGEMENT_BAIT = re.compile(
    r"\b(like\s+if\s+you|comment\s+below|tag\s+a\s+friend|share\s+if\s+you)\b",
    re.IGNORECASE,
)
# Excessive-emoji heuristic: flag if more than 5 emoji-ish chars in text.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F300-\U0001F6FF]"
)


def _has_creds() -> bool:
    s = get_settings()
    return bool(s.linkedin_client_id.strip() and s.linkedin_client_secret.strip())


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
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            req_headers = dict(headers or {})
            if token:
                req_headers["Authorization"] = f"Bearer {token}"
            req_headers.setdefault("X-Restli-Protocol-Version", "2.0.0")
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
                    "linkedin request retry status=%s attempt=%s url=%s",
                    resp.status_code,
                    attempt,
                    url,
                )
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("linkedin request error attempt=%s: %s", attempt, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(
        f"linkedin request failed after {_MAX_RETRIES} attempts: {last_exc}"
    )


@register_organic
class LinkedInAdapter(ChannelAdapter):
    """LinkedIn Marketing/Community APIs organic adapter (spec 05)."""

    channel = "linkedin"

    # ---- OAuth ----
    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.linkedin_client_id or "LINKEDIN_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": "https://example.com/oauth/linkedin/callback",
            "scope": " ".join(_LI_SCOPES),
            "response_type": "code",
            "state": state,
        }
        return f"{_LI_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        if not _has_creds():
            raise NotImplementedError(
                "LinkedIn OAuth exchange requires LINKEDIN_CLIENT_ID and "
                "LINKEDIN_CLIENT_SECRET in settings."
            )
        s = get_settings()
        resp = asyncio.run(
            _request(
                "POST",
                _LI_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": s.linkedin_client_id,
                    "client_secret": s.linkedin_client_secret,
                    "redirect_uri": "https://example.com/oauth/linkedin/callback",
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
            scopes=body.get("scope", " ".join(_LI_SCOPES)).split(" "),
        )

    # ---- profile ----
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        resp = asyncio.run(
            _request(
                "GET",
                f"{_LI_API}/v2/me",
                params={"projection": "(id,localizedFirstName,localizedLastName,vanityName)",
            },
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        body = resp.json()
        handle = body.get("vanityName", "") or body.get("id", "")
        display = " ".join(
            filter(None, [body.get("localizedFirstName"), body.get("localizedLastName")])
        ).strip() or handle
        return ChannelProfile(
            channel=self.channel,
            handle=handle,
            display_name=display,
            follower_count=None,
            metadata={"member_id": body.get("id", "")},
        )

    # ---- schema ----
    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": _TEXT_MAX},
                "visibility": {
                    "type": "string",
                    "enum": ["public", "connections"],
                },
                "media_category": {"type": "string"},
                "media_url": {"type": "string"},
                "article_url": {"type": "string"},
                "article_title": {"type": "string"},
                "article_description": {"type": "string"},
            },
            "required": ["text", "visibility"],
        }

    # ---- policy ----
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        blocked: list[str] = []
        warnings: list[str] = []

        text = str(payload.get("text", ""))
        if len(text) > _TEXT_MAX:
            blocked.append(f"text exceeds {_TEXT_MAX} characters")
        if _ENGAGEMENT_BAIT.search(text):
            blocked.append("engagement-bait language detected")

        cg = claims_gate(text)
        if cg.blocked_reasons:
            blocked.extend(cg.blocked_reasons)
        if cg.warnings:
            warnings.extend(cg.warnings)

        # professional tone check: flag excessive emojis (>5 emoji chars).
        emoji_count = len(_EMOJI_RE.findall(text))
        if emoji_count > 5:
            warnings.append(
                f"excessive emojis ({emoji_count}) may breach professional tone"
            )

        return PolicyResult(
            passed=not blocked,
            blocked_reasons=blocked,
            warnings=warnings,
        )

    # ---- publish ----
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        text = str(payload.get("text", ""))
        visibility = payload.get("visibility", "public")
        author = payload.get("_author_urn", "urn:li:person:UNKNOWN")
        body: dict[str, Any] = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": payload.get("media_category", "NONE"),
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": (
                    "PUBLIC" if visibility == "public" else "CONNECTIONS"
                )
            },
        }
        media = body["specificContent"]["com.linkedin.ugc.ShareContent"]
        if payload.get("media_url"):
            media["media"] = [
                {"status": "READY", "mediaUrl": payload["media_url"]}
            ]
        if payload.get("article_url"):
            media["shareMediaCategory"] = "ARTICLE"
            media["media"] = [
                {
                    "status": "READY",
                    "originalUrl": payload["article_url"],
                    "title": {"text": payload.get("article_title", "")},
                    "description": {"text": payload.get("article_description", "")},
                }
            ]
        resp = asyncio.run(
            _request(
                "POST",
                f"{_LI_API}/v2/ugcPosts",
                json_body=body,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        # ugcPosts returns the resource URN in the 'x-restli-id' header / location.
        native_id = resp.headers.get("x-restli-id", "") or resp.headers.get(
            "location", ""
        ).rsplit("/", 1)[-1]
        return PublishedRef(
            channel=self.channel,
            native_id=native_id or "unknown",
            url=None,
            published_at=datetime.now(UTC),
        )

    # ---- metrics ----
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # LinkedIn does not expose per-post organic metrics trivially; we query
        # organizationalEntityShareStatistics when an org URN is present.
        org_urn = ""
        resp = asyncio.run(
            _request(
                "GET",
                f"{_LI_API}/rest/organizationalEntityShareStatistics",
                params={"q": "organizationalEntity", "organizationalEntity": org_urn},
                token=tokens.access_token,
            )
        )
        events: list[MetricEvent] = []
        ts = datetime.now(UTC)
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            totals: dict[str, float] = {}
            for el in elements:
                for key in ("impressionCount", "clickCount", "likeCount", "commentCount"):
                    totals[key] = totals.get(key, 0.0) + float(el.get("totalShareStatistics", {}).get(key, 0))
            metric_map = {
                "impressionCount": "impressions",
                "clickCount": "clicks",
                "likeCount": "likes",
                "commentCount": "comments",
            }
            for k, label in metric_map.items():
                events.append(
                    MetricEvent(
                        channel=self.channel,
                        entity_type="organization",
                        entity_id=org_urn or "self",
                        metric=label,
                        value=totals.get(k, 0.0),
                        ts=ts,
                    )
                )
        return events
