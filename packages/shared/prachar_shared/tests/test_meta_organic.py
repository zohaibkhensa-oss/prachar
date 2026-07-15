from __future__ import annotations

import pytest

from prachar_shared.adapters.organic.instagram import InstagramAdapter
from prachar_shared.adapters.organic.facebook import FacebookAdapter
from prachar_shared.contracts import AudienceSpec, CreativeAsset


def test_instagram_channel():
    assert InstagramAdapter().channel == "instagram"


def test_instagram_schema():
    schema = InstagramAdapter().generate_schema()
    assert "caption" in schema["properties"]
    assert "hashtag_sets" in schema["properties"]
    assert "post_type" in schema["properties"]
    assert "media_urls" in schema["properties"]
    assert schema["properties"]["caption"]["maxLength"] == 2200


def test_instagram_policy_gate_long_caption():
    adapter = InstagramAdapter()
    result = adapter.policy_gate({"caption": "A" * 2201, "post_type": "feed", "media_urls": ["url"]})
    assert not result.passed
    assert any("2200" in r for r in result.blocked_reasons)


def test_instagram_policy_gate_banned_hashtag():
    adapter = InstagramAdapter()
    result = adapter.policy_gate({
        "caption": "Good caption",
        "hashtag_sets": [["#like4like", "#good"]],
        "post_type": "feed",
        "media_urls": ["url"],
    })
    assert not result.passed
    assert any("Banned hashtag" in r for r in result.blocked_reasons)


def test_instagram_policy_gate_valid():
    adapter = InstagramAdapter()
    result = adapter.policy_gate({
        "caption": "Great content about our brand!",
        "hashtag_sets": [["#brand", "#quality"]],
        "first_comment_hashtags": True,
        "post_type": "feed",
        "media_urls": ["https://example.com/img.jpg"],
    })
    assert result.passed


def test_instagram_auth_url():
    url = InstagramAdapter().auth_url("state789")
    assert "facebook.com" in url
    assert "instagram" in url
    assert "state789" in url


def test_facebook_channel():
    assert FacebookAdapter().channel == "facebook"


def test_facebook_schema():
    schema = FacebookAdapter().generate_schema()
    assert "message" in schema["properties"]
    assert "link" in schema["properties"]
    assert "hashtags" in schema["properties"]


def test_facebook_policy_gate_long_message():
    adapter = FacebookAdapter()
    result = adapter.policy_gate({"message": "A" * 63207})
    assert not result.passed


def test_facebook_policy_gate_valid():
    adapter = FacebookAdapter()
    result = adapter.policy_gate({"message": "Check out our new product!"})
    assert result.passed


def test_facebook_auth_url():
    url = FacebookAdapter().auth_url("fb-state-123")
    assert "facebook.com" in url
    assert "fb-state-123" in url
