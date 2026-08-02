"""Tests for the publish worker (P3.8 + Phase C.3.1-C.3.4).

Run with:
    .venv/bin/python -m pytest apps/workers/prachar_workers/tests/test_publish.py -q
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from prachar_workers import publish
from prachar_workers.publish import (
    campaign_to_dict,
    launch_google_ads,
    launch_meta_ads,
    publish_for_campaign,
    publish_to_gbp,
    publish_to_meta,
    publish_to_whatsapp,
)


# ─── Fakes ────────────────────────────────────────────────────────────────────


class FakeAdapter:
    """Minimal adapter implementing only ``create_campaign``."""

    def __init__(self, native_id: str | None = "gads-1", raise_on_create: bool = False) -> None:
        self._native_id = native_id
        self._raise = raise_on_create
        self.create_calls: list[tuple[Any, dict[str, Any]]] = []

    def create_campaign(self, tokens: Any, campaign_dict: dict[str, Any]) -> str:
        self.create_calls.append((tokens, campaign_dict))
        if self._raise:
            raise RuntimeError("adapter boom")
        return self._native_id


class FakeOrganicAdapter:
    """Minimal organic adapter implementing ``policy_gate`` and ``publish``."""

    def __init__(
        self,
        native_id: str = "org-1",
        raise_on_publish: bool = False,
        policy_passed: bool = True,
        async_publish: bool = False,
    ) -> None:
        self._native_id = native_id
        self._raise = raise_on_publish
        self._policy_passed = policy_passed
        self._async = async_publish
        self.publish_calls: list[tuple[Any, dict[str, Any]]] = []

    def policy_gate(self, payload: dict[str, Any]) -> Any:
        from prachar_shared.contracts import PolicyResult

        if self._policy_passed:
            return PolicyResult(passed=True)
        return PolicyResult(passed=False, blocked_reasons=["fake block"])

    def publish(self, tokens: Any, payload: dict[str, Any]) -> Any:
        from datetime import UTC, datetime

        from prachar_shared.contracts import PublishedRef

        self.publish_calls.append((tokens, payload))
        if self._raise:
            raise RuntimeError("organic boom")

        def _build_ref():
            return PublishedRef(
                channel="fake",
                native_id=self._native_id,
                url=f"https://example.com/{self._native_id}",
                published_at=datetime.now(UTC),
            )

        if self._async:
            async def _async_ref():
                return _build_ref()
            return _async_ref()
        return _build_ref()


def _campaign(
    network: str = "google_ads",
    ncid: str | None = None,
    brand_id: Any | None = None,
    tenant_id: Any | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        brand_id=brand_id or uuid.uuid4(),
        tenant_id=tenant_id or uuid.uuid4(),
        network=network,
        network_campaign_id=ncid,
        objective="traffic",
        budget_daily=100.0,
        currency="INR",
        audience_spec={"geo": ["IN"]},
        bid_strategy={},
        dry_run=True,
    )


def _brand(
    name: str = "Acme",
    website: str = "https://acme.com",
    brand_id: Any | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=brand_id or uuid.uuid4(),
        name=name,
        website=website,
        category="marketing",
    )


def _conn(channel: str = "google_ads") -> SimpleNamespace:
    return SimpleNamespace(channel=channel)


# ─── campaign_to_dict tests ───────────────────────────────────────────────────


def test_campaign_to_dict_serialises_fields():
    camp = _campaign(network="meta_ads", ncid=None)
    d = campaign_to_dict(camp)
    assert d["id"] == str(camp.id)
    assert d["network"] == "meta_ads"
    assert d["objective"] == "traffic"
    assert d["budget_daily"] == 100.0
    assert d["currency"] == "INR"
    assert d["audience_spec"] == {"geo": ["IN"]}
    assert d["dry_run"] is True


def test_campaign_to_dict_defaults_for_missing_attrs():
    """Missing attributes fall back to safe defaults instead of raising."""
    bare = SimpleNamespace(id=uuid.uuid4())
    d = campaign_to_dict(bare)
    assert d["network"] == ""
    assert d["budget_daily"] == 0.0
    assert d["currency"] == "INR"
    assert d["audience_spec"] == {}
    assert d["dry_run"] is True


# ─── publish_for_campaign tests ────────────────────────────────────────────────


def test_publish_for_campaign_processes_channel():
    """A single connection is published and the result records the native id."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeAdapter(native_id="gads-native-1")

    result = publish_for_campaign(
        session, camp, [_conn("google_ads")], adapter_factory=lambda _n: adapter
    )

    assert result["campaign_id"] == str(camp.id)
    assert result["channels"]["google_ads"]["status"] == "ok"
    assert result["channels"]["google_ads"]["network_campaign_id"] == "gads-native-1"
    # Adapter was called once.
    assert len(adapter.create_calls) == 1


