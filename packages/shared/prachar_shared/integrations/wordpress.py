"""WordPress Integration — publish blogs, landing pages, and manage SEO.

World-class CMS integration:
- Authenticate via Application Password (WordPress REST API)
- Publish blog posts with full content
- Create/update landing pages
- Update SEO metadata (Yoast/RankMath compatible)
- Upload and manage media
- Pull existing pages/posts

API: WordPress REST API (wp-json/wp/v2)
Docs: https://developer.wordpress.org/rest-api/
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..contracts import MetricEvent, TokenSet
from .base import (
    IntegrationCapability,
    IntegrationInfo,
    MarketingIntegration,
    register_integration,
)

log = logging.getLogger("prachar.integrations.wordpress")


@register_integration
class WordPress(MarketingIntegration):
    """WordPress integration — publish content and manage SEO."""

    integration_name = "wordpress"
    integration_display_name = "WordPress"

    @classmethod
    def info(cls) -> IntegrationInfo:
        return IntegrationInfo(
            name="wordpress",
            display_name="WordPress",
            category="cms",
            icon="📝",
            description="Connect WordPress to publish blog posts, create landing pages, update SEO metadata, and manage media — all from CURV AI.",
            capabilities=(
                IntegrationCapability.AUTHENTICATE
                | IntegrationCapability.PUBLISH
                | IntegrationCapability.SYNC_ASSETS
                | IntegrationCapability.MANAGE_MEDIA
                | IntegrationCapability.SEO_MANAGEMENT
            ),
            auth_type="app_password",
            scopes=["read", "write", "upload"],
            docs_url="https://developer.wordpress.org/rest-api/",
            setup_guide="1. Log in to WordPress Admin. 2. Go to Users → Profile → Application Passwords. 3. Create a new application password. 4. Enter your site URL, username, and the generated password.",
        )

    def authenticate(self, **kwargs: Any) -> TokenSet:
        """Authenticate with WordPress using Application Password.

        Required kwargs:
            site_url: WordPress site URL (e.g. https://example.com)
            username: WordPress username
            app_password: Application Password (from WordPress Admin)
        """
        site_url = kwargs.get("site_url", "").rstrip("/")
        username = kwargs.get("username", "")
        app_password = kwargs.get("app_password", "")

        if not site_url or not username or not app_password:
            raise ValueError("site_url, username, and app_password are required")

        # Test the credentials by fetching the current user
        credentials = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        resp = httpx.get(
            f"{site_url}/wp-json/wp/v2/users/me",
            headers={"Authorization": f"Basic {credentials}"},
            timeout=15.0,
        )

        if resp.status_code != 200:
            raise ValueError(f"WordPress authentication failed: {resp.status_code}")

        # Store the encoded credentials as the access token
        expires_at = datetime.now(timezone.utc) + timedelta(days=365)  # App passwords don't expire
        return TokenSet(
            access_token=credentials,
            refresh_token=None,
            expires_at=expires_at,
            scopes=["read", "write", "upload"],
        )

    def test_connection(self, tokens: TokenSet) -> bool:
        """Test if the WordPress connection is valid."""
        try:
            site_url = self._get_site_url(tokens)
            resp = httpx.get(
                f"{site_url}/wp-json/wp/v2/users/me",
                headers={"Authorization": f"Basic {tokens.access_token}"},
                timeout=15.0,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _get_site_url(self, tokens: TokenSet) -> str:
        """Extract site URL from token metadata."""
        # The site URL is stored in the token scopes or metadata
        # In production, this would be stored in the Connection record
        return getattr(tokens, "_site_url", "https://example.com").rstrip("/")

    def _headers(self, tokens: TokenSet) -> dict[str, str]:
        return {
            "Authorization": f"Basic {tokens.access_token}",
            "Content-Type": "application/json",
        }

    def fetch_assets(
        self,
        tokens: TokenSet,
        asset_type: str = "posts",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Pull existing posts or pages from WordPress.

        Args:
            asset_type: "posts" | "pages" | "categories" | "tags"
        """
        site_url = self._get_site_url(tokens)
        endpoint = f"wp-json/wp/v2/{asset_type}"
        params = {"per_page": 50, "orderby": "date", "order": "desc"}
        if asset_type in ("categories", "tags"):
            params = {"per_page": 100}

        resp = httpx.get(
            f"{site_url}/{endpoint}",
            headers=self._headers(tokens),
            params=params,
            timeout=30.0,
        )
        resp.raise_for_status()
        items = resp.json()

        if asset_type in ("posts", "pages"):
            return [
                {
                    "id": item.get("id"),
                    "title": item.get("title", {}).get("rendered", ""),
                    "slug": item.get("slug", ""),
                    "status": item.get("status", ""),
                    "date": item.get("date", ""),
                    "modified": item.get("modified", ""),
                    "link": item.get("link", ""),
                    "excerpt": item.get("excerpt", {}).get("rendered", ""),
                    "categories": item.get("categories", []),
                    "tags": item.get("tags", []),
                    "featured_media": item.get("featured_media", 0),
                    "seo": {
                        "yoast_title": item.get("yoast_head_json", {}).get("title", ""),
                        "yoast_meta": item.get("yoast_head_json", {}).get("description", ""),
                        "yoast_schema": item.get("yoast_head_json", {}).get("schema", {}),
                    } if item.get("yoast_head_json") else {},
                }
                for item in items
            ]
        else:
            return [
                {
                    "id": item.get("id"),
                    "name": item.get("name", ""),
                    "slug": item.get("slug", ""),
                    "count": item.get("count", 0),
                }
                for item in items
            ]

    def publish(
        self,
        tokens: TokenSet,
        payload: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Publish a blog post or page to WordPress.

        Required payload:
            title: Post title
            content: Post content (HTML)
            type: "post" (default) or "page"

        Optional payload:
            status: "draft" | "publish" | "private" (default: "draft")
            slug: URL slug
            excerpt: Short excerpt
            categories: list of category IDs
            tags: list of tag IDs
            featured_media: media ID
            seo: {title, meta_description, focus_keyword, schema}
        """
        site_url = self._get_site_url(tokens)
        post_type = payload.get("type", "post")
        endpoint = "wp-json/wp/v2/posts" if post_type == "post" else "wp-json/wp/v2/pages"

        # Build the post data
        post_data: dict[str, Any] = {
            "title": payload.get("title", ""),
            "content": payload.get("content", ""),
            "status": payload.get("status", "draft"),
        }

        if "slug" in payload:
            post_data["slug"] = payload["slug"]
        if "excerpt" in payload:
            post_data["excerpt"] = payload["excerpt"]
        if "categories" in payload:
            post_data["categories"] = payload["categories"]
        if "tags" in payload:
            post_data["tags"] = payload["tags"]
        if "featured_media" in payload:
            post_data["featured_media"] = payload["featured_media"]

        # Add SEO data (Yoast/RankMath compatible)
        seo = payload.get("seo", {})
        if seo:
            if seo.get("title"):
                post_data["yoast_head_json"] = {
                    "title": seo["title"],
                    "description": seo.get("meta_description", ""),
                }

        # Check if updating or creating
        post_id = payload.get("id")
        if post_id:
            # Update existing post
            resp = httpx.post(
                f"{site_url}/{endpoint}/{post_id}",
                headers=self._headers(tokens),
                json=post_data,
                timeout=30.0,
            )
        else:
            # Create new post
            resp = httpx.post(
                f"{site_url}/{endpoint}",
                headers=self._headers(tokens),
                json=post_data,
                timeout=30.0,
            )

        resp.raise_for_status()
        result = resp.json()

        return {
            "native_id": str(result.get("id", "")),
            "url": result.get("link", ""),
            "published_at": result.get("date", datetime.now(timezone.utc).isoformat()),
            "status": result.get("status", ""),
            "slug": result.get("slug", ""),
        }

    def manage_media(
        self,
        tokens: TokenSet,
        action: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Upload, list, or delete media files.

        Args:
            action: "upload" | "list" | "delete"

        For "upload":
            kwargs: file_bytes, filename, content_type
        For "list":
            kwargs: per_page (default 20)
        For "delete":
            kwargs: media_id
        """
        site_url = self._get_site_url(tokens)

        if action == "upload":
            file_bytes = kwargs.get("file_bytes")
            filename = kwargs.get("filename", "upload")
            content_type = kwargs.get("content_type", "application/octet-stream")

            if not file_bytes:
                raise ValueError("file_bytes is required for upload")

            resp = httpx.post(
                f"{site_url}/wp-json/wp/v2/media",
                headers={
                    "Authorization": f"Basic {tokens.access_token}",
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": content_type,
                },
                content=file_bytes,
                timeout=60.0,
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "id": result.get("id"),
                "url": result.get("source_url", ""),
                "alt": result.get("alt_text", ""),
                "media_type": result.get("media_type", ""),
            }

        elif action == "list":
            per_page = kwargs.get("per_page", 20)
            resp = httpx.get(
                f"{site_url}/wp-json/wp/v2/media",
                headers=self._headers(tokens),
                params={"per_page": per_page, "orderby": "date", "order": "desc"},
                timeout=15.0,
            )
            resp.raise_for_status()
            items = resp.json()
            return {
                "media": [
                    {
                        "id": m.get("id"),
                        "url": m.get("source_url", ""),
                        "alt": m.get("alt_text", ""),
                        "title": m.get("title", {}).get("rendered", ""),
                        "media_type": m.get("media_type", ""),
                    }
                    for m in items
                ]
            }

        elif action == "delete":
            media_id = kwargs.get("media_id")
            if not media_id:
                raise ValueError("media_id is required for delete")
            resp = httpx.delete(
                f"{site_url}/wp-json/wp/v2/media/{media_id}",
                headers=self._headers(tokens),
                params={"force": "true"},
                timeout=15.0,
            )
            resp.raise_for_status()
            return {"deleted": True, "id": media_id}

        else:
            raise ValueError(f"Unknown action: {action}")

    def update_seo(
        self,
        tokens: TokenSet,
        page_id: str,
        seo_data: dict[str, Any],
        **kwargs: Any,
    ) -> bool:
        """Update SEO metadata for a WordPress post or page.

        Compatible with Yoast SEO and Rank Math plugins.

        Args:
            page_id: WordPress post/page ID
            seo_data: {
                title: SEO title,
                meta_description: Meta description,
                focus_keyword: Focus keyword (Yoast),
                canonical_url: Canonical URL,
                og_title: Open Graph title,
                og_description: Open Graph description,
                schema: JSON-LD schema markup,
            }
        """
        site_url = self._get_site_url(tokens)
        post_type = kwargs.get("post_type", "posts")

        # Build Yoast-compatible SEO payload
        update_data: dict[str, Any] = {}

        yoast_head: dict[str, Any] = {}
        if seo_data.get("title"):
            yoast_head["title"] = seo_data["title"]
        if seo_data.get("meta_description"):
            yoast_head["description"] = seo_data["meta_description"]
        if seo_data.get("canonical_url"):
            yoast_head["canonical"] = seo_data["canonical_url"]
        if seo_data.get("og_title"):
            yoast_head["og_title"] = seo_data["og_title"]
        if seo_data.get("og_description"):
            yoast_head["og_description"] = seo_data["og_description"]
        if seo_data.get("schema"):
            yoast_head["schema"] = seo_data["schema"]

        if yoast_head:
            update_data["yoast_head_json"] = yoast_head

        # Rank Math compatibility
        if seo_data.get("focus_keyword"):
            update_data["rank_math_focus_keyword"] = seo_data["focus_keyword"]
        if seo_data.get("meta_description"):
            update_data["rank_math_description"] = seo_data["meta_description"]

        if not update_data:
            return False

        resp = httpx.post(
            f"{site_url}/wp-json/wp/v2/{post_type}/{page_id}",
            headers=self._headers(tokens),
            json=update_data,
            timeout=30.0,
        )

        return resp.status_code == 200

    def fetch_metrics(
        self,
        tokens: TokenSet,
        since: datetime,
        until: datetime | None = None,
        **kwargs: Any,
    ) -> list[MetricEvent]:
        """WordPress doesn't provide analytics metrics directly.

        In production, this would integrate with WordPress analytics plugins
        (Jetpack, MonsterInsights) or pull from the WP REST API stats endpoint.
        """
        # WordPress core doesn't have built-in analytics
        # Metrics come from GA4 or plugin-specific endpoints
        return []
