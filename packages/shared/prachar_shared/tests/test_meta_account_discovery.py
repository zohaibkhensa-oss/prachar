"""Meta integration hardening tests — ad-account discovery + token lifecycle.

Covers:
  1. TokenSet carries metadata (ad_account_id persisted at OAuth).
  2. MetaAdsAdapter reads account id from token metadata (real path).
  3. FacebookAdapter.exchange_code performs fb_exchange_token long-lived upgrade.
  4. fetch_ad_accounts hits /me/adaccounts and returns account dicts.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from prachar_shared.adapters.ads.meta_ads import MetaAdsAdapter
from prachar_shared.adapters.organic.facebook import FacebookAdapter
from prachar_shared.contracts import TokenSet


def _tokens(**meta) -> TokenSet:
    return TokenSet(
        access_token="tok",
        expires_at=datetime.now(UTC) + timedelta(days=60),
        scopes=["ads_management"],
        metadata=meta,
    )


class TestAccountIdResolution:
    def test_reads_ad_account_id_from_metadata(self):
        adapter = MetaAdsAdapter()
        assert adapter._get_account_id(_tokens(ad_account_id="123456789")) == "123456789"

    def test_strips_act_prefix(self):
        adapter = MetaAdsAdapter()
        assert adapter._get_account_id(_tokens(ad_account_id="act_123456789")) == "123456789"

    def test_missing_account_returns_none_not_fallback(self):
        adapter = MetaAdsAdapter()
        assert adapter._get_account_id(_tokens()) is None


class TestLongLivedExchange:
    async def test_exchange_code_upgrades_to_long_lived(self, monkeypatch):
        from prachar_shared.config import get_settings

        s = get_settings()
        monkeypatch.setattr(s, "meta_app_id", "app1")
        monkeypatch.setattr(s, "meta_app_secret", "sec1")

        calls = []

        class FakeResp:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def raise_for_status(self):
                pass

            def json(self):
                return self._data

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def post(self, url, data=None, **kw):
                calls.append(("post", url))
                return FakeResp({"access_token": "short", "expires_in": 3600})

            async def get(self, url, params=None, **kw):
                calls.append(("get", url))
                return FakeResp({"access_token": "long-lived", "expires_in": 5184000})

        monkeypatch.setattr(
            "prachar_shared.adapters.organic.facebook.httpx.AsyncClient",
            lambda *a, **kw: FakeClient(),
        )
        adapter = FacebookAdapter()
        tokens = await adapter.exchange_code("code123")

        assert tokens.access_token == "long-lived"
        # fb_exchange_token call happened
        assert any(
            m == "get" and "oauth/access_token" in u for m, u in calls
        ), calls
        assert tokens.expires_at > datetime.now(UTC) + timedelta(days=30)


class TestAdAccountDiscovery:
    async def test_fetch_ad_accounts_hits_me_adaccounts(self):
        class FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "data": [
                        {
                            "id": "act_111",
                            "account_id": "111",
                            "name": "Acct One",
                            "business": {"id": "b1", "name": "Biz"},
                            "account_status": 1,
                        }
                    ]
                }

        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def get(self, url, params=None, **kw):
                assert "me/adaccounts" in url
                assert params["access_token"] == "tok"
                return FakeResp()

        with patch(
            "prachar_shared.adapters.organic.facebook.httpx.AsyncClient",
            lambda *a, **kw: FakeClient(),
        ):
            accounts = await FacebookAdapter().fetch_ad_accounts(_tokens())

        assert accounts[0]["account_id"] == "111"
        assert accounts[0]["business"]["name"] == "Biz"

    async def test_fetch_ad_accounts_error_returns_empty(self):
        class FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def get(self, url, params=None, **kw):
                raise RuntimeError("graph error")

        with patch(
            "prachar_shared.adapters.organic.facebook.httpx.AsyncClient",
            lambda *a, **kw: FakeClient(),
        ):
            accounts = await FacebookAdapter().fetch_ad_accounts(_tokens())
        assert accounts == []
