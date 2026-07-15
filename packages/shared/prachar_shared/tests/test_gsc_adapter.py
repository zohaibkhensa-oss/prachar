from __future__ import annotations

from prachar_shared.adapters.organic.gsc import GSCAdapter


def test_gsc_channel_is_gsc() -> None:
    assert GSCAdapter().channel == "gsc"


def test_generate_schema_has_required_keys() -> None:
    schema = GSCAdapter().generate_schema()
    props = schema["properties"]
    for key in ("title", "meta", "h_structure", "schema_org", "internal_links", "faq"):
        assert key in props, f"missing key: {key}"


def test_policy_gate_title_too_long_blocks() -> None:
    result = GSCAdapter().policy_gate({"title": "A" * 70})
    assert result.passed is False
    assert any("title too long" in r for r in result.blocked_reasons)


def test_policy_gate_valid_payload_passes() -> None:
    result = GSCAdapter().policy_gate(
        {
            "title": "Good Title",
            "meta": "Good meta",
            "h_structure": [],
            "schema_org": {},
            "internal_links": [],
            "faq": [],
        }
    )
    assert result.passed is True


def test_auth_url_contains_webmasters_scope_and_state() -> None:
    url = GSCAdapter().auth_url("state123")
    assert "webmasters" in url
    assert "state=state123" in url
