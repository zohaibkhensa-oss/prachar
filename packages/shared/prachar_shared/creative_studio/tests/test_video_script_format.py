"""Tests for the video_script creative format generator (Part P2.5)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.video_script import (
    VIDEO_SCRIPT,
    generate_video_script,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _completion(text: str, tokens: int = 120) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


def _valid_script_json() -> dict:
    return {
        "scenes": [
            {
                "scene_no": 1,
                "visual": "Close-up of a steaming coffee cup on a wooden table",
                "voiceover": "Start your morning the right way.",
                "on_screen_text": "Fresh mornings",
                "duration": 5,
            },
            {
                "scene_no": 2,
                "visual": "Barista pouring milk into a latte, slow motion",
                "voiceover": "Handcrafted by our expert baristas.",
                "on_screen_text": "Crafted with care",
                "duration": 7,
            },
            {
                "scene_no": 3,
                "visual": "Customer smiling, taking first sip",
                "voiceover": "Taste the difference today.",
                "on_screen_text": "Visit us now",
                "duration": 3,
            },
        ],
        "music_mood": "upbeat",
        "total_duration": 15,
    }


@pytest.fixture()
def sample_campaign() -> dict:
    return {
        "id": "camp-123",
        "name": "Summer Coffee Launch",
        "goal": "drive footfall to cafe",
        "budget": "₹50,000",
    }


@pytest.fixture()
def sample_creative_direction() -> dict:
    return {
        "id": "cd-456",
        "hook": "Fresh mornings start here",
        "angle": "Comfort + craft",
        "tone": "warm",
        "sample_headline": "Your best morning yet",
        "sample_cta": "Visit today",
    }


@pytest.fixture()
def sample_domain_context() -> dict:
    return {
        "id": "f_and_b",
        "label": "Food & Beverage",
        "customer_type": "consumer",
    }


@pytest.fixture()
def mock_gateway():
    """A MagicMock AIGateway that returns a valid video script JSON."""
    gw = MagicMock()
    gw.complete = MagicMock(
        return_value=_completion(json.dumps(_valid_script_json()))
    )
    return gw


@pytest.fixture()
def markdown_gateway():
    """A gateway that wraps the JSON in markdown fences (tests extract_json)."""
    payload = _valid_script_json()
    text = f"```json\n{json.dumps(payload)}\n```"
    gw = MagicMock()
    gw.complete = MagicMock(return_value=_completion(text))
    return gw


@pytest.fixture()
def failing_gateway():
    """A gateway whose complete() raises a generic RuntimeError."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=RuntimeError("LLM exploded"))
    return gw


@pytest.fixture()
def budget_gateway():
    """A gateway whose complete() raises BudgetExceeded."""
    gw = MagicMock()
    gw.complete = MagicMock(side_effect=BudgetExceeded("over budget"))
    return gw


# ─── Spec sanity ───────────────────────────────────────────────────────────


class TestVideoScriptSpec:
    def test_spec_id(self):
        assert VIDEO_SCRIPT.id == "video_script"

    def test_spec_has_required_placeholders(self):
        for ph in ["{campaign}", "{creative_direction}", "{domain_context}"]:
            assert ph in VIDEO_SCRIPT.prompt_template

    def test_spec_schema_has_required_keys(self):
        props = VIDEO_SCRIPT.output_schema["properties"]
        assert "scenes" in props
        assert "music_mood" in props
        assert "total_duration" in props
        scene_props = props["scenes"]["items"]["properties"]
        for key in ["scene_no", "visual", "voiceover", "on_screen_text", "duration"]:
            assert key in scene_props


# ─── Generator: success path ───────────────────────────────────────────────


class TestGenerateVideoScriptSuccess:
    def test_returns_dict(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert isinstance(result, dict)

    def test_has_scenes_list(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert "scenes" in result
        assert isinstance(result["scenes"], list)
        assert len(result["scenes"]) == 3

    def test_has_music_mood(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert "music_mood" in result
        assert result["music_mood"] == "upbeat"

    def test_has_total_duration(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert "total_duration" in result
        assert result["total_duration"] == 15

    def test_each_scene_has_required_fields(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        required = {"scene_no", "visual", "voiceover", "on_screen_text", "duration"}
        for scene in result["scenes"]:
            assert isinstance(scene, dict)
            assert required.issubset(scene.keys())
            assert isinstance(scene["scene_no"], int)
            assert isinstance(scene["visual"], str)
            assert isinstance(scene["voiceover"], str)
            assert isinstance(scene["on_screen_text"], str)
            assert isinstance(scene["duration"], (int, float))

    def test_scene_numbers_preserved(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert [s["scene_no"] for s in result["scenes"]] == [1, 2, 3]

    def test_uses_tier_large(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        from prachar_shared.ai_gateway import Tier

        generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=mock_gateway,
        )
        assert mock_gateway.complete.called
        _, kwargs = mock_gateway.complete.call_args
        assert kwargs.get("tier") is Tier.large

    def test_parses_markdown_fenced_json(
        self,
        markdown_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=markdown_gateway,
        )
        assert len(result["scenes"]) == 3
        assert result["music_mood"] == "upbeat"


# ─── Generator: graceful fallback ──────────────────────────────────────────


class TestGenerateVideoScriptFallback:
    def test_failing_gateway_returns_empty_dict(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=failing_gateway,
        )
        assert result == {}

    def test_malformed_json_returns_empty_or_normalised(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion("not json at all"))
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        # extract_json returns None for non-JSON → _parse_video_script({}) →
        # normalised empty shape (scenes=[], music_mood='', total_duration=0.0)
        assert result["scenes"] == []
        assert result["music_mood"] == ""
        assert result["total_duration"] == 0.0

    def test_partial_scene_fields_filled(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        partial = {
            "scenes": [
                {"scene_no": 1, "visual": "A shot", "voiceover": "Hi"},
                # missing on_screen_text and duration
            ],
            "music_mood": "calm",
        }
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion(json.dumps(partial)))
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert len(result["scenes"]) == 1
        scene = result["scenes"][0]
        assert scene["on_screen_text"] == ""
        assert scene["duration"] == 0.0
        assert result["music_mood"] == "calm"

    def test_budget_exceeded_propagates(
        self,
        budget_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        with pytest.raises(BudgetExceeded):
            generate_video_script(
                sample_campaign,
                sample_creative_direction,
                sample_domain_context,
                gateway=budget_gateway,
            )

    def test_total_duration_summed_when_missing(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        payload = {
            "scenes": [
                {"scene_no": 1, "visual": "a", "voiceover": "b", "on_screen_text": "c", "duration": 4},
                {"scene_no": 2, "visual": "d", "voiceover": "e", "on_screen_text": "f", "duration": 6},
            ],
            "music_mood": "energetic",
        }
        gw = MagicMock()
        gw.complete = MagicMock(return_value=_completion(json.dumps(payload)))
        result = generate_video_script(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
            gateway=gw,
        )
        assert result["total_duration"] == 10.0