def test_publish_for_campaign_updates_network_campaign_id():
    """The first returned native id is stored on the campaign row."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeAdapter(native_id="gads-native-42")

    result = publish_for_campaign(
        session, camp, [_conn("google_ads")], adapter_factory=lambda _n: adapter
    )

    assert camp.network_campaign_id == "gads-native-42"
    assert result["network_campaign_id"] == "gads-native-42"


def test_publish_for_campaign_does_not_overwrite_existing_network_campaign_id():
    """If network_campaign_id is already set, it is not overwritten."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid="existing-id")
    adapter = FakeAdapter(native_id="new-id")

    result = publish_for_campaign(
        session, camp, [_conn("google_ads")], adapter_factory=lambda _n: adapter
    )

    # The campaign row keeps its existing id.
    assert camp.network_campaign_id == "existing-id"
    # The result still reports the existing id.
    assert result["network_campaign_id"] == "existing-id"
    # The channel still recorded the native id returned by the adapter.
    assert result["channels"]["google_ads"]["network_campaign_id"] == "new-id"


def test_publish_for_campaign_per_channel_error_isolation():
    """One channel failing must not block other channels."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid=None)
    good_adapter = FakeAdapter(native_id="gads-1")
    bad_adapter = FakeAdapter(raise_on_create=True)

    def factory(network: str) -> Any:
        if network == "meta_ads":
            return bad_adapter
        return good_adapter

    result = publish_for_campaign(
        session,
        camp,
        [_conn("google_ads"), _conn("meta_ads")],
        adapter_factory=factory,
    )

    assert result["channels"]["google_ads"]["status"] == "ok"
    assert result["channels"]["meta_ads"]["status"] == "error"
    assert "adapter boom" in result["channels"]["meta_ads"]["error"]
    # The successful channel still stored its native id.
    assert camp.network_campaign_id == "gads-1"


def test_publish_for_campaign_no_connections():
    """A campaign with no active connections completes with empty channels."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid=None)

    result = publish_for_campaign(
        session, camp, [], adapter_factory=lambda _n: FakeAdapter()
    )

    assert result["channels"] == {}
    assert result["network_campaign_id"] is None
    # Campaign row unchanged.
    assert camp.network_campaign_id is None


def test_publish_for_campaign_skips_connection_with_no_channel():
    """A connection whose ``channel`` is None is skipped silently."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeAdapter(native_id="gads-1")

    result = publish_for_campaign(
        session,
        camp,
        [SimpleNamespace(channel=None), _conn("google_ads")],
        adapter_factory=lambda _n: adapter,
    )

    # Only the real connection was processed.
    assert list(result["channels"].keys()) == ["google_ads"]
    assert len(adapter.create_calls) == 1


def test_publish_for_campaign_without_session_does_not_set_attr():
    """When session is None the campaign row is not mutated (read-only mode)."""
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeAdapter(native_id="gads-1")

    result = publish_for_campaign(
        None, camp, [_conn("google_ads")], adapter_factory=lambda _n: adapter
    )

    # The campaign row was not mutated because session is None.
    assert camp.network_campaign_id is None
    # But the result still reports the native id from the adapter.
    assert result["network_campaign_id"] is None
    assert result["channels"]["google_ads"]["network_campaign_id"] == "gads-1"


def test_publish_for_campaign_adapter_receives_campaign_dict():
    """The adapter is called with a serialised campaign dict, not the ORM row."""
    session = MagicMock()
    camp = _campaign(network="google_ads", ncid=None)
    adapter = FakeAdapter(native_id="gads-1")

    publish_for_campaign(
        session, camp, [_conn("google_ads")], adapter_factory=lambda _n: adapter
    )

    tokens, campaign_dict = adapter.create_calls[0]
    assert isinstance(campaign_dict, dict)
    assert campaign_dict["network"] == "google_ads"
    assert campaign_dict["objective"] == "traffic"


# ─── Celery task registration ─────────────────────────────────────────────────


def test_publish_campaign_is_registered_task():
    from prachar_workers.publish import publish_campaign

    assert hasattr(publish_campaign, "delay")
    assert publish_campaign.name == "prachar_workers.publish.publish_campaign"


# ─── publish_to_gbp tests (C.3.1) ─────────────────────────────────────────────


def test_publish_to_gbp_publishes_when_connected():
    """GBP publish succeeds when a gmb connection exists."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter(native_id="gmb-post-1")

    result = publish_to_gbp(camp, brand, [_conn("gmb")], adapter=adapter)

    assert result["channel"] == "gmb"
    assert result["status"] == "published"
    assert result["native_id"] == "gmb-post-1"
    assert len(adapter.publish_calls) == 1


