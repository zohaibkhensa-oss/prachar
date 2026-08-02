"""Tests for the Consensus Engine.

Tests:
- Weighted consensus (not majority voting)
- Weight calculation by industry/objective/budget/campaign type
- Disagreement calculation
- Minority opinion extraction
- Multi-round review (max 3)
- Self-critique step
- Campaign scoring (7 dimensions + overall)
- Approval status determination
- Tie-breaking
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from prachar_shared.agency_council import (
    ConsensusEngine,
    calculate_disagreement,
    compute_campaign_score,
    compute_weights,
    extract_all_risks,
    extract_disagreements,
    extract_minority_opinions,
    DirectorOpinion,
    CampaignScore,
    ConsensusDecision,
    CouncilSession,
)
from prachar_shared.agency_council.directors import ALL_DIRECTORS
from prachar_shared.tests.council_fixtures import StubGateway


BRIEF = {
    "business_name": "Acme Coffee",
    "industry": "Coffee",
    "goal": "Increase sales by 30%",
    "budget": "₹5,00,000",
    "objective": {"objective_type": "increase_sales"},
    "campaign_strategy": {"core_message": "Every cup tells a story"},
    "media_plan": {"recommended_channels": ["Instagram", "YouTube"]},
}


# ─── Weight calculation tests ───────────────────────────────────────────────


class TestWeightCalculation:
    def test_default_weights_sum_to_one(self) -> None:
        w = compute_weights()
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)

    def test_restaurant_weights(self) -> None:
        w = compute_weights(industry="restaurant")
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)
        # Strategy should have highest weight for restaurants
        assert w["chief_strategy_officer"] > w["chief_compliance_officer"]

    def test_ecommerce_weights(self) -> None:
        w = compute_weights(industry="ecommerce")
        # Performance should be elevated for ecommerce
        assert w["chief_performance_officer"] > w["chief_brand_officer"]

    def test_healthcare_weights(self) -> None:
        w = compute_weights(industry="healthcare")
        # Compliance should be highest for healthcare
        assert w["chief_compliance_officer"] == max(w.values())

    def test_finance_weights(self) -> None:
        w = compute_weights(industry="finance")
        # Compliance and Finance should be elevated
        assert w["chief_compliance_officer"] > 0.15
        assert w["chief_financial_officer"] > 0.10

    def test_objective_adjustment(self) -> None:
        w_default = compute_weights()
        w_sales = compute_weights(objective="increase_sales")
        # Performance should be higher for sales objective
        assert w_sales["chief_performance_officer"] > w_default["chief_performance_officer"]

    def test_brand_awareness_objective(self) -> None:
        w = compute_weights(objective="brand_awareness")
        # Creative should be elevated
        assert w["chief_creative_officer"] > 0.15

    def test_low_budget_increases_cfo_weight(self) -> None:
        w = compute_weights(budget="₹5,000")
        w_normal = compute_weights(budget="₹5,00,000")
        assert w["chief_financial_officer"] > w_normal["chief_financial_officer"]

    def test_high_budget_increases_strategy_weight(self) -> None:
        w = compute_weights(budget="₹50,00,000")
        w_normal = compute_weights(budget="₹5,00,000")
        assert w["chief_strategy_officer"] > w_normal["chief_strategy_officer"]

    def test_campaign_type_launch(self) -> None:
        w = compute_weights(campaign_type="launch")
        w_default = compute_weights()
        assert w["chief_strategy_officer"] > w_default["chief_strategy_officer"]

    def test_campaign_type_promotional(self) -> None:
        w = compute_weights(campaign_type="promotional")
        w_default = compute_weights()
        assert w["chief_performance_officer"] > w_default["chief_performance_officer"]

    def test_combined_factors(self) -> None:
        w = compute_weights(industry="restaurant", objective="increase_sales", budget="₹5,000")
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)
        # All factors combined — should still normalize
        assert all(v > 0 for v in w.values())

    def test_unknown_industry_uses_default(self) -> None:
        w = compute_weights(industry="unknown_industry")
        assert sum(w.values()) == pytest.approx(1.0, abs=0.001)

    def test_weights_are_deterministic(self) -> None:
        w1 = compute_weights(industry="restaurant", objective="increase_sales")
        w2 = compute_weights(industry="restaurant", objective="increase_sales")
        assert w1 == w2


# ─── Disagreement calculation tests ─────────────────────────────────────────


class TestDisagreement:
    def test_no_disagreement_when_unanimous(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="c", confidence=0.8, approval=True, priority="medium"),
        ]
        d = calculate_disagreement(opinions)
        assert d < 0.2  # Low disagreement

    def test_max_disagreement_on_split(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.9, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.1, approval=False, priority="critical"),
        ]
        d = calculate_disagreement(opinions)
        assert d > 0.5  # High disagreement

    def test_empty_opinions(self) -> None:
        assert calculate_disagreement([]) == 0.0

    def test_critical_priority_increases_disagreement(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="critical"),
            DirectorOpinion(director="b", confidence=0.8, approval=True, priority="medium"),
        ]
        d = calculate_disagreement(opinions)
        assert d >= 0.1  # Critical priority contributes to disagreement

    def test_confidence_variance_increases_disagreement(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.9, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.2, approval=True, priority="medium"),
        ]
        d = calculate_disagreement(opinions)
        assert d > 0.1


# ─── Minority opinion extraction ────────────────────────────────────────────


class TestMinorityOpinions:
    def test_no_minorities_when_unanimous(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.8, approval=True, priority="medium"),
        ]
        weights = {"a": 0.5, "b": 0.5}
        minorities = extract_minority_opinions(opinions, weights)
        assert minorities == []

    def test_minority_identified_on_approval_split(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.8, approval=False, priority="medium"),
        ]
        weights = {"a": 0.5, "b": 0.5}
        minorities = extract_minority_opinions(opinions, weights)
        # The rejecting director should be in the minority
        minority_directors = [m["director"] for m in minorities]
        assert "b" in minority_directors

    def test_low_confidence_director_is_minority(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.9, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.2, approval=True, priority="medium"),
        ]
        weights = {"a": 0.5, "b": 0.5}
        minorities = extract_minority_opinions(opinions, weights)
        minority_directors = [m["director"] for m in minorities]
        assert "b" in minority_directors

    def test_critical_priority_is_minority(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.8, approval=True, priority="critical"),
        ]
        weights = {"a": 0.5, "b": 0.5}
        minorities = extract_minority_opinions(opinions, weights)
        minority_directors = [m["director"] for m in minorities]
        assert "b" in minority_directors

    def test_empty_opinions(self) -> None:
        assert extract_minority_opinions([], {}) == []


# ─── Disagreement extraction ────────────────────────────────────────────────


class TestExtractDisagreements:
    def test_split_decision_detected(self) -> None:
        opinions = [
            DirectorOpinion(director="a", approval=True, priority="medium"),
            DirectorOpinion(director="b", approval=False, priority="medium"),
        ]
        disagreements = extract_disagreements(opinions)
        assert any("Split decision" in d for d in disagreements)

    def test_critical_risks_detected(self) -> None:
        opinions = [
            DirectorOpinion(director="a", role="CSO", approval=True, priority="critical"),
        ]
        disagreements = extract_disagreements(opinions)
        assert any("Critical risks" in d for d in disagreements)

    def test_low_confidence_detected(self) -> None:
        opinions = [
            DirectorOpinion(director="a", role="CSO", confidence=0.3, approval=True, priority="medium"),
        ]
        disagreements = extract_disagreements(opinions)
        assert any("Low confidence" in d for d in disagreements)


# ─── Risk extraction ────────────────────────────────────────────────────────


class TestRiskExtraction:
    def test_risks_deduplicated(self) -> None:
        opinions = [
            DirectorOpinion(director="a", role="CSO", risks=["Budget too low", "Timing risk"]),
            DirectorOpinion(director="b", role="CCO", risks=["budget too low", "Creative risk"]),
        ]
        risks = extract_all_risks(opinions)
        # "Budget too low" and "budget too low" should be deduplicated (case-insensitive)
        budget_risks = [r for r in risks if "budget" in r.lower()]
        assert len(budget_risks) == 1

    def test_empty_risks(self) -> None:
        opinions = [DirectorOpinion(director="a", risks=[])]
        assert extract_all_risks(opinions) == []


# ─── Campaign scoring ───────────────────────────────────────────────────────


class TestCampaignScoring:
    def test_score_has_7_dimensions_plus_overall(self) -> None:
        opinions = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=True, priority="medium"),
        ]
        weights = {"chief_strategy_officer": 1.0}
        score = compute_campaign_score(opinions, weights)
        assert score.strategy_score > 0
        assert score.creative_score > 0
        assert score.media_score > 0
        assert score.brand_score > 0
        assert score.performance_score > 0
        assert score.risk_score > 0
        assert score.compliance_score > 0
        assert score.overall_score > 0

    def test_approval_boosts_score(self) -> None:
        opinions_approve = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=True, priority="medium"),
        ]
        opinions_reject = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=False, priority="medium"),
        ]
        weights = {"chief_strategy_officer": 1.0}
        score_approve = compute_campaign_score(opinions_approve, weights)
        score_reject = compute_campaign_score(opinions_reject, weights)
        assert score_approve.strategy_score > score_reject.strategy_score

    def test_critical_priority_lowers_score(self) -> None:
        opinions_normal = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=True, priority="medium"),
        ]
        opinions_critical = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=True, priority="critical"),
        ]
        weights = {"chief_strategy_officer": 1.0}
        score_normal = compute_campaign_score(opinions_normal, weights)
        score_critical = compute_campaign_score(opinions_critical, weights)
        assert score_normal.strategy_score > score_critical.strategy_score

    def test_fewer_risks_means_higher_risk_score(self) -> None:
        opinions_low_risk = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium", risks=[]),
        ]
        opinions_high_risk = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium",
                          risks=["r1", "r2", "r3", "r4", "r5"]),
        ]
        weights = {"a": 1.0}
        score_low = compute_campaign_score(opinions_low_risk, weights)
        score_high = compute_campaign_score(opinions_high_risk, weights)
        assert score_low.risk_score > score_high.risk_score

    def test_scores_between_0_and_100(self) -> None:
        opinions = [
            DirectorOpinion(director="chief_strategy_officer", confidence=1.0, approval=True, priority="medium"),
        ]
        weights = {"chief_strategy_officer": 1.0}
        score = compute_campaign_score(opinions, weights)
        for fname in ("strategy_score", "creative_score", "media_score",
                      "brand_score", "performance_score", "risk_score",
                      "compliance_score", "overall_score"):
            val = getattr(score, fname)
            assert 0.0 <= val <= 100.0, f"{fname}={val} not in [0, 100]"

    def test_score_validation(self) -> None:
        score = CampaignScore(strategy_score=50, creative_score=50, overall_score=50)
        errors = score.validate()
        assert errors == []


# ─── Consensus Engine integration tests ─────────────────────────────────────


class TestConsensusEngine:
    @pytest.mark.asyncio
    async def test_reach_consensus_all_approve(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, session = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
            industry="restaurant",
            objective="increase_sales",
        )
        assert isinstance(decision, ConsensusDecision)
        assert isinstance(session, CouncilSession)
        assert decision.approval_status == "approved"
        assert decision.confidence > 0.5
        assert session.status == "completed"
        assert session.rounds_completed >= 1

    @pytest.mark.asyncio
    async def test_reach_consensus_all_reject(self) -> None:
        gw = StubGateway(approval_mode="all_reject")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert decision.approval_status in ("rejected", "revise")
        assert decision.confidence < 0.5

    @pytest.mark.asyncio
    async def test_reach_consensus_compliance_rejects(self) -> None:
        """Compliance has veto power — if compliance rejects, campaign should not be approved."""
        gw = StubGateway(approval_mode="compliance_rejects")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        # Should not be approved because compliance rejected with critical priority
        assert decision.approval_status != "approved"

    @pytest.mark.asyncio
    async def test_consensus_includes_self_critique(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert len(decision.self_critique) > 0

    @pytest.mark.asyncio
    async def test_consensus_includes_campaign_score(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        score = decision.campaign_score
        assert "overall_score" in score
        assert "strategy_score" in score
        assert "compliance_score" in score

    @pytest.mark.asyncio
    async def test_consensus_includes_weights(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
            industry="restaurant",
        )
        assert "chief_strategy_officer" in decision.weights
        assert sum(decision.weights.values()) == pytest.approx(1.0, abs=0.001)

    @pytest.mark.asyncio
    async def test_consensus_includes_minority_opinions(self) -> None:
        gw = StubGateway(approval_mode="split")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        # Split mode → some directors reject → should have minorities
        assert isinstance(decision.minority_opinions, list)

    @pytest.mark.asyncio
    async def test_consensus_includes_disagreements(self) -> None:
        gw = StubGateway(approval_mode="split")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert isinstance(decision.disagreements, list)

    @pytest.mark.asyncio
    async def test_consensus_includes_risks(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert isinstance(decision.risks, list)

    @pytest.mark.asyncio
    async def test_consensus_has_executive_decision(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert decision.executive_decision
        assert "Council" in decision.executive_decision

    @pytest.mark.asyncio
    async def test_consensus_has_final_recommendation(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert decision.final_recommendation

    @pytest.mark.asyncio
    async def test_session_has_all_opinions(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        _, session = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        # Should have 9 opinions per round
        for round_str, opinions in session.opinions_by_round.items():
            assert len(opinions) == 9

    @pytest.mark.asyncio
    async def test_total_tokens_and_cost_tracked(self) -> None:
        gw = StubGateway(approval_mode="all_approve")
        engine = ConsensusEngine(gateway=gw)
        decision, session = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        assert decision.total_tokens > 0
        assert decision.total_cost_usd > 0
        assert session.total_tokens > 0
        assert session.total_cost_usd > 0

    @pytest.mark.asyncio
    async def test_max_rounds_respected(self) -> None:
        gw = StubGateway(approval_mode="split")  # High disagreement
        engine = ConsensusEngine(gateway=gw)
        decision, session = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
            max_rounds=2,
        )
        assert session.rounds_completed <= 2
        assert decision.rounds_completed <= 2


# ─── Tie-breaking tests ─────────────────────────────────────────────────────


class TestTieBreaking:
    @pytest.mark.asyncio
    async def test_tie_break_by_compliance_veto(self) -> None:
        """When approval is 50/50, compliance score breaks the tie."""
        gw = StubGateway(approval_mode="split")
        engine = ConsensusEngine(gateway=gw)
        decision, _ = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief=BRIEF,
        )
        # With split, compliance rejects → should not be approved
        assert decision.approval_status != "approved"

    def test_weighted_approval_not_simple_majority(self) -> None:
        """Weighted approval should differ from simple majority when weights are unequal."""
        opinions = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="chief_compliance_officer", confidence=0.5, approval=False, priority="medium"),
        ]
        # Simple majority: 50/50. Weighted: strategy has more weight.
        weights = {"chief_strategy_officer": 0.25, "chief_compliance_officer": 0.15}
        engine = ConsensusEngine()
        weighted = engine._compute_weighted_approval(opinions, weights)
        # Strategy approves with 0.25 weight, compliance rejects with 0.15
        # Weighted approval = 0.25 / (0.25 + 0.15) = 0.625
        assert weighted > 0.5  # Not a simple majority — weighted favors strategy


# ─── Determinism tests ──────────────────────────────────────────────────────


class TestDeterminism:
    def test_weights_deterministic(self) -> None:
        w1 = compute_weights(industry="restaurant", objective="increase_sales", budget="₹5L")
        w2 = compute_weights(industry="restaurant", objective="increase_sales", budget="₹5L")
        assert w1 == w2

    def test_disagreement_deterministic(self) -> None:
        opinions = [
            DirectorOpinion(director="a", confidence=0.8, approval=True, priority="medium"),
            DirectorOpinion(director="b", confidence=0.3, approval=False, priority="high"),
        ]
        d1 = calculate_disagreement(opinions)
        d2 = calculate_disagreement(opinions)
        assert d1 == d2

    def test_score_deterministic(self) -> None:
        opinions = [
            DirectorOpinion(director="chief_strategy_officer", confidence=0.8, approval=True, priority="medium"),
        ]
        weights = {"chief_strategy_officer": 1.0}
        s1 = compute_campaign_score(opinions, weights)
        s2 = compute_campaign_score(opinions, weights)
        assert s1.to_dict() == s2.to_dict()

    def test_approval_status_deterministic(self) -> None:
        engine = ConsensusEngine()
        score = CampaignScore(
            strategy_score=70, creative_score=70, media_score=70,
            brand_score=70, performance_score=70, risk_score=80,
            compliance_score=80, overall_score=75,
        )
        status1 = engine._determine_approval(0.7, score, [])
        status2 = engine._determine_approval(0.7, score, [])
        assert status1 == status2
