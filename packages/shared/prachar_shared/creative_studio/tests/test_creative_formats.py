"""Tests for the Creative Studio spec registry and all 10 format specs."""
from __future__ import annotations

import pytest

from prachar_shared.creative_studio import (
    CreativeFormatRegistry,
    CreativeFormatSpec,
    register_all,
)
from prachar_shared.creative_studio.formats import ALL_FORMATS

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

REQUIRED_FIELDS = ["id", "label", "description", "output_schema", "prompt_template", "max_tokens", "tier"]

PLACEHOLDERS = ["{campaign}", "{creative_direction}", "{domain_context}"]


@pytest.fixture()
def registry() -> CreativeFormatRegistry:
    """Fresh registry with all formats registered.

    register_all() populates the singleton via get_registry(), so we return
    that singleton instance after clearing + re-registering.
    """
    from prachar_shared.creative_studio import get_registry

    reg = get_registry()
    reg.clear()
    register_all()
    return reg


# ─── Registry tests ────────────────────────────────────────────────────────


class TestRegistry:
    def test_all_10_formats_registered(self, registry: CreativeFormatRegistry):
        assert len(registry.all()) == 10

    def test_registry_ids_match_expected(self, registry: CreativeFormatRegistry):
        assert sorted(registry.ids()) == sorted(EXPECTED_IDS)

    def test_get_returns_spec_by_id(self, registry: CreativeFormatRegistry):
        spec = registry.get("poster")
        assert spec is not None
        assert spec.id == "poster"
        assert spec.label == "Poster"

    def test_get_returns_none_for_unknown(self, registry: CreativeFormatRegistry):
        assert registry.get("nonexistent") is None

    def test_get_required_raises_for_unknown(self, registry: CreativeFormatRegistry):
        with pytest.raises(KeyError):
            registry.get_required("nonexistent")

    def test_get_required_returns_spec(self, registry: CreativeFormatRegistry):
        spec = registry.get_required("email")
        assert spec.id == "email"

    def test_all_formats_list_matches_all_formats_constant(self, registry: CreativeFormatRegistry):
        reg_ids = sorted(registry.ids())
        const_ids = sorted(s.id for s in ALL_FORMATS)
        assert reg_ids == const_ids

    def test_singleton_instance(self):
        a = CreativeFormatRegistry.instance()
        b = CreativeFormatRegistry.instance()
        assert a is b


# ─── Per-spec tests ────────────────────────────────────────────────────────


class TestSpecFields:
    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_has_required_fields(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        for field_name in REQUIRED_FIELDS:
            assert hasattr(spec, field_name), f"{spec_id} missing field {field_name}"

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_id_is_nonempty_string(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        assert isinstance(spec.id, str) and spec.id

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_label_is_nonempty_string(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        assert isinstance(spec.label, str) and spec.label

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_description_is_nonempty_string(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        assert isinstance(spec.description, str) and spec.description

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_output_schema_is_dict(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        assert isinstance(spec.output_schema, dict)
        assert "properties" in spec.output_schema

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_prompt_template_has_placeholders(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        for ph in PLACEHOLDERS:
            assert ph in spec.prompt_template, f"{spec_id} prompt missing {ph}"

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_max_tokens_positive(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        assert isinstance(spec.max_tokens, int) and spec.max_tokens > 0

    @pytest.mark.parametrize("spec_id", EXPECTED_IDS)
    def test_spec_tier_valid(self, registry: CreativeFormatRegistry, spec_id: str):
        spec = registry.get_required(spec_id)
        assert spec.tier in ("free", "pro", "enterprise")


# ─── Schema-specific tests ─────────────────────────────────────────────────


class TestSchemas:
    def test_poster_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("poster").output_schema["properties"]
        for key in ["headline", "subheadline", "body", "cta", "visual_brief", "color_palette", "layout_hint"]:
            assert key in props

    def test_video_script_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("video_script").output_schema["properties"]
        assert "scenes" in props
        assert "music_mood" in props
        assert "total_duration" in props
        scene_props = props["scenes"]["items"]["properties"]
        for key in ["scene_no", "visual", "voiceover", "on_screen_text", "duration"]:
            assert key in scene_props

    def test_carousel_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("carousel").output_schema["properties"]
        assert "slides" in props
        assert "cta_slide" in props
        slide_props = props["slides"]["items"]["properties"]
        for key in ["slide_no", "headline", "body", "visual_brief"]:
            assert key in slide_props

    def test_story_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("story").output_schema["properties"]
        assert "frames" in props
        frame_props = props["frames"]["items"]["properties"]
        for key in ["frame_no", "type", "copy", "visual_brief", "sticker"]:
            assert key in frame_props
        assert set(frame_props["type"]["enum"]) == {"poll", "question", "quiz", "text"}

    def test_whatsapp_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("whatsapp").output_schema["properties"]
        for key in ["status_text", "status_image_brief", "broadcast_message"]:
            assert key in props

    def test_facebook_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("facebook").output_schema["properties"]
        for key in ["copy", "image_brief", "link_description"]:
            assert key in props
        assert props["copy"]["maxLength"] == 500

    def test_linkedin_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("linkedin").output_schema["properties"]
        for key in ["hook", "body", "cta", "hashtags"]:
            assert key in props
        assert props["body"]["maxLength"] == 3000

    def test_email_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("email").output_schema["properties"]
        for key in ["subject_lines", "preview_text", "body_html_brief", "cta", "ps_line"]:
            assert key in props
        assert props["subject_lines"]["minItems"] == 3
        assert props["subject_lines"]["maxItems"] == 3

    def test_landing_page_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("landing_page").output_schema["properties"]
        for key in ["hero_headline", "hero_subhead", "benefits", "social_proof_section", "faq", "cta", "form_fields"]:
            assert key in props
        assert props["benefits"]["minItems"] == 3
        assert props["benefits"]["maxItems"] == 3

    def test_sms_schema(self, registry: CreativeFormatRegistry):
        props = registry.get_required("sms").output_schema["properties"]
        assert "variants" in props
        assert "opt_out_language" in props
        variant_props = props["variants"]["items"]["properties"]
        for key in ["char_count", "message"]:
            assert key in variant_props
        assert props["variants"]["minItems"] == 2
        assert props["variants"]["maxItems"] == 2


# ─── Spec immutability ────────────────────────────────────────────────────


class TestImmutability:
    def test_spec_is_frozen(self, registry: CreativeFormatRegistry):
        spec = registry.get_required("poster")
        with pytest.raises(Exception):
            spec.id = "mutated"  # type: ignore[misc]
