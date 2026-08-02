"""Tests for the Story creative format generator (P2.7)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import BudgetExceeded, Completion
from prachar_shared.creative_studio.formats.story import (
    STORY,
    _parse_frames,
    generate_story,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _make_gateway(text: str = "{}") -> MagicMock:
    """Return a mock AIGateway whose ``complete`` returns a Completion."""
    gw = MagicMock()
    gw.complete.return_value = Completion(
        text=text,
        model="test-model",
        tokens_used=100,
        provider="test",
    )
    return gw


def _sample_frames() -> list[dict]:
    return [
        {
            "frame_no": 1,
            "type": "poll",
            "copy": "Which color do you prefer?",
            "visual_brief": "Split-screen showing two color swatches",
            "sticker": "poll",
        },
        {
            "frame_no": 2,
            "type": "question",
            "copy": "What's your biggest challenge?",
            "visual_brief": "Solid brand-color background with text overlay",
            "sticker": "question",
        },
        {
            "frame_no": 3,
            "type": "quiz",
            "copy": "Guess: how many users we have?",
            "visual_brief": "Animated counter graphic",
            "sticker": "quiz",
        },
        {
            "frame_no": 4,
            "type": "text",
            "copy": "Thanks for playing!",
            "visual_brief": "Confetti animation on brand background",
            "sticker": "mention",
        },
    ]


# ─── Spec tests ────────────────────────────────────────────────────────────


class TestStorySpec:
    def test_spec_id(self):
        assert STORY.id == "story"

    def test_spec_label(self):
        assert STORY.label == "Story"

    def test_spec_has_placeholders(self):
        for ph in ["{campaign}", "{creative_direction}", "{domain_context}"]:
            assert ph in STORY.prompt_template

    def test_schema_frames_required(self):
        assert "frames" in STORY.output_schema["properties"]
        assert "frames" in STORY.output_schema["required"]

    def test_schema_frame_fields(self):
        frame_props = STORY.output_schema["properties"]["frames"]["items"]["properties"]
        for key in ["frame_no", "type", "copy", "visual_brief", "sticker"]:
            assert key in frame_props

    def test_schema_frame_type_enum(self):
        frame_props = STORY.output_schema["properties"]["frames"]["items"]["properties"]
        assert set(frame_props["type"]["enum"]) == {"poll", "question", "quiz", "text"}


# ─── _parse_frames tests ───────────────────────────────────────────────────


class TestParseFrames:
    def test_parses_valid_frames(self):
        raw = {"frames": _sample_frames()}
        result = _parse_frames(raw)
        assert len(result) == 4
        assert result[0]["type"] == "poll"
        assert result[0]["frame_no"] == 1
        assert result[3]["type"] == "text"

    def test_empty_dict_returns_empty(self):
        assert _parse_frames({}) == []

    def test_non_dict_returns_empty(self):
        assert _parse_frames("not a dict") == []
        assert _parse_frames(None) == []
        assert _parse_frames([]) == []

    def test_missing_frames_key_returns_empty(self):
        assert _parse_frames({"other": 1}) == []

    def test_frames_not_list_returns_empty(self):
        assert _parse_frames({"frames": "nope"}) == []

    def test_invalid_frame_type_coerced_to_text(self):
        raw = {"frames": [{"frame_no": 1, "type": "unknown", "copy": "x", "visual_brief": "y", "sticker": "z"}]}
        result = _parse_frames(raw)
        assert len(result) == 1
        assert result[0]["type"] == "text"

    def test_missing_type_defaults_to_text(self):
        raw = {"frames": [{"frame_no": 1, "copy": "x", "visual_brief": "y", "sticker": "z"}]}
        result = _parse_frames(raw)
        assert len(result) == 1
        assert result[0]["type"] == "text"

    def test_missing_frame_no_auto_numbered(self):
        raw = {"frames": [{"type": "poll", "copy": "x", "visual_brief": "y", "sticker": "z"}]}
        result = _parse_frames(raw)
        assert result[0]["frame_no"] == 1

    def test_non_dict_frame_items_skipped(self):
        raw = {"frames": ["bad", 42, None, {"type": "poll", "copy": "x", "visual_brief": "y", "sticker": "z"}]}
        result = _parse_frames(raw)
        assert len(result) == 1

    def test_all_required_fields_present(self):
        raw = {"frames": _sample_frames()}
        result = _parse_frames(raw)
        for frame in result:
            for key in ["frame_no", "type", "copy", "visual_brief", "sticker"]:
                assert key in frame


# ─── generate_story tests ──────────────────────────────────────────────────


class TestGenerateStory:
    def test_returns_dict_with_frames_list(self):
        import json

        payload = json.dumps({"frames": _sample_frames()})
        gw = _make_gateway(text=payload)
        result = generate_story(
            campaign={"goal": "brand awareness"},
            creative_direction={"tone": "playful"},
            domain_context={"industry": "fashion"},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        assert isinstance(result, dict)
        assert "frames" in result
        assert isinstance(result["frames"], list)
        assert len(result["frames"]) == 4

    def test_each_frame_has_required_fields(self):
        import json

        payload = json.dumps({"frames": _sample_frames()})
        gw = _make_gateway(text=payload)
        result = generate_story(
            campaign={"goal": "launch"},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        for frame in result["frames"]:
            for key in ["frame_no", "type", "copy", "visual_brief", "sticker"]:
                assert key in frame
            assert frame["type"] in {"poll", "question", "quiz", "text"}

    def test_uses_tier_large(self):
        gw = _make_gateway(text='{"frames": []}')
        generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        args, kwargs = gw.complete.call_args
        from prachar_shared.ai_gateway import Tier

        assert kwargs["tier"] == Tier.large

    def test_calls_gateway_complete(self):
        gw = _make_gateway(text='{"frames": []}')
        generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        gw.complete.assert_called_once()

    def test_graceful_fallback_on_exception(self):
        gw = MagicMock()
        gw.complete.side_effect = RuntimeError("boom")
        result = generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        assert isinstance(result, dict)
        assert result == {"frames": []}

    def test_graceful_fallback_on_bad_json(self):
        gw = _make_gateway(text="not json at all")
        result = generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        assert isinstance(result, dict)
        assert result == {"frames": []}

    def test_graceful_fallback_on_empty_response(self):
        gw = _make_gateway(text="")
        result = generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        assert result == {"frames": []}

    def test_budget_exceeded_propagates(self):
        gw = MagicMock()
        gw.complete.side_effect = BudgetExceeded("over budget")
        with pytest.raises(BudgetExceeded):
            generate_story(
                campaign={},
                creative_direction={},
                domain_context={},
                gateway=gw,
                tenant_id="t1",
                plan="agency",
            )

    def test_prompt_contains_campaign_context(self):
        gw = _make_gateway(text='{"frames": []}')
        generate_story(
            campaign={"brand_name": "Acme", "goal": "sell shoes"},
            creative_direction={"tone": "bold"},
            domain_context={"industry": "retail"},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        args, kwargs = gw.complete.call_args
        prompt = kwargs["prompt"]
        assert "Acme" in prompt or "sell shoes" in prompt

    def test_task_is_story(self):
        gw = _make_gateway(text='{"frames": []}')
        generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="agency",
        )
        args, kwargs = gw.complete.call_args
        assert kwargs["task"] == "story"

    def test_plan_passed_through(self):
        gw = _make_gateway(text='{"frames": []}')
        generate_story(
            campaign={},
            creative_direction={},
            domain_context={},
            gateway=gw,
            tenant_id="t1",
            plan="growth",
        )
        args, kwargs = gw.complete.call_args
        assert kwargs["plan"] == "growth"
