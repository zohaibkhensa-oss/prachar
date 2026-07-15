from __future__ import annotations

import logging
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

_REDDIT_API_BASE = "https://oauth.reddit.com"
_REDDIT_OAUTH_BASE = "https://www.reddit.com/api/v1/authorize"
_REDDIT_TITLE_MAX = 300

# Naive promotional spam detection.
_PROMO_PATTERNS = ["buy now", "click here", "limited time offer", "act now", "discount code"]


@register_organic
class RedditAdapter(ChannelAdapter):
    """Reddit Data API adapter (spec 05 — never auto-publish; human approve queue)."""

    channel = "reddit"

    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.reddit_client_id or "PLACEHOLDER"
        params = urlencode({
            "client_id": client_id,
            "response_type": "code",
            "state": state,
            "redirect_uri": "https://example.com/oauth/reddit/callback",
            "duration": "permanent",
            "scope": "submit,read,identity",
        })
        return f"{_REDDIT_OAUTH_BASE}?{params}"

    def exchange_code(self, code: str) -> TokenSet:
        s = get_settings()
        if not s.reddit_client_id or not s.reddit_client_secret:
            raise NotImplementedError("REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET not configured")
        return TokenSet(
            access_token=code,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=["submit", "read", "identity"],
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_REDDIT_API_BASE}/api/v1/me",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
        return ChannelProfile(
            channel=self.channel,
            handle=str(data.get("name", "")),
            display_name=str(data.get("name", "")),
            follower_count=data.get("total_karma"),
            metadata={"user_id": data.get("id")},
        )

    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "subreddit": {"type": "string"},
                "title": {"type": "string", "maxLength": _REDDIT_TITLE_MAX},
                "kind": {"type": "string", "enum": ["link", "self", "image"]},
                "text": {"type": "string"},
                "url": {"type": "string"},
                "flair_id": {"type": "string"},
                "nsfw": {"type": "boolean"},
                "spoiler": {"type": "boolean"},
            },
            "required": ["subreddit", "title", "kind"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        # REDDIT-SPECIFIC: never auto-publish (spec 05: generate -> human approve queue).
        # policy_gate always returns passed=False with a warning to force the queue.
        title = payload.get("title", "")
        text = f"{title} {payload.get('text', '')}"
        result = claims_gate(text)
        # Always block auto-publish.
        result.passed = False
        result.warnings.append("Reddit requires human approval")
        # Promotional spam detection.
        text_lower = text.lower()
        for pat in _PROMO_PATTERNS:
            if pat in text_lower:
                result.blocked_reasons.append(f"Promotional spam pattern: {pat!r}")
        if len(title) > _REDDIT_TITLE_MAX:
            result.blocked_reasons.append(f"Title exceeds {_REDDIT_TITLE_MAX} characters")
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        # Wrap with a check that _force_publish must be True (human-approved).
        if not payload.get("_force_publish"):
            raise PermissionError(
                "Reddit posts require human approval; set payload['_force_publish'=True] to publish"
            )
        body: dict[str, Any] = {
            "sr": payload["subreddit"],
            "title": payload["title"],
            "kind": payload["kind"],
            "api_type": "json",
        }
        if payload["kind"] == "self":
            body["text"] = payload.get("text", "")
        else:
            body["url"] = payload.get("url", "")
        if payload.get("flair_id"):
            body["flair_id"] = payload["flair_id"]
        if payload.get("nsfw"):
            body["nsfw"] = True
        if payload.get("spoiler"):
            body["spoiler"] = True
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_REDDIT_API_BASE}/api/submit",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                data=body,
            )
            resp.raise_for_status()
            data = resp.json().get("json", {}).get("data", {})
        post_id = str(data.get("id", ""))
        subreddit = str(payload["subreddit"])
        return PublishedRef(
            channel=self.channel,
            native_id=post_id,
            url=f"https://www.reddit.com/r/{subreddit}/comments/{post_id}",
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        # Reddit offers upvotes, comments, views via the post endpoint.
        events: list[MetricEvent] = []
        post_id = "0"  # caller injects target in production
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_REDDIT_API_BASE}/api/info",
                params={"id": f"t3_{post_id}"},
                headers={"Authorization": f"Bearer {tokens.access_token}"},
            )
            if resp.status_code == 200:
                children = resp.json().get("data", {}).get("children", [])
                if children:
                    d = children[0].get("data", {})
                    for metric in ("ups", "num_comments"):
                        events.append(
                            MetricEvent(
                                channel=self.channel,
                                entity_type="post",
                                entity_id=post_id,
                                metric="upvotes" if metric == "ups" else "comments",
                                value=float(d.get(metric, 0)),
                                ts=datetime.now(UTC),
                            )
                        )
        return events
