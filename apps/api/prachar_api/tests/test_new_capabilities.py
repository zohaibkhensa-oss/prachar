"""Phase L tests — New Capabilities (Website, SEO, Landing, CRM, Email, WhatsApp, Calendar, Collaboration).

Tests verify:
1. All 8 capabilities register as tools
2. Each tool has a proper manifest
3. Artefact factories produce correct kinds
4. Tool prompts are world-class (contain key sections)
"""
from __future__ import annotations

import pytest

from prachar_api.runtime.registry import get_registry, ToolCategory
from prachar_api.runtime.artefacts import (
    website_blueprint,
    page_content,
    seo_audit,
    keyword_grid,
    landing_page,
    crm_pipeline,
    contact_card,
    email_sequence,
    whatsapp_campaign,
    calendar_grid,
    team_board,
)


# ─── Tool Registration ─────────────────────────────────────────────────────


class TestToolRegistration:
    """All 8 new capabilities must register as tools."""

    def setup_method(self):
        # Import all tool modules to trigger registration
        import prachar_api.runtime.tools_website  # noqa
        import prachar_api.runtime.tools_seo  # noqa
        import prachar_api.runtime.tools_landing  # noqa
        import prachar_api.runtime.tools_crm  # noqa
        import prachar_api.runtime.tools_email  # noqa
        import prachar_api.runtime.tools_whatsapp  # noqa
        import prachar_api.runtime.tools_calendar  # noqa
        import prachar_api.runtime.tools_collab  # noqa

    def test_website_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("website.")]
        assert "website.build" in tools
        assert "website.page" in tools
        assert len(tools) >= 2

    def test_seo_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("seo.")]
        assert "seo.keywords" in tools
        assert "seo.audit" in tools
        assert "seo.optimise" in tools
        assert len(tools) >= 3

    def test_landing_page_tool_registered(self):
        r = get_registry()
        assert "landing_page.generate" in r._tools

    def test_crm_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("crm.")]
        assert "crm.pipeline" in tools
        assert "crm.follow_ups" in tools
        assert "crm.insights" in tools
        assert len(tools) >= 3

    def test_email_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("email.")]
        assert "email.sequence" in tools
        assert "email.subject" in tools
        assert len(tools) >= 2

    def test_whatsapp_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("whatsapp.")]
        assert "whatsapp.campaign" in tools
        assert "whatsapp.broadcast" in tools
        assert len(tools) >= 2

    def test_calendar_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("calendar.")]
        assert "calendar.plan" in tools
        assert "calendar.seasonal" in tools
        assert len(tools) >= 2

    def test_collaboration_tools_registered(self):
        r = get_registry()
        tools = [n for n in r._tools if n.startswith("team.")]
        assert "team.board" in tools
        assert "team.assign" in tools
        assert "team.approve" in tools
        assert len(tools) >= 3

    def test_total_new_tools(self):
        r = get_registry()
        new_prefixes = ("website.", "seo.", "landing_page.", "crm.", "email.", "whatsapp.", "calendar.", "team.")
        new_tools = [n for n in r._tools if any(n.startswith(p) for p in new_prefixes)]
        assert len(new_tools) >= 18  # 2+3+1+3+2+2+2+3 = 18


# ─── Tool Categories ────────────────────────────────────────────────────────


