"""Tests for the DomainModel base class (Phase 3: Architecture Stabilisation).

Verifies that domain models own serialization:
- from_dict() with unknown-key filtering
- from_dict() with version checking
- to_dict() roundtrip
- validate() hook
- schema_version() class method
"""
from __future__ import annotations

import pytest

from prachar_shared.marketing_intelligence import (
    AudienceProfile,
    BudgetEstimate,
    BusinessProfile,
    CampaignStrategy,
    CompetitorProfile,
    CreativeDirection,
    DomainModel,
    ExecutionPlan,
    LearningReport,
    MarketingObjective,
    MediaPlan,
    VersionMismatchError,
)


class TestDomainModelBase:
    def test_from_dict_none_returns_default(self) -> None:
        profile = BusinessProfile.from_dict(None)
        assert profile.industry == ""
        assert profile.strengths == []

    def test_from_dict_filters_unknown_keys(self) -> None:
        profile = BusinessProfile.from_dict({
            "industry": "Coffee",
            "unknown_key": "value",
            "another_unknown": 123,
        })
        assert profile.industry == "Coffee"
        assert not hasattr(profile, "unknown_key")

    def test_from_dict_handles_non_dict(self) -> None:
        profile = BusinessProfile.from_dict("not a dict")  # type: ignore[arg-type]
        assert profile.industry == ""

    def test_to_dict_roundtrip(self) -> None:
        original = BusinessProfile(
            industry="Coffee",
            usp="Direct trade",
            strengths=["Quality", "Story"],
        )
        d = original.to_dict()
        restored = BusinessProfile.from_dict(d)
        assert restored.industry == "Coffee"
        assert restored.usp == "Direct trade"
        assert restored.strengths == ["Quality", "Story"]

    def test_schema_version_classmethod(self) -> None:
        assert BusinessProfile.schema_version() == "1.0.0"
        assert CampaignStrategy.schema_version() == "2.0.0"  # Bumped in Phase 1

    def test_validate_default_returns_empty(self) -> None:
        profile = BusinessProfile()
        assert profile.validate() == []

    def test_version_mismatch_raises(self) -> None:
        """from_dict should raise on incompatible schema versions."""
        # CampaignStrategy MIN_SUPPORTED_VERSION is "1.0.0" by default
        # A version "0.9.0" should raise
        with pytest.raises(VersionMismatchError):
            CampaignStrategy.from_dict({
                "schema_version": "0.9.0",
                "core_message": "test",
            })

    def test_version_compatible_does_not_raise(self) -> None:
        """from_dict should accept compatible versions."""
        strat = CampaignStrategy.from_dict({
            "schema_version": "2.0.0",
            "core_message": "test",
        })
        assert strat.core_message == "test"

    def test_no_declared_version_does_not_raise(self) -> None:
        """from_dict should not raise if no schema_version is declared."""
        strat = CampaignStrategy.from_dict({"core_message": "test"})
        assert strat.core_message == "test"


class TestAllModelsInheritDomainModel:
    """Verify every domain model inherits from DomainModel."""

    def test_business_profile_is_domain_model(self) -> None:
        assert isinstance(BusinessProfile(), DomainModel)

    def test_audience_profile_is_domain_model(self) -> None:
        assert isinstance(AudienceProfile(), DomainModel)

    def test_competitor_profile_is_domain_model(self) -> None:
        assert isinstance(CompetitorProfile(), DomainModel)

    def test_marketing_objective_is_domain_model(self) -> None:
        assert isinstance(MarketingObjective(), DomainModel)

    def test_campaign_strategy_is_domain_model(self) -> None:
        assert isinstance(CampaignStrategy(), DomainModel)

    def test_creative_direction_is_domain_model(self) -> None:
        assert isinstance(CreativeDirection(), DomainModel)

    def test_media_plan_is_domain_model(self) -> None:
        assert isinstance(MediaPlan(), DomainModel)

    def test_budget_estimate_is_domain_model(self) -> None:
        assert isinstance(BudgetEstimate(), DomainModel)

    def test_execution_plan_is_domain_model(self) -> None:
        assert isinstance(ExecutionPlan(), DomainModel)

    def test_learning_report_is_domain_model(self) -> None:
        assert isinstance(LearningReport(), DomainModel)


class TestCampaignStrategyValidation:
    """CampaignStrategy has a custom validate() — test it."""

    def test_valid_strategy(self) -> None:
        strat = CampaignStrategy(
            core_message="Every cup tells a story",
            communication_theme="Traceability",
        )
        assert strat.validate() == []

    def test_invalid_strategy_missing_core_message(self) -> None:
        strat = CampaignStrategy(core_message="", communication_theme="test")
        errors = strat.validate()
        assert len(errors) == 1
        assert "core_message" in errors[0]

    def test_invalid_strategy_missing_both(self) -> None:
        strat = CampaignStrategy()
        errors = strat.validate()
        assert len(errors) == 2


class TestVersionComparison:
    def test_version_lt(self) -> None:
        assert DomainModel._version_lt("1.0.0", "2.0.0")
        assert DomainModel._version_lt("1.9.9", "2.0.0")
        assert not DomainModel._version_lt("2.0.0", "1.0.0")
        assert not DomainModel._version_lt("2.0.0", "2.0.0")
        assert DomainModel._version_lt("1.0", "1.0.1")  # different lengths

    def test_version_lt_invalid(self) -> None:
        # "invalid" parses to (0,) which is < (1,0,0) — so it IS less than
        assert DomainModel._version_lt("invalid", "1.0.0")
        assert DomainModel._version_lt("0", "1.0.0")
        # Equal invalid versions are not less than
        assert not DomainModel._version_lt("invalid", "invalid")
