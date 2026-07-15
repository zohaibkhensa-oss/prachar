from __future__ import annotations

import asyncio
import uuid

import pytest

from prachar_shared.adapters.organic.youtube import YouTubeAdapter
from prachar_workers.organic.youtube_engine import (
    extract_chapters,
    optimize_youtube_metadata,
    transcribe_video,
)


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    from prachar_shared.config import get_settings

    get_settings.cache_clear()


def test_youtube_channel_is_youtube() -> None:
    assert YouTubeAdapter().channel == "youtube"


def test_generate_schema_has_required_keys() -> None:
    schema = YouTubeAdapter().generate_schema()
    props = schema["properties"]
    for key in (
        "title",
        "description",
        "tags",
        "thumbnail_variants",
        "pinned_comment",
        "playlist_id",
    ):
        assert key in props, f"missing key: {key}"


def test_policy_gate_title_too_long_blocks() -> None:
    result = YouTubeAdapter().policy_gate({"title": "A" * 101})
    assert result.passed is False
    assert any("title too long" in r for r in result.blocked_reasons)


def test_policy_gate_valid_payload_passes() -> None:
    result = YouTubeAdapter().policy_gate(
        {
            "title": "Good Title",
            "description": "Good desc",
            "tags": ["tag1"],
            "thumbnail_variants": [],
            "pinned_comment": "",
            "playlist_id": "",
        }
    )
    assert result.passed is True


def test_auth_url_contains_youtube_scope_and_state() -> None:
    url = YouTubeAdapter().auth_url("state456")
    assert "youtube" in url
    assert "state=state456" in url


def test_optimize_youtube_metadata_stub_returns_valid_payload() -> None:
    brand_id = uuid.uuid4()
    transcript = (
        "Welcome to the channel. Today we discuss marketing growth. "
        "There are three principles to understand. Consistency matters most."
    )
    brand_graph = {"brand_name": "Acme", "categories": ["marketing"]}
    result = asyncio.run(
        optimize_youtube_metadata(brand_id, transcript, "en-US", brand_graph)
    )
    assert isinstance(result, dict)
    for key in (
        "title",
        "description",
        "tags",
        "thumbnail_variants",
        "pinned_comment",
        "playlist_id",
    ):
        assert key in result, f"missing key: {key}"
    assert len(result["title"]) <= 100
    assert "Chapters:" in result["description"]
    assert sum(len(t) for t in result["tags"]) <= 500


def test_extract_chapters_returns_at_least_two_from_timestamps() -> None:
    transcript = (
        "0:00 Intro welcome to the video\n"
        "1:23 The first key principle\n"
        "3:45 The second key principle\n"
        "Some closing remarks without timestamps."
    )
    chapters = extract_chapters(transcript)
    assert isinstance(chapters, list)
    assert len(chapters) >= 2
    assert chapters[0]["time"] == "0:00"


def test_transcribe_video_returns_nonempty_string() -> None:
    asset_id = uuid.uuid4()
    transcript = asyncio.run(
        transcribe_video(asset_id, "s3://bucket/video.mp4")
    )
    assert isinstance(transcript, str)
    assert len(transcript) > 0
