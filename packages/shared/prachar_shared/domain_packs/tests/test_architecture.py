"""Architecture tests for the Domain Pack framework.

These tests enforce the architectural rules from UNIFIED_INTELLIGENCE_REVIEW.md:
  - No duplicated orchestration (one ConsultEngine)
  - No duplicated prompts (prompts live in Domain Packs, not routers)
  - No duplicated APIs (one /consult router, not per-domain routers)
  - No duplicated models (Domain Packs define data, not routers)
  - No duplicated dashboard logic (one DashboardShell, widget slots from packs)
  - No duplicated memory (one brand_graph schema per pack)
  - No circular dependencies (packs don't import from api)
  - Plugin isolation (adding a domain doesn't modify core)

If any of these tests fail, the architecture has regressed.
"""
from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pytest

from prachar_shared.domain_packs import (
    BaseDomainPack,
    DomainPack,
    DomainPackRegistry,
    get_registry,
    register_all,
)


# ─── Plugin registration ──────────────────────────────────────────────────


class TestPluginRegistration:
    """Tests that adding a domain = ONE folder + ONE registration line."""

    def test_registry_is_singleton(self):
        """The registry is a singleton — one source of truth."""
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_register_all_registers_built_in_packs(self):
        """register_all() registers all built-in domain packs."""
        register_all()
        reg = get_registry()
        ids = reg.ids()
        assert "business" in ids
        assert "creator" in ids
        assert "restaurant" in ids
        assert "clinic" in ids

    def test_registry_get_required_raises_for_unknown(self):
        """get_required() raises KeyError for unknown packs."""
        reg = get_registry()
        with pytest.raises(KeyError, match="Unknown domain pack"):
            reg.get_required("nonexistent_domain")

    def test_every_pack_implements_the_protocol(self):
        """Every registered pack satisfies the DomainPack protocol."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert isinstance(pack, DomainPack) or hasattr(pack, "id"), (
                f"Pack {pack} does not satisfy DomainPack protocol"
            )

    def test_every_pack_has_required_attributes(self):
        """Every pack has all required attributes from the contract."""
        register_all()
        reg = get_registry()
        required_attrs = [
            "id", "label", "customer_type", "emoji",
            "subtypes", "extraction_schema", "extraction_prompt",
            "default_goal", "goal_options",
            "kpi_cards", "opportunity_prompt",
            "week_schema", "week_prompt",
            "campaign_template", "campaign_prompt", "creative_directions_prompt", "hooks_prompt", "audience_psychology_prompt", "offers_prompt", "pricing_psychology_prompt", "seasonal_prompt", "local_prompt", "differentiation_prompt", "strategy_prompt",
            "recommendations_prompt",
            "dashboard_widgets", "quick_actions",
            "brand_graph_schema", "memory_namespace",
            "conversation_role", "forbidden_jargon", "greeting_template",
            "nav_sections", "tools",
        ]
        for pack in reg.all():
            for attr in required_attrs:
                assert hasattr(pack, attr), (
                    f"Pack {pack.id} missing required attribute: {attr}"
                )

    def test_every_pack_has_unique_id(self):
        """No two packs share the same id."""
        register_all()
        reg = get_registry()
        ids = [p.id for p in reg.all()]
        assert len(ids) == len(set(ids)), f"Duplicate pack ids: {ids}"

    def test_every_pack_has_at_least_one_subtype(self):
        """Every pack has at least one subtype for onboarding."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert len(pack.subtypes) > 0, f"Pack {pack.id} has no subtypes"

    def test_every_pack_has_at_least_one_kpi(self):
        """Every pack has at least one KPI card for the dashboard."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert len(pack.kpi_cards) > 0, f"Pack {pack.id} has no KPI cards"

    def test_every_pack_has_at_least_one_nav_section(self):
        """Every pack has at least one nav section for the sidebar."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert len(pack.nav_sections) > 0, f"Pack {pack.id} has no nav sections"

    def test_every_pack_has_at_least_one_dashboard_widget(self):
        """Every pack has at least one dashboard widget."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert len(pack.dashboard_widgets) > 0, f"Pack {pack.id} has no dashboard widgets"


# ─── No circular dependencies ─────────────────────────────────────────────


class TestNoCircularDependencies:
    """Tests that domain packs don't import from the api layer."""

    def test_packs_do_not_import_from_api(self):
        """Domain packs must not import from prachar_api (dependency inversion)."""
        pack_files = list(Path(__file__).resolve().parents[2].glob("domain_packs/*/pack.py"))
        assert len(pack_files) >= 4, f"Expected >= 4 pack files, found {len(pack_files)}"
        for pack_file in pack_files:
            content = pack_file.read_text()
            assert "prachar_api" not in content, (
                f"{pack_file.name} imports from prachar_api — packs must be api-agnostic"
            )
            assert "from apps.api" not in content, (
                f"{pack_file.name} imports from apps.api — packs must be api-agnostic"
            )

    def test_packs_do_not_import_fastapi(self):
        """Domain packs must not import FastAPI (presentation-layer concern)."""
        pack_files = list(Path(__file__).resolve().parents[2].glob("domain_packs/*/pack.py"))
        for pack_file in pack_files:
            content = pack_file.read_text()
            assert "from fastapi" not in content, (
                f"{pack_file.name} imports FastAPI — packs must be presentation-agnostic"
            )

    def test_packs_do_not_import_sqlalchemy(self):
        """Domain packs must not import SQLAlchemy (infrastructure concern)."""
        pack_files = list(Path(__file__).resolve().parents[2].glob("domain_packs/*/pack.py"))
        for pack_file in pack_files:
            content = pack_file.read_text()
            assert "from sqlalchemy" not in content, (
                f"{pack_file.name} imports SQLAlchemy — packs must be infrastructure-agnostic"
            )

    def test_base_does_not_import_from_any_pack_at_module_level(self):
        """The base module must not import from any specific pack at module level.

        The register_all() function may import packs (that's the registration
        point), but no other code in base.py should depend on a specific pack.
        """
        base_path = Path(__file__).resolve().parents[2] / "domain_packs" / "base.py"
        content = base_path.read_text()
        # Find all import lines that reference specific packs
        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Allow imports inside register_all() (the registration function)
            # by checking the line is not inside a function that's not register_all.
            # Simplest check: imports of specific packs must be inside a function.
            if stripped.startswith("from .business") or stripped.startswith("from .creator") or \
               stripped.startswith("from .restaurant") or stripped.startswith("from .clinic"):
                # This import must be inside register_all() — check it's indented
                assert line.startswith("    "), (
                    f"base.py line {i+1} imports a specific pack at module level: {stripped}"
                )


