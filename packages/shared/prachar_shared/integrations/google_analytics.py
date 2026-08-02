"""Google Analytics 4 (GA4) Integration.

World-class analytics integration:
- Authenticate via OAuth 2.0 (Google)
- Pull page views, sessions, conversions, engagement metrics
- Real-time active users
- Conversion attribution to campaigns/channels
- Feed Performance Advisor with real data

API: Google Analytics Data API v1beta
Docs: https://developers.google.com/analytics/devguides/reporting/data/v1
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..contracts import MetricEvent, TokenSet
from .base import (
    IntegrationCapability,
    IntegrationInfo,
    IntegrationStatus,
    MarketingIntegration,
    register_integration,
)

log = logging.getLogger("prachar.integrations.ga4")

# Google OAuth endpoints
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

# GA4 Data API endpoint
GA4_DATA_API = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport"
GA4_REALTIME_API = "https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runRealtimeReport"

# Required OAuth scopes
GA4_SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
]


@register_integration
class GoogleAnalytics4(MarketingIntegration):
    """Google Analytics 4 integration — pull metrics and attribute conversions."""

    integration_name = "google_analytics"
    integration_display_name = "Google Analytics 4"

    @classmethod
    def info(cls) -> IntegrationInfo:
        return IntegrationInfo(
            name="google_analytics",
            display_name="Google Analytics 4",
            category="analytics",
            icon="📊",
            description="Connect Google Analytics 4 to measure campaign performance, attribute conversions, and feed real data to the Performance Advisor.",
            capabilities=(
                IntegrationCapability.AUTHENTICATE
                | IntegrationCapability.READ_METRICS
                | IntegrationCapability.ATTRIBUTION
            ),
            auth_type="oauth",
            scopes=GA4_SCOPES,
            docs_url="https://developers.google.com/analytics/devguides/reporting/data/v1",
            setup_guide="1. Go to Google Cloud Console → APIs → enable Google Analytics Data API. 2. Create OAuth credentials. 3. Set redirect URI. 4. Connect.",
        )

    def auth_url(self, state: str, client_id: str, redirect_uri: str) -> str:
        """Generate the OAuth authorization URL."""
        from urllib.parse import urlencode

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GA4_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    def authenticate(self, **kwargs: Any) -> TokenSet:
        """Exchange OAuth code for tokens.

        Required kwargs:
            code: OAuth authorization code
            client_id: Google OAuth client ID
            client_secret: Google OAuth client secret
            redirect_uri: OAuth redirect URI
        """
        code = kwargs.get("code", "")
        client_id = kwargs.get("client_id", "")
        client_secret = kwargs.get("client_secret", "")
        redirect_uri = kwargs.get("redirect_uri", "")

        if not code:
            raise ValueError("OAuth code is required")

        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            scopes=GA4_SCOPES,
        )

    def refresh_token(self, refresh_token: str, client_id: str, client_secret: str) -> TokenSet:
        """Refresh an expired access token."""
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=data.get("expires_in", 3600))
        return TokenSet(
            access_token=data["access_token"],
            refresh_token=refresh_token,
            expires_at=expires_at,
            scopes=GA4_SCOPES,
        )

    def test_connection(self, tokens: TokenSet) -> bool:
        """Test if the connection is valid by listing account summaries."""
        try:
            resp = httpx.get(
                "https://analyticsadmin.googleapis.com/v1beta/accountSummaries",
                headers={"Authorization": f"Bearer {tokens.access_token}"},
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def list_properties(self, tokens: TokenSet) -> list[dict[str, Any]]:
        """List available GA4 properties for this account."""
        resp = httpx.get(
            "https://analyticsadmin.googleapis.com/v1beta/properties",
            headers={"Authorization": f"Bearer {tokens.access_token}"},
            params={"pageSize": "100"},
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "property_id": p.get("name", "").split("/")[-1],
                "display_name": p.get("displayName", ""),
                "property_type": p.get("propertyType", ""),
                "currency_code": p.get("currencyCode", ""),
                "time_zone": p.get("timeZone", ""),
            }
            for p in data.get("properties", [])
        ]

    def fetch_metrics(
        self,
        tokens: TokenSet,
        since: datetime,
        until: datetime | None = None,
        property_id: str = "",
        **kwargs: Any,
    ) -> list[MetricEvent]:
        """Pull core metrics from GA4.

        Returns MetricEvents for: sessions, totalUsers, screenPageViews,
        conversions, engagementRate, averageSessionDuration.
        """
        if not property_id:
            raise ValueError("property_id is required for GA4 metrics")

        until = until or datetime.now(timezone.utc)

        # Build the GA4 report request
        request = {
            "dateRanges": [
                {
                    "startDate": since.strftime("%Y-%m-%d"),
                    "endDate": until.strftime("%Y-%m-%d"),
                }
            ],
            "metrics": [
                {"name": "sessions"},
                {"name": "totalUsers"},
                {"name": "screenPageViews"},
                {"name": "conversions"},
                {"name": "engagementRate"},
                {"name": "averageSessionDuration"},
                {"name": "bounceRate"},
            ],
            "dimensions": [
                {"name": "date"},
                {"name": "sessionDefaultChannelGroup"},
            ],
        }

        url = GA4_DATA_API.format(property_id=property_id)
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {tokens.access_token}",
                "Content-Type": "application/json",
            },
            json=request,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Convert GA4 rows to MetricEvents
        metrics: list[MetricEvent] = []
        dimension_headers = [d["name"] for d in data.get("dimensionHeaders", [])]
        metric_headers = [m["name"] for m in data.get("metricHeaders", [])]

        for row in data.get("rows", []):
            dim_values = {dimension_headers[i]: row["dimensionValues"][i]["value"]
                          for i in range(len(dimension_headers))}
            met_values = {}
            for i, header in enumerate(metric_headers):
                val = row["metricValues"][i]["value"]
                try:
                    met_values[header] = float(val)
                except (ValueError, TypeError):
                    met_values[header] = 0.0

            date_str = dim_values.get("date", "")
            try:
                event_time = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                event_time = datetime.now(timezone.utc)

            channel = dim_values.get("sessionDefaultChannelGroup", "Unknown")

            for metric_name, value in met_values.items():
                metrics.append(MetricEvent(
                    channel=f"ga4:{channel}",
                    metric=metric_name,
                    value=value,
                    timestamp=event_time,
                    metadata={"property_id": property_id, "date": date_str},
                ))

        return metrics

    def fetch_realtime(
        self,
        tokens: TokenSet,
        property_id: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Pull real-time data: active users, top pages, traffic sources."""
        if not property_id:
            raise ValueError("property_id is required for realtime data")

        request = {
            "metrics": [
                {"name": "activeUsers"},
                {"name": "screenPageViews"},
            ],
            "dimensions": [
                {"name": "unifiedScreenName"},
                {"name": "sessionMedium"},
                {"name": "country"},
            ],
            "limit": 50,
        }

        url = GA4_REALTIME_API.format(property_id=property_id)
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {tokens.access_token}",
                "Content-Type": "application/json",
            },
            json=request,
            timeout=15.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Aggregate
        total_active = 0
        total_pageviews = 0
        top_pages: list[dict[str, Any]] = []
        traffic_sources: dict[str, int] = {}

        for row in data.get("rows", []):
            dim_values = row.get("dimensionValues", [])
            met_values = row.get("metricValues", [])

            page = dim_values[0]["value"] if dim_values else "Unknown"
            medium = dim_values[1]["value"] if len(dim_values) > 1 else "Unknown"
            country = dim_values[2]["value"] if len(dim_values) > 2 else "Unknown"

            active = int(float(met_values[0]["value"])) if met_values else 0
            pageviews = int(float(met_values[1]["value"])) if len(met_values) > 1 else 0

            total_active += active
            total_pageviews += pageviews
            traffic_sources[medium] = traffic_sources.get(medium, 0) + active

            top_pages.append({
                "page": page,
                "active_users": active,
                "pageviews": pageviews,
                "country": country,
            })

        return {
            "active_users": total_active,
            "pageviews": total_pageviews,
            "top_pages": top_pages[:10],
            "traffic_sources": dict(sorted(traffic_sources.items(), key=lambda x: x[1], reverse=True)),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def attribute_conversions(
        self,
        tokens: TokenSet,
        since: datetime,
        property_id: str = "",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Attribute conversions to campaigns and channels.

        Pulls conversion data broken down by session source/medium/campaign
        and returns attribution records.
        """
        if not property_id:
            raise ValueError("property_id is required for attribution")

        until = kwargs.get("until", datetime.now(timezone.utc))

        request = {
            "dateRanges": [
                {
                    "startDate": since.strftime("%Y-%m-%d"),
                    "endDate": until.strftime("%Y-%m-%d"),
                }
            ],
            "metrics": [
                {"name": "conversions"},
                {"name": "totalRevenue"},
                {"name": "sessions"},
            ],
            "dimensions": [
                {"name": "sessionSource"},
                {"name": "sessionMedium"},
                {"name": "sessionCampaignName"},
                {"name": "sessionDefaultChannelGroup"},
            ],
        }

        url = GA4_DATA_API.format(property_id=property_id)
        resp = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {tokens.access_token}",
                "Content-Type": "application/json",
            },
            json=request,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        dimension_headers = [d["name"] for d in data.get("dimensionHeaders", [])]
        metric_headers = [m["name"] for m in data.get("metricHeaders", [])]

        conversions: list[dict[str, Any]] = []
        for row in data.get("rows", []):
            dim_values = {dimension_headers[i]: row["dimensionValues"][i]["value"]
                          for i in range(len(dimension_headers))}
            met_values = {}
            for i, header in enumerate(metric_headers):
                val = row["metricValues"][i]["value"]
                try:
                    met_values[header] = float(val)
                except (ValueError, TypeError):
                    met_values[header] = 0.0

            conversions.append({
                "source": dim_values.get("sessionSource", ""),
                "medium": dim_values.get("sessionMedium", ""),
                "campaign": dim_values.get("sessionCampaignName", ""),
                "channel_group": dim_values.get("sessionDefaultChannelGroup", ""),
                "conversions": int(met_values.get("conversions", 0)),
                "revenue": met_values.get("totalRevenue", 0),
                "sessions": int(met_values.get("sessions", 0)),
                "conversion_rate": (
                    met_values.get("conversions", 0) / met_values.get("sessions", 1) * 100
                    if met_values.get("sessions", 0) > 0 else 0
                ),
            })

        return conversions