def test_publish_to_gbp_skips_when_not_connected():
    """GBP publish gracefully skips when no gmb connection exists."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter()

    result = publish_to_gbp(camp, brand, [], adapter=adapter)

    assert result["channel"] == "gmb"
    assert result["status"] == "skipped"
    assert "not connected" in result["reason"]
    assert len(adapter.publish_calls) == 0


def test_publish_to_gbp_skips_when_none_connections():
    """GBP publish gracefully skips when connections is None."""
    camp = _campaign()
    brand = _brand()

    result = publish_to_gbp(camp, brand, None)

    assert result["status"] == "skipped"


def test_publish_to_gbp_handles_adapter_error():
    """GBP publish returns error status when the adapter raises."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter(raise_on_publish=True)

    result = publish_to_gbp(camp, brand, [_conn("gmb")], adapter=adapter)

    assert result["channel"] == "gmb"
    assert result["status"] == "error"
    assert "organic boom" in result["error"]


def test_publish_to_gbp_policy_gate_blocks():
    """GBP publish returns error when policy gate fails."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter(policy_passed=False)

    result = publish_to_gbp(camp, brand, [_conn("gmb")], adapter=adapter)

    assert result["status"] == "error"
    assert "policy" in result["error"]
    assert len(adapter.publish_calls) == 0


def test_publish_to_gbp_supports_async_adapter():
    """GBP publish works with an async publish method (via asyncio.run)."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter(native_id="gmb-async-1", async_publish=True)

    result = publish_to_gbp(camp, brand, [_conn("gmb")], adapter=adapter)

    assert result["status"] == "published"
    assert result["native_id"] == "gmb-async-1"


# ─── publish_to_meta tests (C.3.2) ────────────────────────────────────────────


def test_publish_to_meta_publishes_facebook_and_instagram():
    """Meta publish sends to both Facebook and Instagram when both connected."""
    camp = _campaign()
    brand = _brand()
    fb_adapter = FakeOrganicAdapter(native_id="fb-1")
    ig_adapter = FakeOrganicAdapter(native_id="ig-1")

    result = publish_to_meta(
        camp, brand, [_conn("facebook"), _conn("instagram")],
        facebook_adapter=fb_adapter, instagram_adapter=ig_adapter,
    )

    assert result["channel"] == "meta"
    assert result["status"] == "published"
    posts_by_ch = {p["channel"]: p for p in result["posts"]}
    assert posts_by_ch["facebook"]["status"] == "published"
    assert posts_by_ch["facebook"]["native_id"] == "fb-1"
    assert posts_by_ch["instagram"]["status"] == "published"
    assert posts_by_ch["instagram"]["native_id"] == "ig-1"
    assert len(fb_adapter.publish_calls) == 1
    assert len(ig_adapter.publish_calls) == 1


def test_publish_to_meta_skips_when_not_connected():
    """Meta publish skips both channels when no FB/IG connections exist."""
    camp = _campaign()
    brand = _brand()

    result = publish_to_meta(camp, brand, [])

    assert result["status"] == "skipped"
    posts_by_ch = {p["channel"]: p for p in result["posts"]}
    assert posts_by_ch["facebook"]["status"] == "skipped"
    assert posts_by_ch["instagram"]["status"] == "skipped"


def test_publish_to_meta_partial_connection():
    """Meta publish handles only Facebook connected (Instagram skipped)."""
    camp = _campaign()
    brand = _brand()
    fb_adapter = FakeOrganicAdapter(native_id="fb-1")

    result = publish_to_meta(
        camp, brand, [_conn("facebook")],
        facebook_adapter=fb_adapter,
    )

    assert result["status"] == "published"
    posts_by_ch = {p["channel"]: p for p in result["posts"]}
    assert posts_by_ch["facebook"]["status"] == "published"
    assert posts_by_ch["instagram"]["status"] == "skipped"


