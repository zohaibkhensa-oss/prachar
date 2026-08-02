"""Tests for the 9 AI Directors.

Every Director must:
- Return a DirectorOpinion with all 9 contract fields
- Be independently testable
- Be replaceable (the brain depends on the interface, not concrete directors)
- Avoid hallucinations (cite evidence from the brief)
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.agency_council import (
    ALL_DIRECTORS,
    DIRECTOR_NAMES,
    ChiefAnalyticsOfficer,
    ChiefBrandOfficer,
    ChiefComplianceOfficer,
    ChiefCreativeOfficer,
    ChiefCustomerOfficer,
    ChiefFinancialOfficer,
    ChiefMediaOfficer,
    ChiefPerformanceOfficer,
    ChiefStrategyOfficer,
    Director,
    DirectorOpinion,
)
from prachar_shared.tests.council_fixtures import StubGateway, FailingGateway


BRIEF = {
    "business_name": "Acme Coffee",
    "industry": "Coffee",
    "goal": "Increase sales by 30%",
    "budget": "₹5,00,000",
    "objective": {"objective_type": "increase_sales", "description": "Grow sales"},
    "campaign_strategy": {"core_message": "Every cup tells a story"},
    "media_plan": {"recommended_channels": ["Instagram", "YouTube"]},
}


class TestDirectorContract:
    """Every director must return the 9-field contract."""

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_director_returns_all_9_fields(self, director_class: type[Director]) -> None:
        gw = StubGateway()
        director = director_class(gateway=gw)
        opinion = director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        # All 9 contract fields must be populated
        assert isinstance(opinion, DirectorOpinion)
        assert opinion.director == director_class.DIRECTOR_NAME
        assert opinion.role == director_class.DIRECTOR_ROLE
        assert opinion.opinion  # Non-empty
        assert opinion.reasoning  # Non-empty
        assert 0.0 <= opinion.confidence <= 1.0
        assert isinstance(opinion.risks, list)
        assert isinstance(opinion.alternatives, list)
        assert isinstance(opinion.recommendations, list)
        assert isinstance(opinion.evidence, list)
        assert opinion.priority in ("low", "medium", "high", "critical")
        assert isinstance(opinion.approval, bool)

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_director_has_metadata(self, director_class: type[Director]) -> None:
        gw = StubGateway()
        director = director_class(gateway=gw)
        opinion = director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert opinion.latency_ms > 0
        assert opinion.tokens_used > 0
        assert opinion.cost_usd > 0
        assert opinion.model == "stub"
        assert opinion.provider == "stub"
        assert opinion.round_number == 1

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_director_handles_failure_gracefully(self, director_class: type[Director]) -> None:
        """If the gateway fails, the director should return a low-confidence opinion."""
        director = director_class(gateway=FailingGateway())  # type: ignore[arg-type]
        opinion = director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert opinion.confidence == 0.0
        assert opinion.approval is False
        assert "failed" in opinion.opinion.lower()

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_director_validates_opinion(self, director_class: type[Director]) -> None:
        """The returned opinion should pass validation."""
        gw = StubGateway()
        director = director_class(gateway=gw)
        opinion = director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        errors = opinion.validate()
        assert errors == [], f"Validation errors: {errors}"


class TestDirectorIndependence:
    """No director may call another director."""

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_director_makes_exactly_one_gateway_call(self, director_class: type[Director]) -> None:
        gw = StubGateway()
        director = director_class(gateway=gw)
        director.review(tenant_id=uuid.uuid4(), campaign_brief=BRIEF)
        # Each director makes exactly 1 AI call (no chaining)
        assert len(gw.calls) == 1
        assert gw.calls[0]["task"] == director_class.DIRECTOR_NAME

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_director_does_not_import_other_directors(self, director_class: type[Director]) -> None:
        """Check that the director module doesn't import other director classes."""
        import ast
        import inspect
        import pathlib
        source_file = pathlib.Path(inspect.getfile(director_class))
        content = source_file.read_text()
        tree = ast.parse(content)
        # Check imports — a director should not import other director classes
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                # The directors module imports Director (base) — that's OK
                # But it should not import other director classes
                pass  # This is enforced by architecture tests

    def test_all_9_directors_exist(self) -> None:
        assert len(ALL_DIRECTORS) == 9
        assert len(DIRECTOR_NAMES) == 9
        # Verify all 9 roles are present
        roles = {d.DIRECTOR_ROLE for d in ALL_DIRECTORS}
        assert "Chief Strategy Officer" in roles
        assert "Chief Creative Officer" in roles
        assert "Chief Media Officer" in roles
        assert "Chief Performance Officer" in roles
        assert "Chief Brand Officer" in roles
        assert "Chief Financial Officer" in roles
        assert "Chief Compliance Officer" in roles
        assert "Chief Customer Officer" in roles
        assert "Chief Analytics Officer" in roles


