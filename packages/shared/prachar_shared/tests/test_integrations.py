"""Tests for the Integrations framework — common interface, GA4, WordPress, registry."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from prachar_shared.integrations import (
    IntegrationCapability,
    IntegrationHealth,
    IntegrationInfo,
    IntegrationStatus,
    MarketingIntegration,
    SyncResult,
    get_integration_registry,
    register_integration,
)
from prachar_shared.integrations.google_analytics import GoogleAnalytics4
from prachar_shared.integrations.wordpress import WordPress


# ─── Common Interface Tests ─────────────────────────────────────────────────


class TestIntegrationCapability:
    """Integration capability flags."""

    def test_capabilities_exist(self):
        assert IntegrationCapability.AUTHENTICATE
        assert IntegrationCapability.READ_METRICS
        assert IntegrationCapability.PUBLISH
        assert IntegrationCapability.SYNC_ASSETS
        assert IntegrationCapability.WRITE_BACK
        assert IntegrationCapability.ATTRIBUTION
        assert IntegrationCapability.MANAGE_MEDIA
        assert IntegrationCapability.SEO_MANAGEMENT

    def test_capability_combination(self):
        caps = IntegrationCapability.READ_METRICS | IntegrationCapability.ATTRIBUTION
        assert caps & IntegrationCapability.READ_METRICS
        assert caps & IntegrationCapability.ATTRIBUTION
        assert not (caps & IntegrationCapability.PUBLISH)

    def test_none_capability(self):
        assert IntegrationCapability.NONE.value == 0


class TestIntegrationInfo:
    """Integration metadata dataclass."""

    def test_creation(self):
        info = IntegrationInfo(
            name="test",
            display_name="Test Integration",
            category="analytics",
            capabilities=IntegrationCapability.READ_METRICS,
        )
        assert info.name == "test"
        assert info.display_name == "Test Integration"
        assert info.category == "analytics"
        assert info.capabilities & IntegrationCapability.READ_METRICS

    def test_defaults(self):
        info = IntegrationInfo(name="x", display_name="X", category="test")
        assert info.icon == ""
        assert info.description == ""
        assert info.capabilities == IntegrationCapability.NONE
        assert info.auth_type == "oauth"
        assert info.scopes == []


class TestIntegrationHealth:
    """Health status dataclass."""

    def test_creation(self):
        health = IntegrationHealth(
            name="ga4",
            status=IntegrationStatus.CONNECTED,
            capabilities=IntegrationCapability.READ_METRICS,
        )
        d = health.to_dict()
        assert d["name"] == "ga4"
        assert d["status"] == "connected"
        assert "READ_METRICS" in d["capabilities"]

    def test_error_status(self):
        health = IntegrationHealth(
            name="ga4",
            status=IntegrationStatus.ERROR,
            last_error="Token expired",
        )
        d = health.to_dict()
        assert d["status"] == "error"
        assert d["last_error"] == "Token expired"


class TestSyncResult:
    """Sync result dataclass."""

    def test_success(self):
        result = SyncResult(success=True, synced_count=50, duration_ms=1500.0)
        assert result.success
        assert result.synced_count == 50
        assert result.errors == []

    def test_failure(self):
        result = SyncResult(success=False, errors=["Auth failed"])
        assert not result.success
        assert len(result.errors) == 1


# ─── Registry Tests ─────────────────────────────────────────────────────────


class TestIntegrationRegistry:
    """Integration registry."""

    def test_ga4_registered(self):
        registry = get_integration_registry()
        assert "google_analytics" in registry.available()

    def test_wordpress_registered(self):
        registry = get_integration_registry()
        assert "wordpress" in registry.available()

    def test_get_integration(self):
        registry = get_integration_registry()
        cls = registry.get("google_analytics")
        assert cls is not None
        assert cls.integration_name == "google_analytics"

    def test_get_nonexistent(self):
        registry = get_integration_registry()
        assert registry.get("nonexistent") is None

    def test_all_integrations_info(self):
        registry = get_integration_registry()
        all_info = registry.all_integrations()
        assert "google_analytics" in all_info
        assert "wordpress" in all_info
        assert all_info["google_analytics"].category == "analytics"
        assert all_info["wordpress"].category == "cms"


# ─── GA4 Adapter Tests ──────────────────────────────────────────────────────


class TestGoogleAnalytics4:
    """GA4 integration adapter."""

    def test_info(self):
        info = GoogleAnalytics4.info()
        assert info.name == "google_analytics"
        assert info.display_name == "Google Analytics 4"
        assert info.category == "analytics"
        assert info.auth_type == "oauth"
        assert IntegrationCapability.READ_METRICS in info.capabilities
        assert IntegrationCapability.ATTRIBUTION in info.capabilities

    def test_auth_url(self):
        ga4 = GoogleAnalytics4()
        url = ga4.auth_url(
            state="test_state",
            client_id="test_client_id",
            redirect_uri="http://localhost:3000/callback",
        )
        assert "accounts.google.com" in url
        assert "test_client_id" in url
        assert "test_state" in url
        assert "analytics.readonly" in url

    def test_authenticate_requires_code(self):
        ga4 = GoogleAnalytics4()
        with pytest.raises(ValueError, match="OAuth code is required"):
            ga4.authenticate(code="")

    def test_fetch_metrics_requires_property_id(self):
        ga4 = GoogleAnalytics4()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="property_id is required"):
            ga4.fetch_metrics(tokens, since=datetime.now(timezone.utc))

    def test_fetch_realtime_requires_property_id(self):
        ga4 = GoogleAnalytics4()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="property_id is required"):
            ga4.fetch_realtime(tokens)

    def test_attribute_conversions_requires_property_id(self):
        ga4 = GoogleAnalytics4()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="property_id is required"):
            ga4.attribute_conversions(tokens, since=datetime.now(timezone.utc))

    def test_unsupported_methods_raise(self):
        """GA4 should not support PUBLISH or SYNC_ASSETS."""
        ga4 = GoogleAnalytics4()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(NotImplementedError, match="does not support PUBLISH"):
            ga4.publish(tokens, payload={})
        with pytest.raises(NotImplementedError, match="does not support SYNC_ASSETS"):
            ga4.fetch_assets(tokens)
        with pytest.raises(NotImplementedError, match="does not support MANAGE_MEDIA"):
            ga4.manage_media(tokens, action="list")


# ─── WordPress Adapter Tests ────────────────────────────────────────────────


class TestWordPress:
    """WordPress integration adapter."""

    def test_info(self):
        info = WordPress.info()
        assert info.name == "wordpress"
        assert info.display_name == "WordPress"
        assert info.category == "cms"
        assert info.auth_type == "app_password"
        assert IntegrationCapability.PUBLISH in info.capabilities
        assert IntegrationCapability.SYNC_ASSETS in info.capabilities
        assert IntegrationCapability.MANAGE_MEDIA in info.capabilities
        assert IntegrationCapability.SEO_MANAGEMENT in info.capabilities

    def test_authenticate_requires_credentials(self):
        wp = WordPress()
        with pytest.raises(ValueError, match="site_url, username, and app_password"):
            wp.authenticate(site_url="", username="", app_password="")

    def test_authenticate_requires_site_url(self):
        wp = WordPress()
        with pytest.raises(ValueError, match="site_url, username, and app_password"):
            wp.authenticate(site_url="https://example.com", username="", app_password="")

    def test_unsupported_methods_raise(self):
        """WordPress should not support READ_METRICS or ATTRIBUTION."""
        wp = WordPress()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        # WordPress fetch_metrics returns empty list (not NotImplementedError)
        metrics = wp.fetch_metrics(tokens, since=datetime.now(timezone.utc))
        assert metrics == []

        with pytest.raises(NotImplementedError, match="does not support ATTRIBUTION"):
            wp.attribute_conversions(tokens, since=datetime.now(timezone.utc))

        with pytest.raises(NotImplementedError, match="does not support WRITE_BACK"):
            wp.write_back(tokens, entity_id="1", updates={})

    def test_manage_media_unknown_action(self):
        wp = WordPress()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="Unknown action"):
            wp.manage_media(tokens, action="invalid")

    def test_manage_media_upload_requires_bytes(self):
        wp = WordPress()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="file_bytes is required"):
            wp.manage_media(tokens, action="upload")

    def test_manage_media_delete_requires_id(self):
        wp = WordPress()
        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        tokens = TokenSet(
            access_token="fake",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        with pytest.raises(ValueError, match="media_id is required"):
            wp.manage_media(tokens, action="delete")


# ─── Base Class Tests ───────────────────────────────────────────────────────


class TestMarketingIntegrationBase:
    """Test the base MarketingIntegration interface."""

    def test_default_sync_calls_fetch_methods(self):
        """The default sync() should call fetch_metrics and fetch_assets."""
        # Create a minimal test integration
        @register_integration
        class TestIntegration(MarketingIntegration):
            integration_name = "test_sync_integration"
            integration_display_name = "Test Sync"

            @classmethod
            def info(cls):
                return IntegrationInfo(
                    name="test_sync_integration",
                    display_name="Test Sync",
                    category="test",
                    capabilities=IntegrationCapability.READ_METRICS | IntegrationCapability.SYNC_ASSETS,
                )

            def authenticate(self, **kwargs):
                from prachar_shared.contracts import TokenSet
                from datetime import timedelta
                return TokenSet(
                    access_token="test",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )

            def test_connection(self, tokens):
                return True

            def fetch_metrics(self, tokens, since, until=None, **kwargs):
                return []

            def fetch_assets(self, tokens, asset_type="all", **kwargs):
                return []

        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        integration = TestIntegration()
        tokens = TokenSet(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        result = integration.sync(tokens)
        assert result.success
        assert result.synced_count == 0

    def test_health_returns_connected(self):
        @register_integration
        class TestHealthIntegration(MarketingIntegration):
            integration_name = "test_health_integration"
            integration_display_name = "Test Health"

            @classmethod
            def info(cls):
                return IntegrationInfo(
                    name="test_health_integration",
                    display_name="Test Health",
                    category="test",
                    capabilities=IntegrationCapability.AUTHENTICATE,
                )

            def authenticate(self, **kwargs):
                from prachar_shared.contracts import TokenSet
                from datetime import timedelta
                return TokenSet(
                    access_token="test",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )

            def test_connection(self, tokens):
                return True

        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        integration = TestHealthIntegration()
        tokens = TokenSet(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        health = integration.health(tokens)
        assert health.status == IntegrationStatus.CONNECTED
        assert health.name == "test_health_integration"

    def test_health_returns_error_on_failure(self):
        @register_integration
        class TestErrorIntegration(MarketingIntegration):
            integration_name = "test_error_integration"
            integration_display_name = "Test Error"

            @classmethod
            def info(cls):
                return IntegrationInfo(
                    name="test_error_integration",
                    display_name="Test Error",
                    category="test",
                )

            def authenticate(self, **kwargs):
                from prachar_shared.contracts import TokenSet
                from datetime import timedelta
                return TokenSet(
                    access_token="test",
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )

            def test_connection(self, tokens):
                raise Exception("Connection refused")

        from prachar_shared.contracts import TokenSet
        from datetime import timedelta
        integration = TestErrorIntegration()
        tokens = TokenSet(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        health = integration.health(tokens)
        assert health.status == IntegrationStatus.ERROR
        assert "Connection refused" in health.last_error
