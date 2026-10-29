from __future__ import annotations

import logging
from datetime import UTC
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

from ..registry import register_organic
from .base import ChannelAdapter

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
            "redirect_uri": self.redirect_uri,
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
                    "redirect_uri": self.redirect_uri,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        from datetime import datetime, timedelta

        access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)

        # Exchange short-lived user token for a 60-day long-lived token (same as Facebook).
        try:
            async with httpx.AsyncClient() as client:
                ll = await client.get(
                    f"{IG_GRAPH_BASE}/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": s.meta_app_id,
                        "client_secret": s.meta_app_secret,
                        "fb_exchange_token": access_token,
                    },
                )
                if ll.status_code == 200:
                    ll_data = ll.json()
                    access_token = ll_data.get("access_token", access_token)
                    expires_in = ll_data.get("expires_in", expires_in)
        except Exception:
            pass

        return TokenSet(
            access_token=access_token,
            refresh_token=data.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=IG_SCOPES,
        )

    def refresh_access_token(self, refresh_token: str) -> TokenSet:
        """Exchange an Instagram/Meta user token for a fresh 60-day long-lived token."""
        from datetime import datetime, timedelta

        s = get_settings()
        if not s.meta_app_id or not s.meta_app_secret:
            raise NotImplementedError("META_APP_ID/META_APP_SECRET not configured")
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(
                f"{IG_GRAPH_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": s.meta_app_id,
                    "client_secret": s.meta_app_secret,
                    "fb_exchange_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        access_token = data.get("access_token") or refresh_token
        expires_in = int(data.get("expires_in", 5184000))
        return TokenSet(
            access_token=access_token,
            refresh_token=None,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
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

        chosen_page = pages[0]
        ig_id = ""
        ig_info: dict[str, Any] = {}
        async with httpx.AsyncClient() as client:
            for page in pages:
                resp = await client.get(
                    f"{IG_GRAPH_BASE}/{page['id']}",
                    params={"fields": "instagram_business_account", "access_token": page.get("access_token") or tokens.access_token},
                )
                ig_data = resp.json().get("instagram_business_account", {}) if resp.status_code == 200 else {}
                candidate_ig_id = ig_data.get("id", "")
                if candidate_ig_id:
                    chosen_page = page
                    ig_id = candidate_ig_id
                    resp_info = await client.get(
                        f"{IG_GRAPH_BASE}/{ig_id}",
                        params={"fields": "username,followers_count,media_count", "access_token": page.get("access_token") or tokens.access_token},
                    )
                    if resp_info.status_code == 200:
                        ig_info = resp_info.json()
                    break
        return ChannelProfile(
            channel=self.channel,
            handle=ig_info.get("username", ""),
            display_name=ig_info.get("username", ""),
            follower_count=ig_info.get("followers_count"),
            metadata={
                "ig_id": ig_id,
                "page_id": chosen_page["id"],
                "page_access_token": chosen_page.get("access_token", ""),
            },
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
        import asyncio
        from datetime import datetime

        profile_meta = dict(payload.get("_profile_metadata") or {})
        ig_id = profile_meta.get("ig_id", "")
        if not ig_id:
            try:
                prof = await self.fetch_profile(tokens)
                ig_id = (prof.metadata or {}).get("ig_id", "")
                if (prof.metadata or {}).get("page_access_token"):
                    profile_meta["page_access_token"] = prof.metadata["page_access_token"]
            except Exception:
                pass
        if not ig_id:
            raise ValueError("No instagram_business_account id in profile metadata")
        media_urls = payload.get("media_urls", [])
        if not media_urls:
            raise ValueError("No media_urls in payload")
        auth_token = profile_meta.get("page_access_token") or tokens.access_token
        post_type = payload.get("post_type", "feed")
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Step 1: create container
            if post_type == "carousel" and len(media_urls) > 1:
                children_ids = []
                for url in media_urls:
                    resp = await client.post(
                        f"{IG_GRAPH_BASE}/{ig_id}/media",
                        params={
                            "access_token": auth_token,
                            "is_carousel_item": "true",
                            "image_url": url,
                        },
                    )
                    resp.raise_for_status()
                    children_ids.append(resp.json()["id"])
                resp = await client.post(
                    f"{IG_GRAPH_BASE}/{ig_id}/media",
                    params={
                        "access_token": auth_token,
                        "caption": payload.get("caption", ""),
                        "media_type": "CAROUSEL",
                        "children": ",".join(children_ids),
                    },
                )
            elif post_type == "reels":
                resp = await client.post(
                    f"{IG_GRAPH_BASE}/{ig_id}/media",
                    params={
                        "access_token": auth_token,
                        "caption": payload.get("caption", ""),
                        "media_type": "REELS",
                        "video_url": media_urls[0],
                    },
                )
            else:
                # Single image feed post: Instagram Graph API requires image_url
                # without media_type="feed" (which is not a valid Graph enum).
                resp = await client.post(
                    f"{IG_GRAPH_BASE}/{ig_id}/media",
                    params={
                        "access_token": auth_token,
                        "caption": payload.get("caption", ""),
                        "image_url": media_urls[0],
                    },
                )
            resp.raise_for_status()
            creation_id = resp.json()["id"]
            if post_type == "reels":
                for _ in range(10):
                    st_resp = await client.get(
                        f"{IG_GRAPH_BASE}/{creation_id}",
                        params={"fields": "status_code", "access_token": auth_token},
                    )
                    if st_resp.status_code == 200 and st_resp.json().get("status_code") == "FINISHED":
                        break
                    await asyncio.sleep(2)
            # Step 2: publish
            resp = await client.post(
                f"{IG_GRAPH_BASE}/{ig_id}/media_publish",
                params={"creation_id": creation_id, "access_token": auth_token},
            )
            resp.raise_for_status()
            media_id = resp.json()["id"]
        return PublishedRef(
            channel=self.channel,
            native_id=media_id,
            url=f"https://www.instagram.com/p/{media_id}",
            published_at=datetime.now(UTC),
        )

    async def metrics(self, tokens: TokenSet, since: Any) -> list[MetricEvent]:
        from datetime import datetime

        meta = tokens.metadata or {}
        ig_id = meta.get("ig_id") or "me"
        auth_token = meta.get("page_access_token") or tokens.access_token
        events: list[MetricEvent] = []
        ts = datetime.now(UTC)

        # Pull IG insights: impressions, reach, engagement + media-level likes/comments.
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{IG_GRAPH_BASE}/{ig_id}/insights",
                params={
                    "metric": "impressions,reach,profile_views",
                    "period": "day",
                    "access_token": auth_token,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                for metric_data in data.get("data", []):
                    metric_name = f"ig_{metric_data['name']}"
                    for val in metric_data.get("values", []):
                        events.append(MetricEvent(
                            channel=self.channel,
                            entity_type="profile",
                            entity_id=ig_id,
                            metric=metric_name,
                            value=float(val.get("value", 0)),
                            ts=ts,
                        ))
            if ig_id != "me":
                try:
                    prof_resp = await client.get(
                        f"{IG_GRAPH_BASE}/{ig_id}",
                        params={"fields": "followers_count,media_count", "access_token": auth_token},
                    )
                    if prof_resp.status_code == 200:
                        pdata = prof_resp.json()
                        followers = float(pdata.get("followers_count") or 0)
                        if followers > 0:
                            events.append(MetricEvent(
                                channel=self.channel,
                                entity_type="profile",
                                entity_id=ig_id,
                                metric="followers",
                                value=followers,
                                ts=ts,
                            ))
                    media_resp = await client.get(
                        f"{IG_GRAPH_BASE}/{ig_id}/media",
                        params={"fields": "like_count,comments_count", "limit": "25", "access_token": auth_token},
                    )
                    if media_resp.status_code == 200:
                        items = media_resp.json().get("data", [])
                        likes = sum(float(m.get("like_count", 0)) for m in items)
                        comments = sum(float(m.get("comments_count", 0)) for m in items)
                        if likes > 0:
                            events.append(MetricEvent(channel=self.channel, entity_type="profile", entity_id=ig_id, metric="likes", value=likes, ts=ts))
                        if comments > 0:
                            events.append(MetricEvent(channel=self.channel, entity_type="profile", entity_id=ig_id, metric="comments", value=comments, ts=ts))
                except Exception:
                    pass
        return events
