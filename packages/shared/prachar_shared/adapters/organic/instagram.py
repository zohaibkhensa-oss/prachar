from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from prachar_shared.config import get_settings
from prachar_shared.contracts import (
    ChannelProfile,
    MetricEvent,
    PolicyResult,
    PublishedRef,
    TokenSet,
)
from prachar_shared.policy.claims_gate import claims_gate

from .base import ChannelAdapter
from ..registry import register_organic

logger = logging.getLogger(__name__)

IG_GRAPH_BASE = "https://graph.facebook.com/v19.0"
IG_SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "instagram_manage_insights",
    "pages_show_list",
]

# Banned hashtag list (subset — real list maintained per Meta policy updates).
BANNED_HASHTAGS = {
    "#like4like", "#follow4follow", "#likeforlike", "#followforfollow",
    "#like4likes", "#follow4likes", "#likesforlikes",
}


@register_organic
class InstagramAdapter(ChannelAdapter):
    channel = "instagram"

    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.meta_app_id or "PLACEHOLDER"
        params = urlencode({
            "client_id": client_id,
            "redirect_uri": f"https://example.com/oauth/instagram/callback",
            "scope": ",".join(IG_SCOPES),
            "response_type": "code",
            "state": state,
        })
        return f"https://www.facebook.com/v19.0/dialog/oauth?{params}"

    async def exchange_code(self, code: str) -> TokenSet:
        s = get_settings()
        if not s.meta_app_id or not s.meta_app_secret:
            raise NotImplementedError("META_APP_ID/META_APP_SECRET not configured")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{IG_GRAPH_BASE}/oauth/access_token",
                data={
                    "client_id": s.meta_app_id,
                    "client_secret": s.meta_app_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "https://example.com/oauth/instagram/callback",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        from datetime import datetime, timedelta, timezone

        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600)),
            scopes=IG_SCOPES,
        )

    async def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{IG_GRAPH_BASE}/me/accounts",
                params={"access_token": tokens.access_token},
            )
            resp.raise_for_status()
            data = resp.json()
        pages = data.get("data", [])
        if not pages:
            return ChannelProfile(channel=self.channel, handle="", display_name="")
        page = pages[0]
        # Get IG business account for the page.
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{IG_GRAPH_BASE}/{page['id']}",
                params={"fields": "instagram_business_account", "access_token": tokens.access_token},
            )
            ig_data = resp.json().get("instagram_business_account", {})
            ig_id = ig_data.get("id", "")
            if ig_id:
                resp = await client.get(
                    f"{IG_GRAPH_BASE}/{ig_id}",
                    params={"fields": "username,followers_count,media_count", "access_token": tokens.access_token},
                )
                ig_info = resp.json()
            else:
                ig_info = {}
        return ChannelProfile(
            channel=self.channel,
            handle=ig_info.get("username", ""),
            display_name=ig_info.get("username", ""),
            follower_count=ig_info.get("followers_count"),
            metadata={"ig_id": ig_id, "page_id": page["id"]},
        )

    def generate_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "caption": {"type": "string", "maxLength": 2200},
                "hashtag_sets": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
                "first_comment_hashtags": {"type": "boolean"},
                "alt_text": {"type": "string"},
                "post_type": {"type": "string", "enum": ["feed", "reels", "carousel"]},
                "schedule_at": {"type": "string", "format": "date-time"},
                "media_urls": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["caption", "post_type", "media_urls"],
        }

    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        caption = payload.get("caption", "")
        result = claims_gate(caption)
        # Hashtag count sanity: max 30 per set.
        for hs in payload.get("hashtag_sets", []):
            if len(hs) > 30:
                result.warnings.append(f"Hashtag set has {len(hs)} tags (max 30)")
        # Check banned hashtags.
        all_tags = []
        for hs in payload.get("hashtag_sets", []):
            all_tags.extend(hs)
        for tag in all_tags:
            if tag.lower() in BANNED_HASHTAGS:
                result.blocked_reasons.append(f"Banned hashtag: {tag}")
        if len(caption) > 2200:
            result.blocked_reasons.append("Caption exceeds 2200 characters")
        result.passed = len(result.blocked_reasons) == 0
        return result

    async def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        # Two-step IG publishing: create media container, then publish.
        from datetime import datetime, timezone

        profile_meta = payload.get("_profile_metadata", {})
        ig_id = profile_meta.get("ig_id", "")
        if not ig_id:
            raise ValueError("No instagram_business_account id in profile metadata")
        media_urls = payload.get("media_urls", [])
        if not media_urls:
            raise ValueError("No media_urls in payload")
        async with httpx.AsyncClient() as client:
            # Step 1: create container
            container_params = {
                "access_token": tokens.access_token,
                "caption": payload.get("caption", ""),
                "media_type": payload.get("post_type", "feed"),
            }
            if payload.get("post_type") == "carousel" and len(media_urls) > 1:
                children_ids = []
                for url in media_urls:
                    resp = await client.post(
                        f"{IG_GRAPH_BASE}/{ig_id}/media",
                        params={**container_params, "media_type": "FEED", "image_url": url},
                    )
                    resp.raise_for_status()
                    children_ids.append(resp.json()["id"])
                resp = await client.post(
                    f"{IG_GRAPH_BASE}/{ig_id}/media",
                    params={**container_params, "media_type": "CAROUSEL", "children": ",".join(children_ids)},
                )
            else:
                container_params["image_url"] = media_urls[0]
                resp = await client.post(f"{IG_GRAPH_BASE}/{ig_id}/media", params=container_params)
            resp.raise_for_status()
            creation_id = resp.json()["id"]
            # Step 2: publish
            resp = await client.post(
                f"{IG_GRAPH_BASE}/{ig_id}/media_publish",
                params={"creation_id": creation_id, "access_token": tokens.access_token},
            )
            resp.raise_for_status()
            media_id = resp.json()["id"]
        return PublishedRef(
            channel=self.channel,
            native_id=media_id,
            url=f"https://www.instagram.com/p/{media_id}",
            published_at=datetime.now(timezone.utc),
        )

    async def metrics(self, tokens: TokenSet, since: Any) -> list[MetricEvent]:
        from datetime import datetime, timezone

        # Pull IG insights: impressions, reach, engagement.
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{IG_GRAPH_BASE}/me/insights",
                params={
                    "metric": "impressions,reach,profile_views",
                    "period": "day",
                    "access_token": tokens.access_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        events = []
        ts = datetime.now(timezone.utc)
        for metric_data in data.get("data", []):
            metric_name = f"ig_{metric_data['name']}"
            for val in metric_data.get("values", []):
                events.append(MetricEvent(
                    channel=self.channel,
                    entity_type="profile",
                    entity_id="self",
                    metric=metric_name,
                    value=float(val.get("value", 0)),
                    ts=ts,
                ))
        return events
