"""Tests for the Creative Studio generation engine (studio.py)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from prachar_shared.ai_gateway import Completion
from prachar_shared.creative_studio import CreativeFormatRegistry, register_all
from prachar_shared.creative_studio.studio import CreativePackage, CreativeStudio

# Ensure all formats are registered
register_all()

EXPECTED_IDS = [
    "poster",
    "video_script",
    "carousel",
    "story",
    "whatsapp",
    "facebook",
    "linkedin",
    "email",
    "landing_page",
    "sms",
]


# ─── Fixtures ──────────────────────────────────────────────────────────────


def _make_completion(text: str, tokens: int = 100) -> Completion:
    return Completion(
        text=text,
        tokens_used=tokens,
        model="test-model",
        confidence=0.9,
    )


@pytest.fixture()
def registry() -> CreativeFormatRegistry:
    reg = CreativeFormatRegistry()
    reg.clear()
    register_all()
    return reg


@pytest.fixture()
def mock_gateway():
    """A MagicMock AIGateway whose complete() returns valid JSON per format."""

    def fake_complete(prompt, **kwargs):
        # Return a minimal valid JSON matching the format id from the task name
        task = kwargs.get("task", "")
        fmt_id = task.replace("creative_studio_", "") if task else "poster"
        payload = {"format": fmt_id, "headline": f"Test {fmt_id} headline", "cta": "Buy now"}
        return _make_completion(json.dumps(payload), tokens=50)

    gw = MagicMock()
    gw.complete = MagicMock(side_effect=fake_complete)
    return gw


@pytest.fixture()
def failing_gateway():
    """A gateway where the 'poster' format raises but others succeed."""

    def fake_complete(prompt, **kwargs):
        task = kwargs.get("task", "")
        fmt_id = task.replace("creative_studio_", "") if task else "poster"
        if fmt_id == "poster":
            raise RuntimeError("poster generation exploded")
        payload = {"format": fmt_id, "headline": f"Test {fmt_id} headline"}
        return _make_completion(json.dumps(payload), tokens=50)

    gw = MagicMock()
    gw.complete = MagicMock(side_effect=fake_complete)
    return gw


@pytest.fixture()
def sample_campaign() -> dict:
    return {
        "id": "camp-123",
        "name": "Summer Sale Campaign",
        "goal": "increase sales",
        "budget": "₹50,000",
        "preview": {"title": "Summer Sale"},
    }


@pytest.fixture()
def sample_creative_direction() -> dict:
    return {
        "id": "cd-456",
        "hook": "Beat the heat",
        "angle": "Urgency + value",
        "tone": "energetic",
        "sample_headline": "Summer's hottest deals",
        "sample_cta": "Shop now",
    }


@pytest.fixture()
def sample_domain_context() -> dict:
    return {
        "id": "business",
        "label": "Business Growth",
        "customer_type": "business",
    }


# ─── CreativePackage dataclass ─────────────────────────────────────────────


class TestCreativePackage:
    def test_to_dict_roundtrip(self):
        pkg = CreativePackage(
            id="pkg-1",
            campaign_id="camp-1",
            creative_direction_id="cd-1",
            formats={"poster": {"headline": "Hi"}},
            generated_at="2024-01-01T00:00:00Z",
            total_tokens=500,
        )
        d = pkg.to_dict()
        assert d["id"] == "pkg-1"
        assert d["campaign_id"] == "camp-1"
        assert d["creative_direction_id"] == "cd-1"
        assert d["formats"] == {"poster": {"headline": "Hi"}}
        assert d["generated_at"] == "2024-01-01T00:00:00Z"
        assert d["total_tokens"] == 500

    def test_defaults(self):
        pkg = CreativePackage(id="p", campaign_id="c", creative_direction_id="d")
        assert pkg.formats == {}
        assert pkg.total_tokens == 0
        assert pkg.generated_at == ""


# ─── generate_all ──────────────────────────────────────────────────────────


class TestGenerateAll:
    async def test_returns_creative_package_with_10_formats(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        pkg = await studio.generate_all(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        assert isinstance(pkg, CreativePackage)
        assert len(pkg.formats) == 10
        for fid in EXPECTED_IDS:
            assert fid in pkg.formats
            assert "error" not in pkg.formats[fid]

    async def test_package_ids_from_campaign_and_direction(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        pkg = await studio.generate_all(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        assert pkg.campaign_id == "camp-123"
        assert pkg.creative_direction_id == "cd-456"

    async def test_generated_at_is_set(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        pkg = await studio.generate_all(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        assert pkg.generated_at != ""

    async def test_total_tokens_accumulated(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        pkg = await studio.generate_all(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        # 10 formats × 50 tokens each
        assert pkg.total_tokens == 500

    async def test_to_dict_serialisable(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        pkg = await studio.generate_all(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        d = pkg.to_dict()
        # Must be JSON serialisable
        json.dumps(d)


# ─── generate_one ──────────────────────────────────────────────────────────


class TestGenerateOne:
    async def test_returns_single_format(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        result = await studio.generate_one(
            "poster",
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        assert isinstance(result, dict)
        assert result.get("format") == "poster"

    async def test_unknown_format_raises(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        with pytest.raises(KeyError):
            await studio.generate_one(
                "nonexistent",
                sample_campaign,
                sample_creative_direction,
                sample_domain_context,
            )

    async def test_no_internal_tokens_key_in_output(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        result = await studio.generate_one(
            "email",
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        assert "_tokens" not in result


# ─── Error handling ────────────────────────────────────────────────────────


class TestErrorHandling:
    async def test_one_format_failure_does_not_break_others(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(failing_gateway)
        pkg = await studio.generate_all(
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        # Still 10 formats
        assert len(pkg.formats) == 10
        # Poster failed
        assert "error" in pkg.formats["poster"]
        assert "poster generation exploded" in pkg.formats["poster"]["error"]
        # All other 9 succeeded
        for fid in EXPECTED_IDS:
            if fid == "poster":
                continue
            assert "error" not in pkg.formats[fid]
            assert pkg.formats[fid].get("format") == fid

    async def test_generate_one_propagates_error_as_dict(
        self,
        failing_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        """generate_one wraps errors too (via _generate_safe)."""
        studio = CreativeStudio(failing_gateway)
        result = await studio.generate_one(
            "poster",
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        assert "error" in result


# ─── Prompt template filling ───────────────────────────────────────────────


class TestPromptTemplate:
    async def test_placeholders_are_filled(
        self,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        """The prompt passed to the gateway must have all placeholders filled."""
        captured_prompts: list[str] = []

        def fake_complete(prompt, **kwargs):
            captured_prompts.append(prompt)
            return _make_completion(json.dumps({"headline": "x"}), tokens=10)

        gw = MagicMock()
        gw.complete = MagicMock(side_effect=fake_complete)
        studio = CreativeStudio(gw)

        await studio.generate_one(
            "poster",
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        # No unfilled placeholders
        assert "{campaign}" not in prompt
        assert "{creative_direction}" not in prompt
        assert "{domain_context}" not in prompt
        # Campaign content is present
        assert "Summer Sale Campaign" in prompt
        # Creative direction content is present
        assert "Beat the heat" in prompt
        # Domain context content is present
        assert "Business Growth" in prompt

    def test_all_10_specs_have_three_placeholders(self, registry):
        """Every registered spec must have the 3 required placeholders."""
        for spec in registry.all():
            assert "{campaign}" in spec.prompt_template, f"{spec.id} missing {{campaign}}"
            assert "{creative_direction}" in spec.prompt_template, f"{spec.id} missing {{creative_direction}}"
            assert "{domain_context}" in spec.prompt_template, f"{spec.id} missing {{domain_context}}"

    async def test_gateway_called_with_correct_tier_and_max_tokens(
        self,
        mock_gateway,
        sample_campaign,
        sample_creative_direction,
        sample_domain_context,
    ):
        studio = CreativeStudio(mock_gateway)
        await studio.generate_one(
            "poster",
            sample_campaign,
            sample_creative_direction,
            sample_domain_context,
        )
        call_kwargs = mock_gateway.complete.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1200  # poster spec max_tokens
        assert call_kwargs["task"] == "creative_studio_poster"