def test_publish_to_meta_isolates_errors():
    """One sub-channel error does not block the other."""
    camp = _campaign()
    brand = _brand()
    fb_adapter = FakeOrganicAdapter(raise_on_publish=True)
    ig_adapter = FakeOrganicAdapter(native_id="ig-ok")

    result = publish_to_meta(
        camp, brand, [_conn("facebook"), _conn("instagram")],
        facebook_adapter=fb_adapter, instagram_adapter=ig_adapter,
    )

    posts_by_ch = {p["channel"]: p for p in result["posts"]}
    assert posts_by_ch["facebook"]["status"] == "error"
    assert posts_by_ch["instagram"]["status"] == "published"
    assert result["status"] == "published"


# ─── publish_to_whatsapp tests (C.3.3) ────────────────────────────────────────


def test_publish_to_whatsapp_sends_to_opted_in_recipients():
    """WhatsApp sends only to opted-in recipients."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter(native_id="wa-msg-1")
    recipients = [
        {"phone": "+1234567890", "opted_in": True},
        {"phone": "+1987654321", "opted_in": False},
    ]

    result = publish_to_whatsapp(
        camp, brand, [_conn("whatsapp")], adapter=adapter, recipients=recipients,
    )

    assert result["channel"] == "whatsapp"
    assert result["status"] == "published"
    # Only the opted-in recipient was sent a message.
    assert len(result["sent"]) == 1
    assert result["sent"][0]["to"] == "+1234567890"
    assert result["sent"][0]["status"] == "published"
    assert len(adapter.publish_calls) == 1


def test_publish_to_whatsapp_skips_when_not_connected():
    """WhatsApp skips when no whatsapp connection exists."""
    camp = _campaign()
    brand = _brand()
    recipients = [{"phone": "+1234567890", "opted_in": True}]

    result = publish_to_whatsapp(camp, brand, [], recipients=recipients)

    assert result["status"] == "skipped"
    assert "not connected" in result["reason"]


def test_publish_to_whatsapp_skips_when_no_opted_in_recipients():
    """WhatsApp skips when there are no opted-in recipients (compliance)."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter()
    recipients = [
        {"phone": "+1234567890", "opted_in": False},
        {"phone": "+1987654321", "opted_in": False},
    ]

    result = publish_to_whatsapp(
        camp, brand, [_conn("whatsapp")], adapter=adapter, recipients=recipients,
    )

    assert result["status"] == "skipped"
    assert "opted-in" in result["reason"]
    assert len(adapter.publish_calls) == 0


def test_publish_to_whatsapp_skips_when_no_recipients():
    """WhatsApp skips when recipients list is empty."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter()

    result = publish_to_whatsapp(
        camp, brand, [_conn("whatsapp")], adapter=adapter, recipients=[],
    )

    assert result["status"] == "skipped"
    assert "opted-in" in result["reason"]


def test_publish_to_whatsapp_handles_adapter_error():
    """WhatsApp returns error when the adapter raises."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeOrganicAdapter(raise_on_publish=True)
    recipients = [{"phone": "+1234567890", "opted_in": True}]

    result = publish_to_whatsapp(
        camp, brand, [_conn("whatsapp")], adapter=adapter, recipients=recipients,
    )

    assert result["status"] == "error"
    assert "organic boom" in result["error"]


# ─── launch_google_ads tests (C.3.4) ──────────────────────────────────────────


def test_launch_google_ads_publishes_when_connected():
    """Google Ads launch succeeds when a google_ads connection exists."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeAdapter(native_id="gads-native-1")

    result = launch_google_ads(camp, brand, [_conn("google_ads")], adapter=adapter)

    assert result["channel"] == "google_ads"
    assert result["status"] == "published"
    assert result["network_campaign_id"] == "gads-native-1"
    assert len(adapter.create_calls) == 1


def test_launch_google_ads_skips_when_not_connected():
    """Google Ads launch skips when no google_ads connection exists."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeAdapter()

    result = launch_google_ads(camp, brand, [], adapter=adapter)

    assert result["status"] == "skipped"
    assert "not connected" in result["reason"]
    assert len(adapter.create_calls) == 0


