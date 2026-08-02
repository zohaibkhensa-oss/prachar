"""Phase I2 tests — Creative Studio Intelligence.

Tests that all creative formats include agency-quality fields:
- rationale (why this creative works)
- brand_alignment (score + reason)
- ab_variants (alternative angles for testing)
- Platform-specific guidance
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from prachar_shared.creative_studio.formats.poster import _normalise as normalise_poster
from prachar_shared.creative_studio.formats.video_script import _parse_video_script as normalise_video
from prachar_shared.creative_studio.formats.whatsapp import _normalise as normalise_whatsapp
from prachar_shared.creative_studio.formats.facebook import _parse_facebook as normalise_facebook
from prachar_shared.creative_studio.formats.linkedin import _parse_linkedin as normalise_linkedin


class TestPosterIntelligence:
    """Poster format includes agency-quality fields."""

    def test_poster_normalise_includes_rationale(self):
        raw = {
            "headline": "Summer Sale",
            "subheadline": "Up to 50% off",
            "body": "Shop the best deals",
            "cta": "Shop Now",
            "visual_brief": "Bright summer colors",
            "color_palette": ["#FF6B6B", "#FFD93D"],
            "layout_hint": "Hero top 60%",
            "rationale": "Warm colors evoke summer urgency",
        }
        result = normalise_poster(raw)
        assert result["rationale"] == "Warm colors evoke summer urgency"

    def test_poster_normalise_includes_brand_alignment(self):
        raw = {
            "headline": "Test",
            "brand_alignment": {"score": 8, "reason": "Matches brand voice"},
        }
        result = normalise_poster(raw)
        assert result["brand_alignment"]["score"] == 8
        assert result["brand_alignment"]["reason"] == "Matches brand voice"

    def test_poster_normalise_includes_ab_variants(self):
        raw = {
            "headline": "Test",
            "ab_variants": [
                {"angle": "emotional", "headline": "Feel the difference"},
                {"angle": "rational", "headline": "Save 50% today"},
            ],
        }
        result = normalise_poster(raw)
        assert len(result["ab_variants"]) == 2
        assert result["ab_variants"][0]["angle"] == "emotional"

    def test_poster_normalise_includes_cta_optimisation(self):
        raw = {
            "headline": "Test",
            "cta_optimisation": {
                "primary": "Shop Now",
                "reason": "Direct and actionable",
                "alternative": "Get Yours",
            },
        }
        result = normalise_poster(raw)
        assert result["cta_optimisation"]["primary"] == "Shop Now"
        assert result["cta_optimisation"]["alternative"] == "Get Yours"

    def test_poster_normalise_includes_platform_notes(self):
        raw = {
            "headline": "Test",
            "platform_notes": "Square for IG, vertical for Stories",
        }
        result = normalise_poster(raw)
        assert result["platform_notes"] == "Square for IG, vertical for Stories"

    def test_poster_normalise_defaults_missing_intelligence_fields(self):
        result = normalise_poster({"headline": "Test"})
        assert result["rationale"] == ""
        assert result["brand_alignment"] == {}
        assert result["ab_variants"] == []
        assert result["cta_optimisation"] == {}
        assert result["platform_notes"] == ""


class TestVideoScriptIntelligence:
    """Video script format includes agency-quality fields."""

    def test_video_normalise_includes_rationale(self):
        raw = {
            "scenes": [{"scene_no": 1, "visual": "Opening", "voiceover": "Hi", "on_screen_text": "Welcome", "duration": 5}],
            "music_mood": "upbeat",
            "total_duration": 30,
            "rationale": "Hook in first 5s grabs attention",
        }
        result = normalise_video(raw)
        assert result["rationale"] == "Hook in first 5s grabs attention"

    def test_video_normalise_includes_brand_alignment(self):
        raw = {
            "scenes": [],
            "brand_alignment": {"score": 9, "reason": "Perfect brand fit"},
        }
        result = normalise_video(raw)
        assert result["brand_alignment"]["score"] == 9

    def test_video_normalise_includes_hook_alternatives(self):
        raw = {
            "scenes": [],
            "hook_alternatives": ["What if I told you...", "90% of businesses fail because..."],
        }
        result = normalise_video(raw)
        assert len(result["hook_alternatives"]) == 2

    def test_video_normalise_includes_platform_adaptations(self):
        raw = {
            "scenes": [],
            "platform_adaptations": "YouTube: add chapters. Reels: 15s cut.",
        }
        result = normalise_video(raw)
        assert "YouTube" in result["platform_adaptations"]

    def test_video_normalise_defaults_missing_intelligence_fields(self):
        result = normalise_video({"scenes": []})
        assert result["rationale"] == ""
        assert result["brand_alignment"] == {}
        assert result["hook_alternatives"] == []
        assert result["platform_adaptations"] == ""


class TestWhatsAppIntelligence:
    """WhatsApp format includes agency-quality fields."""

    def test_whatsapp_normalise_includes_rationale(self):
        raw = {
            "status_text": "Limited time offer!",
            "rationale": "Conversational tone feels native to WhatsApp",
        }
        result = normalise_whatsapp(raw)
        assert result["rationale"] == "Conversational tone feels native to WhatsApp"

    def test_whatsapp_normalise_includes_brand_alignment(self):
        raw = {
            "status_text": "Test",
            "brand_alignment": {"score": 7, "reason": "Friendly tone matches brand"},
        }
        result = normalise_whatsapp(raw)
        assert result["brand_alignment"]["score"] == 7

    def test_whatsapp_normalise_includes_ab_variants(self):
        raw = {
            "status_text": "Test",
            "ab_variants": ["Playful: Guess what's coming! 😄", "Urgent: Last day! 🏃"],
        }
        result = normalise_whatsapp(raw)
        assert len(result["ab_variants"]) == 2

    def test_whatsapp_normalise_includes_best_send_time(self):
        raw = {
            "status_text": "Test",
            "best_send_time": "7-9 PM when users are relaxing",
        }
        result = normalise_whatsapp(raw)
        assert "7-9 PM" in result["best_send_time"]

    def test_whatsapp_normalise_defaults_missing_intelligence_fields(self):
        result = normalise_whatsapp({"status_text": "Test"})
        assert result["rationale"] == ""
        assert result["brand_alignment"] == {}
        assert result["ab_variants"] == []
        assert result["best_send_time"] == ""


class TestFacebookIntelligence:
    """Facebook format includes agency-quality fields."""

    def test_facebook_normalise_includes_rationale(self):
        raw = {
            "copy": "Amazing product!",
            "rationale": "Storytelling hook stops the scroll",
        }
        result = normalise_facebook(raw)
        assert result["rationale"] == "Storytelling hook stops the scroll"

    def test_facebook_normalise_includes_brand_alignment(self):
        raw = {
            "copy": "Test",
            "brand_alignment": {"score": 8, "reason": "Authentic voice"},
        }
        result = normalise_facebook(raw)
        assert result["brand_alignment"]["score"] == 8

    def test_facebook_normalise_includes_ab_variants(self):
        raw = {
            "copy": "Test",
            "ab_variants": ["Did you know...", "Here's what nobody tells you..."],
        }
        result = normalise_facebook(raw)
        assert len(result["ab_variants"]) == 2

    def test_facebook_normalise_includes_audience_targeting(self):
        raw = {
            "copy": "Test",
            "audience_targeting": "Small business owners aged 25-45",
        }
        result = normalise_facebook(raw)
        assert "Small business" in result["audience_targeting"]

    def test_facebook_normalise_defaults_missing_intelligence_fields(self):
        result = normalise_facebook({"copy": "Test"})
        assert result["rationale"] == ""
        assert result["brand_alignment"] == {}
        assert result["ab_variants"] == []
        assert result["audience_targeting"] == ""


class TestLinkedInIntelligence:
    """LinkedIn format includes agency-quality fields."""

    def test_linkedin_normalise_includes_rationale(self):
        raw = {
            "hook": "Here's the truth about marketing",
            "body": "Most businesses get this wrong...",
            "cta": "Comment your thoughts",
            "hashtags": ["marketing", "strategy"],
            "rationale": "Contrarian hook drives engagement from professionals",
        }
        result = normalise_linkedin(raw)
        assert result["rationale"] == "Contrarian hook drives engagement from professionals"

    def test_linkedin_normalise_includes_brand_alignment(self):
        raw = {
            "hook": "Test",
            "body": "Test",
            "cta": "Test",
            "hashtags": [],
            "brand_alignment": {"score": 9, "reason": "Thought leadership tone"},
        }
        result = normalise_linkedin(raw)
        assert result["brand_alignment"]["score"] == 9

    def test_linkedin_normalise_includes_ab_variants(self):
        raw = {
            "hook": "Test",
            "body": "Test",
            "cta": "Test",
            "hashtags": [],
            "ab_variants": ["Unpopular opinion...", "I learned this the hard way..."],
        }
        result = normalise_linkedin(raw)
        assert len(result["ab_variants"]) == 2

    def test_linkedin_normalise_includes_target_audience(self):
        raw = {
            "hook": "Test",
            "body": "Test",
            "cta": "Test",
            "hashtags": [],
            "target_audience": "CMOs and marketing directors at B2B SaaS companies",
        }
        result = normalise_linkedin(raw)
        assert "CMOs" in result["target_audience"]

    def test_linkedin_normalise_defaults_missing_intelligence_fields(self):
        result = normalise_linkedin({"hook": "T", "body": "T", "cta": "T", "hashtags": []})
        assert result["rationale"] == ""
        assert result["brand_alignment"] == {}
        assert result["ab_variants"] == []
        assert result["target_audience"] == ""