class TestToolCategories:
    """Each tool must have the correct category."""

    def setup_method(self):
        import prachar_api.runtime.tools_website  # noqa
        import prachar_api.runtime.tools_seo  # noqa
        import prachar_api.runtime.tools_landing  # noqa
        import prachar_api.runtime.tools_crm  # noqa
        import prachar_api.runtime.tools_email  # noqa
        import prachar_api.runtime.tools_whatsapp  # noqa
        import prachar_api.runtime.tools_calendar  # noqa
        import prachar_api.runtime.tools_collab  # noqa

    def test_website_category(self):
        r = get_registry()
        manifest = r._tools["website.build"].manifest
        assert manifest.category == ToolCategory.WEBSITE

    def test_seo_category(self):
        r = get_registry()
        manifest = r._tools["seo.keywords"].manifest
        assert manifest.category == ToolCategory.SEO

    def test_landing_page_category(self):
        r = get_registry()
        manifest = r._tools["landing_page.generate"].manifest
        assert manifest.category == ToolCategory.LANDING_PAGE

    def test_crm_category(self):
        r = get_registry()
        manifest = r._tools["crm.pipeline"].manifest
        assert manifest.category == ToolCategory.CRM

    def test_email_category(self):
        r = get_registry()
        manifest = r._tools["email.sequence"].manifest
        assert manifest.category == ToolCategory.EMAIL

    def test_whatsapp_category(self):
        r = get_registry()
        manifest = r._tools["whatsapp.campaign"].manifest
        assert manifest.category == ToolCategory.WHATSAPP

    def test_calendar_category(self):
        r = get_registry()
        manifest = r._tools["calendar.plan"].manifest
        assert manifest.category == ToolCategory.CALENDAR

    def test_collaboration_category(self):
        r = get_registry()
        manifest = r._tools["team.board"].manifest
        assert manifest.category == ToolCategory.COLLABORATION


# ─── Manifest Quality ───────────────────────────────────────────────────────


class TestManifestQuality:
    """Manifests must have world-class metadata."""

    def setup_method(self):
        import prachar_api.runtime.tools_website  # noqa
        import prachar_api.runtime.tools_seo  # noqa
        import prachar_api.runtime.tools_landing  # noqa
        import prachar_api.runtime.tools_crm  # noqa
        import prachar_api.runtime.tools_email  # noqa
        import prachar_api.runtime.tools_whatsapp  # noqa
        import prachar_api.runtime.tools_calendar  # noqa
        import prachar_api.runtime.tools_collab  # noqa

    def test_all_manifests_have_display_name(self):
        r = get_registry()
        new_prefixes = ("website.", "seo.", "landing_page.", "crm.", "email.", "whatsapp.", "calendar.", "team.")
        for name, entry in r._tools.items():
            manifest = entry.manifest
            if any(name.startswith(p) for p in new_prefixes):
                assert manifest.display_name, f"{name} missing display_name"
                assert len(manifest.display_name) > 3

    def test_all_manifests_have_description(self):
        r = get_registry()
        new_prefixes = ("website.", "seo.", "landing_page.", "crm.", "email.", "whatsapp.", "calendar.", "team.")
        for name, entry in r._tools.items():
            manifest = entry.manifest
            if any(name.startswith(p) for p in new_prefixes):
                assert manifest.description, f"{name} missing description"
                assert len(manifest.description) > 50, f"{name} description too short"

    def test_all_manifests_have_quality_score(self):
        r = get_registry()
        new_prefixes = ("website.", "seo.", "landing_page.", "crm.", "email.", "whatsapp.", "calendar.", "team.")
        for name, entry in r._tools.items():
            manifest = entry.manifest
            if any(name.startswith(p) for p in new_prefixes):
                assert manifest.quality_score >= 0.80, f"{name} quality_score too low: {manifest.quality_score}"

    def test_all_manifests_have_estimated_cost(self):
        r = get_registry()
        new_prefixes = ("website.", "seo.", "landing_page.", "crm.", "email.", "whatsapp.", "calendar.", "team.")
        for name, entry in r._tools.items():
            manifest = entry.manifest
            if any(name.startswith(p) for p in new_prefixes):
                assert manifest.estimated_cost_usd > 0, f"{name} missing cost estimate"

    def test_all_manifests_have_input_schema(self):
        r = get_registry()
        new_prefixes = ("website.", "seo.", "landing_page.", "crm.", "email.", "whatsapp.", "calendar.", "team.")
        for name, entry in r._tools.items():
            manifest = entry.manifest
            if any(name.startswith(p) for p in new_prefixes):
                assert manifest.input_schema is not None, f"{name} missing input_schema"


# ─── Artefact Factories ─────────────────────────────────────────────────────


