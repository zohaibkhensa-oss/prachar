"""Channel publish helpers shared by the API publish/schedule endpoints and
the scheduled-publish worker.

Zero platform logic lives outside adapters — this module only builds adapter
inputs (payloads, token state) and invokes ``adapter.publish`` uniformly.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from prachar_shared.contracts import TokenSet


def build_channel_payload(
    channel: str,
    text: str,
    media_url: str | None,
    media_type: str,
    chat_id: str | None,
    metadata: dict[str, Any],
    media_urls: list[str] | None = None,
) -> dict[str, Any]:
    """Map composer inputs to the adapter payload schema.

    Raises ``ValueError`` for unsupported/invalid combinations — callers
    translate to HTTP 400 (API) or task failure (worker)."""
    urls = [u for u in (media_urls or []) if u]
    if not urls and media_url:
        urls = [media_url]
    primary_url = urls[0] if urls else None

    if channel == "facebook":
        payload: dict[str, Any] = {
            "message": text,
            "_page_access_token": metadata.get("page_access_token"),
            "_page_id": metadata.get("page_id"),
        }
        if primary_url:
            payload["picture"] = primary_url
        if len(urls) > 1:
            payload["media_urls"] = urls[:10]
        return payload
    if channel == "x":
        return {"text": text}
    if channel == "linkedin":
        payload = {
            "text": text,
            "_author_urn": f"urn:li:person:{metadata.get('member_id', '')}",
        }
        if primary_url:
            payload["media_url"] = primary_url
        if len(urls) > 1:
            payload["media_urls"] = urls[:9]
        return payload
    if channel == "instagram":
        if not urls:
            raise ValueError("instagram requires an image or video")
        if len(urls) > 10:
            raise ValueError("instagram carousel supports at most 10 items")
        post_type = (
            "reels"
            if media_type == "video"
            else ("carousel" if len(urls) > 1 else "feed")
        )
        return {
            "caption": text,
            "media_urls": urls,
            "post_type": post_type,
            "_profile_metadata": metadata,
        }
    if channel == "youtube":
        if not (primary_url and media_type == "video"):
            raise ValueError("youtube requires a video file")
        return {
            "video_url": primary_url,
            "title": text[:100] or "Untitled",
            "description": text,
            "privacy": "public",
        }
    if channel == "telegram":
        if not chat_id:
            raise ValueError("telegram requires a chat_id")
        return {
            "text": text,
            "chat_id": chat_id,
            "media_type": "photo" if primary_url else "none",
            "media_url": primary_url or "",
        }
    raise ValueError(f"publishing to {channel} is not supported yet")


_REFRESH_WINDOW = timedelta(seconds=30)


def tokens_from_bundle(bundle: dict[str, Any]) -> TokenSet:
    """Build a TokenSet from the decrypted connection bundle."""
    expires_at = (
        datetime.fromisoformat(bundle["expires_at"])
        if bundle.get("expires_at")
        else datetime.now(UTC)
    )
    return TokenSet(
        access_token=bundle["access_token"],
        refresh_token=bundle.get("refresh_token"),
        expires_at=expires_at,
        scopes=bundle.get("scopes") or [],
        metadata=bundle.get("metadata") or {},
    )


def refresh_if_expiring(
    adapter: Any, bundle: dict[str, Any], now: datetime | None = None
) -> tuple[dict[str, Any], bool]:
    """Refresh the access token when it is expired or expiring within 30s.

    Returns ``(bundle, changed)`` — when ``changed`` is True the caller must
    persist the updated bundle (re-encrypted) so the refreshed token is
    reused. Raises ``PermissionError("REAUTH_REQUIRED")`` when the grant is
    dead (refresh failed, or expired with no refresh token)."""
    now = now or datetime.now(UTC)
    expires_at = (
        datetime.fromisoformat(bundle["expires_at"])
        if bundle.get("expires_at")
        else datetime.now(UTC)
    )
    if expires_at > now + _REFRESH_WINDOW:
        return bundle, False
    refresh_token = bundle.get("refresh_token")
    if refresh_token and hasattr(adapter, "refresh_access_token"):
        try:
            new = adapter.refresh_access_token(refresh_token)
        except Exception as exc:
            raise PermissionError("REAUTH_REQUIRED") from exc
        bundle.update(
            {
                "access_token": new.access_token,
                "refresh_token": new.refresh_token or refresh_token,
                "expires_at": new.expires_at.isoformat(),
                "scopes": new.scopes,
            }
        )
        return bundle, True
    if expires_at <= now:
        raise PermissionError("REAUTH_REQUIRED")
    return bundle, False


async def call_adapter_publish(adapter: Any, tokens: TokenSet, payload: dict[str, Any]) -> Any:
    """Invoke ``adapter.publish`` whether it is sync or async."""
    if asyncio.iscoroutinefunction(adapter.publish):
        return await adapter.publish(tokens, payload)
    return await asyncio.to_thread(adapter.publish, tokens, payload)