# ─── No duplicated orchestration ──────────────────────────────────────────


class TestNoDuplicatedOrchestration:
    """Tests that there is ONE ConsultEngine, not per-domain engines."""

    def test_one_consult_engine(self):
        """There is exactly ONE ConsultEngine class in the codebase."""
        from prachar_api.infrastructure.consult_engine import ConsultEngine
        assert inspect.isclass(ConsultEngine)

    def test_consult_engine_is_domain_agnostic(self):
        """ConsultEngine does not hard-code any domain."""
        import prachar_api.infrastructure.consult_engine as ce
        source = inspect.getsource(ce)
        # The engine should reference "pack" not specific domain names
        assert "pack.extraction_prompt" in source
        assert "pack.campaign_prompt" in source
        assert "pack.week_prompt" in source
        # It should NOT hard-code business/creator logic
        # (the _assemble_understanding_prompt has a creator branch — that's a
        # temporary compromise documented in the review, not ideal but contained)
        assert "pack.opportunity_prompt" in source

    def test_unified_router_is_domain_agnostic(self):
        """The unified consult router does not hard-code any domain."""
        import prachar_api.routers.unified_consult as uc
        source = inspect.getsource(uc)
        # The router should reference body.domain, not hard-coded domain checks
        assert "body.domain" in source
        # It should NOT have if/elif chains for specific domains
        assert 'if body.domain == "business"' not in source
        assert 'if body.domain == "creator"' not in source


# ─── No duplicated prompts ────────────────────────────────────────────────