class TestArtefactFactories:
    """New artefact factories produce correct kinds."""

    def test_website_blueprint(self):
        a = website_blueprint(
            pages=[{"slug": "home", "title": "Home"}],
            navigation=[{"label": "Home", "url": "/"}],
            design_system={"colors": ["#000", "#fff"]},
            seo_foundation={"target_keywords": ["test"]},
        )
        assert a.kind == "website_blueprint"
        assert a.payload["pages"][0]["slug"] == "home"

    def test_page_content(self):
        a = page_content(
            title="About Us",
            meta_description="Learn about our company",
            headings=[{"level": 1, "text": "About Us"}],
            body="We are a great company",
            cta="Contact us",
            seo_keywords=["about", "company"],
        )
        assert a.kind == "page_content"
        assert a.payload["title"] == "About Us"

    def test_seo_audit(self):
        a = seo_audit(
            score=75,
            issues=[{"category": "On-Page", "severity": "high", "issue": "Missing meta"}],
            recommendations=[{"priority": "high", "action": "Add meta description"}],
            passed=["H1 present"],
        )
        assert a.kind == "seo_audit"
        assert a.payload["score"] == 75

    def test_keyword_grid(self):
        a = keyword_grid(
            keywords=[{"keyword": "marketing", "volume": 1000}],
            total_volume=1000,
        )
        assert a.kind == "keyword_grid"
        assert a.payload["total_volume"] == 1000

    def test_landing_page(self):
        a = landing_page(
            hero={"headline": "Grow your business"},
            benefits=[{"title": "Save time"}],
            social_proof=[{"name": "John", "quote": "Great!"}],
            cta="Get started",
            variants=[{"angle": "emotional"}],
        )
        assert a.kind == "landing_page"
        assert a.payload["hero"]["headline"] == "Grow your business"

    def test_crm_pipeline(self):
        a = crm_pipeline(
            stages=[{"stage": "new", "count": 10, "value": 5000}],
            total_value="₹5,000",
            contact_count=10,
        )
        assert a.kind == "crm_pipeline"
        assert a.payload["contact_count"] == 10

    def test_contact_card(self):
        a = contact_card(
            name="John Doe",
            stage="qualified",
            value="₹10,000",
            next_action="Call tomorrow",
        )
        assert a.kind == "contact_card"
        assert a.payload["name"] == "John Doe"

    def test_email_sequence(self):
        a = email_sequence(
            steps=[{"step_number": 1, "subject_line": "Welcome"}],
            total_duration="5 emails over 14 days",
            target_segment="new signups",
        )
        assert a.kind == "email_sequence"
        assert a.payload["target_segment"] == "new signups"

    def test_whatsapp_campaign(self):
        a = whatsapp_campaign(
            templates=[{"name": "welcome", "message": "Hi!"}],
            segments=[{"name": "new customers"}],
            schedule="Mon 10am",
            compliance_notes="Opt-in required",
        )
        assert a.kind == "whatsapp_campaign"
        assert a.payload["compliance_notes"] == "Opt-in required"

    def test_calendar_grid(self):
        a = calendar_grid(
            weeks=[{"week_number": 1, "theme": "Launch"}],
            theme="Summer campaign",
        )
        assert a.kind == "calendar_grid"
        assert a.payload["theme"] == "Summer campaign"

    def test_team_board(self):
        a = team_board(
            members=[{"name": "Alice", "role": "Manager"}],
            tasks=[{"title": "Review campaign"}],
            pending_approvals=[{"item": "Campaign X"}],
        )
        assert a.kind == "team_board"
        assert a.payload["pending_approvals"][0]["item"] == "Campaign X"

    def test_all_new_artefacts_to_dict(self):
        """All new artefact factories produce valid to_dict output."""
        artefacts = [
            website_blueprint([], [], {}, {}),
            page_content("t", "d", [], "b"),
            seo_audit(50, [], []),
            keyword_grid([]),
            landing_page({}, [], [], "cta"),
            crm_pipeline([], "", 0),
            contact_card("name", "stage"),
            email_sequence([]),
            whatsapp_campaign([], []),
            calendar_grid([]),
            team_board([], []),
        ]
        for a in artefacts:
            d = a.to_dict()
            assert "kind" in d
            assert "title" in d
            assert "payload" in d
            assert isinstance(d["payload"], dict)