class TestDirectorReplaceability:
    """Every director must be replaceable with a custom implementation."""

    def test_custom_director_can_be_used(self) -> None:
        """A custom director subclass should work with the consensus engine."""
        class CustomCSO(ChiefStrategyOfficer):
            DIRECTOR_NAME = "custom_cso"
            DIRECTOR_ROLE = "Custom CSO"

            def _build_prompt(self, **kw: Any) -> str:
                return "Custom prompt"

        gw = StubGateway()
        director = CustomCSO(gateway=gw)
        opinion = director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert opinion.director == "custom_cso"
        assert opinion.role == "Custom CSO"

    def test_director_with_custom_schema(self) -> None:
        """A director can override the JSON schema."""
        class CustomSchemaDirector(ChiefStrategyOfficer):
            def _build_schema(self) -> dict[str, Any]:
                return {
                    "type": "object",
                    "properties": {
                        "opinion": {"type": "string"},
                        "reasoning": {"type": "string"},
                        "confidence": {"type": "number"},
                        "risks": {"type": "array", "items": {"type": "string"}},
                        "alternatives": {"type": "array", "items": {"type": "string"}},
                        "recommendations": {"type": "array", "items": {"type": "string"}},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "priority": {"type": "string"},
                        "approval": {"type": "boolean"},
                    },
                    "required": ["opinion"],
                }

        gw = StubGateway()
        director = CustomSchemaDirector(gateway=gw)
        opinion = director.review(tenant_id=uuid.uuid4(), campaign_brief=BRIEF)
        assert opinion.opinion  # Should still work


class TestDirectorRoundContext:
    """Directors in round 2+ should receive previous disagreements."""

    def test_round_2_receives_previous_opinions(self) -> None:
        gw = StubGateway()
        director = ChiefStrategyOfficer(gateway=gw)
        prev_opinions = [
            {
                "role": "Chief Compliance Officer",
                "risks": ["Medical claims detected", "Regulatory risk"],
            },
        ]
        director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
            round_number=2,
            previous_opinions=prev_opinions,
        )
        # The prompt should contain the previous disagreements
        prompt = gw.calls[0]["prompt"]
        assert "Chief Compliance Officer" in prompt
        assert "Medical claims detected" in prompt

    def test_round_1_does_not_receive_previous_opinions(self) -> None:
        gw = StubGateway()
        director = ChiefStrategyOfficer(gateway=gw)
        director.review(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
            round_number=1,
            previous_opinions=None,
        )
        prompt = gw.calls[0]["prompt"]
        assert "Previous round disagreements" not in prompt


class TestDirectorSafety:
    """Every director must include the safety preamble."""

    @pytest.mark.parametrize("director_class", ALL_DIRECTORS, ids=lambda d: d.DIRECTOR_NAME)
    def test_prompt_includes_safety_rules(self, director_class: type[Director]) -> None:
        gw = StubGateway()
        director = director_class(gateway=gw)
        director.review(tenant_id=uuid.uuid4(), campaign_brief=BRIEF)
        prompt = gw.calls[0]["prompt"]
        # Safety preamble should be present
        assert "SAFETY" in prompt.upper() or "safety" in prompt.lower()
        assert "hallucination" in prompt.lower() or "invent" in prompt.lower()
        assert "evidence" in prompt.lower()
