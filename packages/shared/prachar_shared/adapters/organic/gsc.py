from __future__ import annotations

import asyncio
import logging
import time
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

_GSC_OAUTH_BASE = "https://accounts.google.com/o/oauth2/v2/auth"
_GSC_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
_GSC_SEARCH_ANALYTICS_URL = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
_GSC_URL_INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"

_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters"
_MAX_RETRIES = 3
_RETRY_STATUS = {401, 403, 429}

_TITLE_MAX = 60
_META_MAX = 155


def _settings():
    from ...config import get_settings

    return get_settings()


def _has_creds() -> bool:
    s = _settings()
    return bool(s.gsc_client_id.strip() and s.gsc_client_secret.strip())


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
                    "gsc request retry status=%s attempt=%s url=%s",
                    resp.status_code,
                    attempt,
                    url,
                )
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            return resp
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("gsc request error attempt=%s: %s", attempt, exc)
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"gsc request failed after {_MAX_RETRIES} attempts: {last_exc}")


@register_organic
class GSCAdapter(ChannelAdapter):
    """Google Search Console organic adapter (spec 05)."""

    channel = "gsc"

    # ---- OAuth ----
    def auth_url(self, state: str) -> str:
        s = _settings()
        client_id = s.gsc_client_id or "GSC_CLIENT_ID_PLACEHOLDER"
        params = {
            "client_id": client_id,
            "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            "response_type": "code",
            "scope": _GSC_SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_GSC_OAUTH_BASE}?{urlencode(params)}"

    def exchange_code(self, code: str) -> TokenSet:
        if not _has_creds():
            raise NotImplementedError(
                "GSC OAuth exchange requires GSC_CLIENT_ID and GSC_CLIENT_SECRET in settings."
            )
        s = _settings()
        resp = asyncio.run(
            _request(
                "POST",
                _GSC_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": s.gsc_client_id,
                    "client_secret": s.gsc_client_secret,
                    "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
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
            scopes=body.get("scope", _GSC_SCOPE).split(" "),
        )

    # ---- profile ----
    def fetch_profile(self, tokens: TokenSet) -> ChannelProfile:
        resp = asyncio.run(
            _request("GET", _GSC_SITES_URL, token=tokens.access_token)
        )
        resp.raise_for_status()
        body = resp.json()
        sites = [e.get("siteUrl", "") for e in body.get("siteEntry", [])]
        handle = sites[0] if sites else "no-sites"
        return ChannelProfile(
            channel=self.channel,
            handle=handle,
            display_name=handle,
            metadata={"verified_sites": sites},
        )

    # ---- schema ----
    def generate_schema(self) -> dict[str, Any]:
        """JSON schema for a GSC/page content item (spec 05)."""
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": _TITLE_MAX},
                "meta": {"type": "string", "maxLength": _META_MAX},
                "h_structure": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "schema_org": {"type": "object"},
                "internal_links": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "faq": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["title", "meta", "h_structure", "schema_org", "internal_links", "faq"],
        }

    # ---- policy ----
    def policy_gate(self, payload: dict[str, Any]) -> PolicyResult:
        blocked: list[str] = []
        warnings: list[str] = []

        title = str(payload.get("title", ""))
        meta = str(payload.get("meta", ""))
        if len(title) > _TITLE_MAX:
            blocked.append(f"title too long: {len(title)} > {_TITLE_MAX}")
        if len(meta) > _META_MAX:
            blocked.append(f"meta too long: {len(meta)} > {_META_MAX}")

        # claims_gate over title + meta (no misleading metadata).
        for field in (title, meta):
            cg = claims_gate(field)
            if cg.blocked_reasons:
                blocked.extend(cg.blocked_reasons)
            if cg.warnings:
                warnings.extend(cg.warnings)

        # misleading metadata: title must not be empty / all caps clickbait.
        if title and title.isupper():
            warnings.append("title is all-caps (possible misleading metadata)")

        return PolicyResult(
            passed=not blocked,
            blocked_reasons=blocked,
            warnings=warnings,
        )

    # ---- publish ----
    def publish(self, tokens: TokenSet, payload: dict[str, Any]) -> PublishedRef:
        url = str(payload.get("url") or payload.get("title") or "")
        body = {
            "inspectionUrl": url,
            "siteUrl": payload.get("site_url", url),
            "language": "en-US",
            "category": payload.get("category", "default"),
        }
        resp = asyncio.run(
            _request(
                "POST",
                _GSC_URL_INSPECTION_URL,
                json_body=body,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        native_id = str(int(time.time()))
        return PublishedRef(
            channel=self.channel,
            native_id=native_id,
            url=url,
            published_at=datetime.now(UTC),
        )

    # ---- metrics ----
    def metrics(self, tokens: TokenSet, since: datetime) -> list[MetricEvent]:
        site = "sc-domain:example.com"
        body = {
            "startDate": since.date().isoformat(),
            "endDate": datetime.now(UTC).date().isoformat(),
            "dimensions": ["query"],
            "rowLimit": 100,
        }
        resp = asyncio.run(
            _request(
                "POST",
                _GSC_SEARCH_ANALYTICS_URL.format(site=site),
                json_body=body,
                token=tokens.access_token,
            )
        )
        resp.raise_for_status()
        data = resp.json()
        events: list[MetricEvent] = []
        for row in data.get("rows", []):
            keys = row.get("keys", [])
            query = keys[0] if keys else ""
            events.append(
                MetricEvent(
                    channel=self.channel,
                    entity_type="query",
                    entity_id=query,
                    metric="impressions",
                    value=float(row.get("impressions", 0)),
                )
            )
            events.append(
                MetricEvent(
                    channel=self.channel,
                    entity_type="query",
                    entity_id=query,
                    metric="ctr",
                    value=float(row.get("ctr", 0)),
                )
            )
            events.append(
                MetricEvent(
                    channel=self.channel,
                    entity_type="query",
                    entity_id=query,
                    metric="position",
                    value=float(row.get("position", 0)),
                )
            )
        return events
