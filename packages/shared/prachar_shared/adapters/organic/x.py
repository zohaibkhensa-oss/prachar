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

_X_OAUTH_BASE = "https://twitter.com/i/oauth2/authorize"
_X_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
_X_API = "https://api.twitter.com/2"

_X_SCOPES = [
    "tweet.read",
    "tweet.write",
    "users.read",
    "offline.access",
]

_MAX_RETRIES = 3
_RETRY_STATUS = {401, 403, 429}

_TEXT_MAX = 280


def _has_creds() -> bool:
    s = get_settings()
    return bool(s.x_client_id.strip() and s.x_client_secret.strip())


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
                    "x request retry status=%s attempt=%s url=%s",
                    resp.status_code,
                    attempt,
                    url,
                )
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("x request error attempt=%s: %s", attempt, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(
        f"x request failed after {_MAX_RETRIES} attempts: {last_exc}"
    )


@register_organic
class XAdapter(ChannelAdapter):
    """X (Twitter) API v2 organic adapter (spec 05)."""

    channel = "x"

    # ---- OAuth ----
    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.x_client_id or "X_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": "https://example.com/oauth/x/callback",
            "response_type": "code",
            "scope": " ".join(_X_SCOPES),
            "state": state,
            "code_challenge": "plain",
            "code_challenge_method": "plain",
        }
        return f"{_X_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        if not _has_creds():
            raise NotImplementedError(
                "X OAuth exchange requires X_CLIENT_ID and X_CLIENT_SECRET in settings."
            )
        s = get_settings()
        resp = asyncio.run(
            _request(
                "POST",
                _X_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "https://example.com/oauth/x/callback",
                    "client_id": s.x_client_id,
                    "code_verifier": "plain",
                },
            )
        )
        resp.raise_for_status()
        body = resp.json()
        expires_in = int(body.get("expires_in", 7200))
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=body.get("scope", " ".join(_X_SCOPES)).split(" "),
        )

    # ---- profile ----
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        resp = asyncio.run(
            _request(
                "GET",
                f"{_X_API}/users/me",
                params={"user.fields": "id,name,username,public_metrics"},
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        body = resp.json().get("data", {})
        metrics = body.get("public_metrics", {})
        return ChannelProfile(
            channel=self.channel,
            handle=body.get("username", "") or body.get("id", ""),
            display_name=body.get("name", "") or body.get("username", ""),
            follower_count=metrics.get("followers_count"),
            metadata={"user_id": body.get("id", "")},
        )

    # ---- schema ----
    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "maxLength": _TEXT_MAX},
                "media_ids": {"type": "array", "items": {"type": "string"}},
                "reply_to_id": {"type": "string"},
                "quote_tweet_id": {"type": "string"},
                "poll": {
                    "type": "object",
                    "properties": {
                        "options": {"type": "array", "items": {"type": "string"}},
                        "duration_minutes": {"type": "integer"},
                    },
                },
            },
            "required": ["text"],
        }

    # ---- policy ----
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        blocked: list[str] = []
        warnings: list[str] = []

        text = str(payload.get("text", ""))
        if len(text) > _TEXT_MAX:
            blocked.append(f"text exceeds {_TEXT_MAX} characters")

        cg = claims_gate(text)
        if cg.blocked_reasons:
            blocked.extend(cg.blocked_reasons)
        if cg.warnings:
            warnings.extend(cg.warnings)

        # duplicate-content heuristic: identical repeated token runs.
        if text and len(text.split()) >= 4:
            tokens_lower = [t.lower() for t in text.split()]
            if len(set(tokens_lower)) == 1 and len(tokens_lower) >= 3:
                blocked.append("duplicate content warning: repeated tokens")

        return PolicyResult(
            passed=not blocked,
            blocked_reasons=blocked,
            warnings=warnings,
        )

    # ---- publish ----
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        body: dict[str, Any] = {"text": str(payload.get("text", ""))}
        media_ids = payload.get("media_ids", [])
        if media_ids:
            body["media"] = {"media_ids": list(media_ids)}
        if payload.get("reply_to_id"):
            body["reply"] = {"in_reply_to_tweet_id": str(payload["reply_to_id"])}
        if payload.get("quote_tweet_id"):
            body["quote_tweet_id"] = str(payload["quote_tweet_id"])
        if payload.get("poll"):
            poll = payload["poll"]
            body["poll"] = {
                "options": poll.get("options", []),
                "duration_minutes": int(poll.get("duration_minutes", 60)),
            }
        resp = asyncio.run(
            _request(
                "POST",
                f"{_X_API}/tweets",
                json_body=body,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        tweet_id = str(data.get("id", ""))
        return PublishedRef(
            channel=self.channel,
            native_id=tweet_id,
            url=f"https://twitter.com/i/web/status/{tweet_id}" if tweet_id else None,
            published_at=datetime.now(UTC),
        )

    # ---- metrics ----
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # X public metrics are returned per-tweet; fetch recent tweets then aggregate.
        resp = asyncio.run(
            _request(
                "GET",
                f"{_X_API}/tweets",
                params={
                    "max_results": 100,
                    "tweet.fields": "public_metrics,created_at",
                    "start_time": since.astimezone(UTC).isoformat(),
                },
                token=tokens.access_token,
            )
        )
        events: list[MetricEvent] = []
        ts = datetime.now(UTC)
        if resp.status_code == 200:
            tweets = resp.json().get("data", [])
            totals = {
                "impressions": 0.0,
                "retweets": 0.0,
                "replies": 0.0,
                "likes": 0.0,
                "profile_clicks": 0.0,
            }
            for t in tweets:
                pm = t.get("public_metrics", {})
                totals["impressions"] += float(pm.get("impression_count", 0))
                totals["retweets"] += float(pm.get("retweet_count", 0))
                totals["replies"] += float(pm.get("reply_count", 0))
                totals["likes"] += float(pm.get("like_count", 0))
                totals["profile_clicks"] += float(pm.get("user_profile_clicks", 0))
            for metric, value in totals.items():
                events.append(
                    MetricEvent(
                        channel=self.channel,
                        entity_type="account",
                        entity_id="self",
                        metric=metric,
                        value=value,
                        ts=ts,
                    )
                )
        return events