def test_launch_google_ads_handles_adapter_error():
    """Google Ads launch returns error when the adapter raises."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeAdapter(raise_on_create=True)

    result = launch_google_ads(camp, brand, [_conn("google_ads")], adapter=adapter)

    assert result["status"] == "error"
    assert "adapter boom" in result["error"]


# ─── launch_meta_ads tests (C.3.4) ────────────────────────────────────────────


def test_launch_meta_ads_publishes_when_connected():
    """Meta Ads launch succeeds when a meta_ads connection exists."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeAdapter(native_id="meta-native-1")

    result = launch_meta_ads(camp, brand, [_conn("meta_ads")], adapter=adapter)

    assert result["channel"] == "meta_ads"
    assert result["status"] == "published"
    assert result["network_campaign_id"] == "meta-native-1"
    assert len(adapter.create_calls) == 1


def test_launch_meta_ads_skips_when_not_connected():
    """Meta Ads launch skips when no meta_ads connection exists."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeAdapter()

    result = launch_meta_ads(camp, brand, [], adapter=adapter)

    assert result["status"] == "skipped"
    assert "not connected" in result["reason"]


def test_launch_meta_ads_handles_adapter_error():
    """Meta Ads launch returns error when the adapter raises."""
    camp = _campaign()
    brand = _brand()
    adapter = FakeAdapter(raise_on_create=True)

    result = launch_meta_ads(camp, brand, [_conn("meta_ads")], adapter=adapter)

    assert result["status"] == "error"
    assert "adapter boom" in result["error"]


# ─── publish_campaign task (with mocked DB layer) ─────────────────────────────


def test_publish_campaign_writes_audit_event():
    """The Celery task writes an AuditEvent row after publishing."""
    camp = _campaign(network="google_ads", ncid=None)
    brand = _brand(brand_id=camp.brand_id)
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    adapter = FakeAdapter(native_id="gads-1")

    with (
        patch("prachar_workers.db.session_scope", return_value=fake_session),
        patch("prachar_workers.publish._load_campaign", return_value=camp),
        patch("prachar_workers.publish._load_brand", return_value=brand),
        patch(
            "prachar_workers.publish._load_active_connections",
            return_value=[_conn("google_ads")],
        ),
        patch("prachar_workers.publish._write_audit") as mock_audit,
        patch("prachar_workers.publish.get_ads_adapter", return_value=adapter),
    ):
        from prachar_workers.publish import publish_campaign

        result = publish_campaign(str(camp.id))

    assert result["status"] == "ok"
    assert result["channels"]["google_ads"]["status"] == "published"
    # Organic channels gracefully skipped (no connections for them).
    assert result["channels"]["gmb"]["status"] == "skipped"
    assert result["channels"]["whatsapp"]["status"] == "skipped"
    # Audit was written exactly once with the campaign id and channel results.
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args.args[1] == camp.tenant_id
    assert call_args.args[2] == camp.id
    payload = call_args.args[3]
    assert "channels" in payload
    assert payload["network_campaign_id"] == "gads-1"


def test_publish_campaign_not_found():
    """When the campaign does not exist the task returns a not_found dict."""
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    with (
        patch("prachar_workers.db.session_scope", return_value=fake_session),
        patch("prachar_workers.publish._load_campaign", return_value=None),
        patch("prachar_workers.publish._write_audit") as mock_audit,
    ):
        from prachar_workers.publish import publish_campaign

        result = publish_campaign("does-not-exist")

    assert result["status"] == "not_found"
    mock_audit.assert_not_called()


def test_publish_campaign_no_connections():
    """A campaign with zero active connections completes with all channels skipped."""
    camp = _campaign(network="google_ads", ncid=None)
    brand = _brand(brand_id=camp.brand_id)
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    with (
        patch("prachar_workers.db.session_scope", return_value=fake_session),
        patch("prachar_workers.publish._load_campaign", return_value=camp),
        patch("prachar_workers.publish._load_brand", return_value=brand),
        patch("prachar_workers.publish._load_active_connections", return_value=[]),
        patch("prachar_workers.publish._write_audit") as mock_audit,
    ):
        from prachar_workers.publish import publish_campaign

        result = publish_campaign(str(camp.id))

    assert result["status"] == "ok"
    # Every channel should be skipped.
    for ch, status in result["channels"].items():
        assert status["status"] == "skipped", f"{ch} not skipped: {status}"
    mock_audit.assert_called_once()


def test_publish_campaign_per_channel_error_isolation():
    """One channel failing inside the task does not abort the task."""
    camp = _campaign(network="google_ads", ncid=None)
    brand = _brand(brand_id=camp.brand_id)
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    good_adapter = FakeAdapter(native_id="gads-1")
    bad_adapter = FakeAdapter(raise_on_create=True)

    def fake_get_ads(network: str) -> Any:
        if network == "meta_ads":
            return bad_adapter
        return good_adapter

    with (
        patch("prachar_workers.db.session_scope", return_value=fake_session),
        patch("prachar_workers.publish._load_campaign", return_value=camp),
        patch("prachar_workers.publish._load_brand", return_value=brand),
        patch(
            "prachar_workers.publish._load_active_connections",
            return_value=[_conn("google_ads"), _conn("meta_ads")],
        ),
        patch("prachar_workers.publish._write_audit"),
        patch("prachar_workers.publish.get_ads_adapter", side_effect=fake_get_ads),
    ):
        from prachar_workers.publish import publish_campaign

        result = publish_campaign(str(camp.id))

    assert result["status"] == "ok"
    assert result["channels"]["google_ads"]["status"] == "published"
    assert result["channels"]["meta_ads"]["status"] == "error"
    # The successful channel stored its native id.
    assert camp.network_campaign_id == "gads-1"


def test_publish_campaign_calls_all_publish_functions():
    """The task calls all five publish sub-functions and collects their statuses."""
    camp = _campaign(network="google_ads", ncid=None)
    brand = _brand(brand_id=camp.brand_id)
    fake_session = MagicMock()
    fake_session.__enter__ = MagicMock(return_value=fake_session)
    fake_session.__exit__ = MagicMock(return_value=False)

    gmb_adapter = FakeOrganicAdapter(native_id="gmb-1")
    fb_adapter = FakeOrganicAdapter(native_id="fb-1")
    ig_adapter = FakeOrganicAdapter(native_id="ig-1")
    wa_adapter = FakeOrganicAdapter(native_id="wa-1")
    gads_adapter = FakeAdapter(native_id="gads-1")
    mads_adapter = FakeAdapter(native_id="mads-1")

    connections = [
        _conn("gmb"), _conn("facebook"), _conn("instagram"),
        _conn("whatsapp"), _conn("google_ads"), _conn("meta_ads"),
    ]

    def fake_get_organic(channel: str) -> Any:
        return {"gmb": gmb_adapter, "facebook": fb_adapter, "instagram": ig_adapter, "whatsapp": wa_adapter}[channel]

    def fake_get_ads(network: str) -> Any:
        return {"google_ads": gads_adapter, "meta_ads": mads_adapter}[network]

    with (
        patch("prachar_workers.db.session_scope", return_value=fake_session),
        patch("prachar_workers.publish._load_campaign", return_value=camp),
        patch("prachar_workers.publish._load_brand", return_value=brand),
        patch("prachar_workers.publish._load_active_connections", return_value=connections),
        patch("prachar_workers.publish._write_audit"),
        patch("prachar_workers.publish.get_organic_adapter", side_effect=fake_get_organic),
        patch("prachar_workers.publish.get_ads_adapter", side_effect=fake_get_ads),
    ):
        from prachar_workers.publish import publish_campaign

        result = publish_campaign(str(camp.id))

    assert result["status"] == "ok"
    assert result["channels"]["gmb"]["status"] == "published"
    assert result["channels"]["facebook"]["status"] == "published"
    assert result["channels"]["instagram"]["status"] == "published"
    # WhatsApp skipped because no recipients passed in the task context.
    assert result["channels"]["whatsapp"]["status"] == "skipped"
    assert result["channels"]["google_ads"]["status"] == "published"
    assert result["channels"]["meta_ads"]["status"] == "published"
    # network_campaign_id set from the first successful ads launch.
    assert result["network_campaign_id"] == "gads-1"
    assert camp.network_campaign_id == "gads-1"


def test_publish_campaign_runs_eager_without_db():
    """In eager mode the task must not raise even when the DB is unavailable."""
    from prachar_workers.publish import publish_campaign

    prev = publish.celery_app.conf.task_always_eager
    prev_prop = publish.celery_app.conf.task_eager_propagates
    publish.celery_app.conf.task_always_eager = True
    publish.celery_app.conf.task_eager_propagates = True
    try:
        result = publish_campaign.apply(args=(str(uuid.uuid4()),)).get()
    finally:
        publish.celery_app.conf.task_always_eager = prev
        publish.celery_app.conf.task_eager_propagates = prev_prop
    # DB unavailable in test env → graceful error/not_found dict, never raises.
    assert isinstance(result, dict)
