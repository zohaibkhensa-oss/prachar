from __future__ import annotations

import asyncio
import base64
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

_PIN_OAUTH_BASE = "https://www.pinterest.com/oauth/"
_PIN_TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
_PIN_API = "https://api.pinterest.com/v5"

_PIN_SCOPES = [
    "boards:read",
    "pins:write",
    "pins:read",
    "user_accounts:read",
]

_MAX_RETRIES = 3
_RETRY_STATUS = {401, 403, 429}

_TITLE_MAX = 100
_DESCRIPTION_MAX = 500


def _has_creds() -> bool:
    s = get_settings()
    return bool(s.pinterest_client_id.strip() and s.pinterest_client_secret.strip())


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
                    "pinterest request retry status=%s attempt=%s url=%s",
                    resp.status_code,
                    attempt,
                    url,
                )
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("pinterest request error attempt=%s: %s", attempt, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(
        f"pinterest request failed after {_MAX_RETRIES} attempts: {last_exc}"
    )


@register_organic
class PinterestAdapter(ChannelAdapter):
    """Pinterest API v5 organic adapter (spec 05)."""

    channel = "pinterest"

    # ---- OAuth ----
    def auth_url(self, state: str) -> str:
        s = get_settings()
        client_id = s.pinterest_client_id or "PINTEREST_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": "https://example.com/oauth/pinterest/callback",
            "response_type": "code",
            "scope": ",".join(_PIN_SCOPES),
            "state": state,
        }
        return f"{_PIN_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        if not _has_creds():
            raise NotImplementedError(
                "Pinterest OAuth exchange requires PINTEREST_CLIENT_ID and "
                "PINTEREST_CLIENT_SECRET in settings."
            )
        s = get_settings()
        basic = base64.b64encode(
            f"{s.pinterest_client_id}:{s.pinterest_client_secret}".encode("utf-8")
        ).decode("ascii")
        resp = asyncio.run(
            _request(
                "POST",
                _PIN_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": "https://example.com/oauth/pinterest/callback",
                },
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        )
        resp.raise_for_status()
        body = resp.json()
        expires_in = int(body.get("expires_in", 2592000))
        return TokenSet(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
            scopes=body.get("scope", ",".join(_PIN_SCOPES)).split(","),
        )

    # ---- profile ----
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        resp = asyncio.run(
            _request(
                "GET",
                f"{_PIN_API}/user_account",
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        body = resp.json()
        return ChannelProfile(
            channel=self.channel,
            handle=body.get("username", "") or body.get("id", ""),
            display_name=body.get("display_name", "") or body.get("username", ""),
            follower_count=body.get("follower_count"),
            metadata={
                "account_type": body.get("account_type", ""),
                "profile_image": body.get("profile_image", ""),
            },
        )

    # ---- schema ----
    def generate_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": _TITLE_MAX},
                "description": {"type": "string", "maxLength": _DESCRIPTION_MAX},
                "board": {"type": "string"},
                "link": {"type": "string"},
                "alt_text": {"type": "string"},
                "image_url": {"type": "string"},
            },
            "required": ["title", "board", "image_url"],
        }

    # ---- policy ----
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        blocked: list[str] = []
        warnings: list[str] = []

        title = str(payload.get("title", ""))
        description = str(payload.get("description", ""))

        if len(title) > _TITLE_MAX:
            blocked.append(f"title exceeds {_TITLE_MAX} characters")
        if len(description) > _DESCRIPTION_MAX:
            blocked.append(f"description exceeds {_DESCRIPTION_MAX} characters")

        for field, label in ((title, "title"), (description, "description")):
            cg = claims_gate(field)
            if cg.blocked_reasons:
                blocked.extend(cg.blocked_reasons)
            if cg.warnings:
                warnings.extend(cg.warnings)

        return PolicyResult(
            passed=not blocked,
            blocked_reasons=blocked,
            warnings=warnings,
        )

    # ---- publish ----
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        board_id = str(payload.get("board", ""))
        if not board_id:
            raise ValueError("pinterest publish payload requires board id")
        image_url = str(payload.get("image_url", ""))
        if not image_url:
            raise ValueError("pinterest publish payload requires image_url")
        body: dict[str, Any] = {
            "board_id": board_id,
            "title": str(payload.get("title", "")),
            "description": str(payload.get("description", "")),
            "media_source": {
                "source_type": "image_url",
                "url": image_url,
            },
        }
        if payload.get("link"):
            body["link"] = str(payload["link"])
        if payload.get("alt_text"):
            body["alt_text"] = str(payload["alt_text"])
        resp = asyncio.run(
            _request(
                "POST",
                f"{_PIN_API}/pins",
                json_body=body,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        data = resp.json()
        pin_id = str(data.get("id", ""))
        return PublishedRef(
            channel=self.channel,
            native_id=pin_id,
            url=f"https://www.pinterest.com/pin/{pin_id}/" if pin_id else None,
            published_at=datetime.now(UTC),
        )

    # ---- metrics ----
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        start = since.strftime("%Y-%m-%d")
        end = datetime.now(UTC).strftime("%Y-%m-%d")
        resp = asyncio.run(
            _request(
                "GET",
                f"{_PIN_API}/user_account/analytics",
                params={
                    "start_date": start,
                    "end_date": end,
                    "metric_types": "IMPRESSION,SAVE,CLICK,CLOSEUP",
                },
                token=tokens.access_token,
            )
        )
        events: list[MetricEvent] = []
        ts = datetime.now(UTC)
        if resp.status_code == 200:
            all_metrics = resp.json().get("all", {})
            metric_map = {
                "IMPRESSION": "impressions",
                "SAVE": "saves",
                "CLICK": "clicks",
                "CLOSEUP": "closeups",
            }
            for k, label in metric_map.items():
                val = 0.0
                bucket = all_metrics.get(k, {})
                if isinstance(bucket, dict):
                    for v in bucket.values():
                        val += float(v or 0)
                events.append(
                    MetricEvent(
                        channel=self.channel,
                        entity_type="account",
                        entity_id="self",
                        metric=label,
                        value=val,
                        ts=ts,
                    )
                )
        return events