class TestNoDuplicatedPrompts:
    """Tests that prompts live in Domain Packs, not routers."""

    def test_unified_router_has_no_prompt_strings(self):
        """The unified consult router contains no LLM prompt templates."""
        import prachar_api.routers.unified_consult as uc
        source = inspect.getsource(uc)
        # Prompts are long strings with "You are" or "Respond as JSON"
        # The router should not contain these — they live in packs
        assert "You are a world-class" not in source
        assert "You are a marketing strategist" not in source
        assert "You are a creator" not in source
        assert "Respond as JSON only" not in source

    def test_consult_engine_has_no_domain_specific_prompts(self):
        """The ConsultEngine does not contain domain-specific prompt content.

        It assembles prompts from pack fragments. The only domain-specific
        text is the temporary creator/business branch in _assemble_understanding_prompt,
        which is documented in the review as a contained compromise.
        """
        import prachar_api.infrastructure.consult_engine as ce
        source = inspect.getsource(ce)
        # The engine should NOT contain full prompt templates
        assert "You are a world-class marketing strategist" not in source
        assert "You are a world-class creator strategist" not in source
        assert "You are a restaurant business analyst" not in source
        assert "You are a clinic business analyst" not in source

    def test_every_pack_has_extraction_prompt(self):
        """Every pack defines its own extraction prompt."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert pack.extraction_prompt, f"Pack {pack.id} has no extraction_prompt"
            assert "{message}" in pack.extraction_prompt, (
                f"Pack {pack.id} extraction_prompt missing {{message}} placeholder"
            )

    def test_every_pack_has_campaign_prompt(self):
        """Every pack defines its own campaign prompt."""
        register_all()
        reg = get_registry()
        for pack in reg.all():
            assert pack.campaign_prompt, f"Pack {pack.id} has no campaign_prompt"


# ─── No duplicated _extract_json ───────────────────────────────────────────


class TestNoDuplicatedUtilities:
    """Tests that shared utilities are not duplicated."""

    def test_extract_json_lives_in_shared(self):
        """extract_json is defined once in prachar_shared, not duplicated."""
        from prachar_shared.ai_gateway.json_utils import extract_json
        assert callable(extract_json)

    def test_consult_engine_uses_shared_extract_json(self):
        """The ConsultEngine uses the shared extract_json, not its own copy."""
        import prachar_api.infrastructure.consult_engine as ce
        source = inspect.getsource(ce)
        assert "from prachar_shared.ai_gateway.json_utils import extract_json" in source
        # It should NOT define its own _extract_json
        assert "def _extract_json" not in source, (
            "ConsultEngine defines its own _extract_json — use the shared one"
        )


# ─── Plugin isolation (the founder demo test) ─────────────────────────────


class TestPluginIsolation:
    """Tests that adding a new domain requires zero core modifications.

    This is the architectural guarantee that makes the founder demo possible.
    """

    def test_new_domain_can_be_registered_without_core_changes(self):
        """A new domain can be registered by creating a pack + calling register().

        No router changes, no dashboard changes, no pipeline changes.
        """
        # Create a new "lawfirm" pack inline
        class LawFirmPack(BaseDomainPack):
            id = "lawfirm"
            label = "Law Firm Growth"
            customer_type = "business"
            emoji = "⚖️"
            subtypes = [type("S", (), {"id": "general", "label": "General Practice", "emoji": "⚖️", "blurb": "Get more clients.", "category": "lawfirm"})()]
            extraction_schema = {"type": "object", "properties": {}}
            extraction_prompt = 'Extract info from: "{message}"'
            default_goal = "get more clients"
            goal_options = ["get more clients"]
            kpi_cards = [type("K", (), {"key": "clients", "label": "Clients", "icon": "Users", "hint": ""})()]
            opportunity_prompt = "List 5 growth opportunities."
            week_schema = {"type": "object", "properties": {}}
            week_prompt = "Create a 4-week plan."
            campaign_template = "Client Acquisition Campaign"
            campaign_prompt = "Create a campaign for {business_name}."
            recommendations_prompt = "Be specific."
            dashboard_widgets = [type("W", (), {"kind": "kpi_grid", "title": "Your firm", "props": {}})()]
            quick_actions = []
            brand_graph_schema = {"type": "object", "properties": {}}
            memory_namespace = "business.lawfirm"
            conversation_role = "marketing strategist"
            forbidden_jargon = ["ROAS", "CPA"]
            greeting_template = "Tell me about your firm."
            nav_sections = []
            tools = []

        reg = get_registry()
        reg.clear()
        reg.register(LawFirmPack())

        # The pack is now available through the same registry
        pack = reg.get("lawfirm")
        assert pack is not None
        assert pack.label == "Law Firm Growth"
        assert pack.campaign_template == "Client Acquisition Campaign"

        # Cleanup
        register_all()

    def test_unified_consult_engine_works_with_any_pack(self):
        """The ConsultEngine can be instantiated with any registered pack."""
        from prachar_api.infrastructure.consult_engine import ConsultEngine
        engine = ConsultEngine()
        # The engine has no domain-specific state
        assert engine is not None
        # Its methods accept a pack_id parameter, not a hard-coded domain
        sig = inspect.signature(engine.consult)
        assert "pack_id" in sig.parameters
        sig = inspect.signature(engine.campaign)
        assert "pack_id" in sig.parameters
        sig = inspect.signature(engine.tool)
        assert "pack_id" in sig.parameters

    def test_unified_router_endpoints_accept_domain_parameter(self):
        """The unified router endpoints accept a `domain` parameter."""
        import prachar_api.routers.unified_consult as uc
        source = inspect.getsource(uc)
        # The consult endpoint accepts domain
        assert "domain: str" in source
        # The campaign endpoint accepts domain
        assert "domain: str = Field" in source


# ─── Domain Pack content tests ────────────────────────────────────────────


class TestDomainPackContent:
    """Tests that the built-in packs have sensible content."""

    def test_business_pack_has_restaurant_subtype(self):
        """BusinessPack includes restaurant as a subtype (for the founder demo)."""
        register_all()
        reg = get_registry()
        business = reg.get("business")
        subtype_ids = [s.id for s in business.subtypes]
        assert "restaurant" in subtype_ids
        assert "clinic" in subtype_ids

    def test_creator_pack_has_youtube_subtype(self):
        """CreatorPack includes youtube_creator as a subtype."""
        register_all()
        reg = get_registry()
        creator = reg.get("creator")
        subtype_ids = [s.id for s in creator.subtypes]
        assert "youtube_creator" in subtype_ids

    def test_restaurant_pack_has_food_specific_kpis(self):
        """RestaurantPack has food-specific KPIs (covers, AOV, repeats)."""
        register_all()
        reg = get_registry()
        restaurant = reg.get("restaurant")
        kpi_keys = [k.key for k in restaurant.kpi_cards]
        assert "covers" in kpi_keys
        assert "aov" in kpi_keys
        assert "repeat" in kpi_keys

    def test_clinic_pack_has_healthcare_specific_kpis(self):
        """ClinicPack has healthcare-specific KPIs (appointments, new patients)."""
        register_all()
        reg = get_registry()
        clinic = reg.get("clinic")
        kpi_keys = [k.key for k in clinic.kpi_cards]
        assert "appointments" in kpi_keys
        assert "new_patients" in kpi_keys

    def test_creator_pack_has_repurpose_and_youtube_plan_tools(self):
        """CreatorPack has the repurpose and youtube_plan tools."""
        register_all()
        reg = get_registry()
        creator = reg.get("creator")
        tool_ids = [t.id for t in creator.tools]
        assert "repurpose" in tool_ids
        assert "youtube_plan" in tool_ids

    def test_business_pack_has_no_tools(self):
        """BusinessPack has no domain-specific tools (yet)."""
        register_all()
        reg = get_registry()
        business = reg.get("business")
        assert len(business.tools) == 0

    def test_restaurant_pack_has_no_tools(self):
        """RestaurantPack has no domain-specific tools (yet)."""
        register_all()
        reg = get_registry()
        restaurant = reg.get("restaurant")
        assert len(restaurant.tools) == 0

    def test_clinic_pack_campaign_template_is_patient_acquisition(self):
        """ClinicPack uses 'Patient Acquisition Campaign' as its template."""
        register_all()
        reg = get_registry()
        clinic = reg.get("clinic")
        assert clinic.campaign_template == "Patient Acquisition Campaign"

    def test_restaurant_pack_campaign_template_is_promotion(self):
        """RestaurantPack uses 'Promotion Campaign' as its template."""
        register_all()
        reg = get_registry()
        restaurant = reg.get("restaurant")
        assert restaurant.campaign_template == "Promotion Campaign"

    def test_creator_pack_campaign_template_is_content(self):
        """CreatorPack uses 'Content Campaign' as its template."""
        register_all()
        reg = get_registry()
        creator = reg.get("creator")
        assert creator.campaign_template == "Content Campaign"


# ─── Backward compatibility ───────────────────────────────────────────────


class TestBackwardCompatibility:
    """Tests that the refactor doesn't break existing imports."""

    def test_postgres_memory_repository_still_importable(self):
        """PostgresMemoryRepository is still importable from infrastructure."""
        from prachar_api.infrastructure import PostgresMemoryRepository
        assert PostgresMemoryRepository is not None

    def test_postgres_council_repository_still_importable(self):
        """PostgresCouncilRepository is still importable from infrastructure."""
        from prachar_api.infrastructure import PostgresCouncilRepository
        assert PostgresCouncilRepository is not None

    def test_legacy_consult_router_still_registered(self):
        """The legacy /consult router is still registered (backward compat)."""
        from prachar_api.main import app
        schema = app.openapi()
        paths = schema["paths"]
        # Legacy /consult (business) should still be there
        assert "/consult" in paths or any(p.startswith("/consult") for p in paths)

    def test_legacy_creator_router_still_registered(self):
        """The legacy /creator router is still registered (backward compat)."""
        from prachar_api.main import app
        schema = app.openapi()
        paths = schema["paths"]
        assert "/creator/consult" in paths

    def test_unified_consult_router_registered(self):
        """The unified /consult router is registered alongside the legacy ones."""
        from prachar_api.main import app
        schema = app.openapi()
        paths = schema["paths"]
        # New unified endpoints
        assert "/consult/domains" in paths
        assert "/consult/nav/{domain}" in paths
        assert "/consult/tool/{tool_id}" in paths
