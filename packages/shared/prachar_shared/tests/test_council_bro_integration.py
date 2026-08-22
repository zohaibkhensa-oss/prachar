"""Tests for CURV AI chat integration with the Agency Council.

Tests:
- is_council_review_request() detection
- summarise_council_decision() produces CURV AI-voiced summaries
- CURV AI never exposes raw director discussions
"""
from __future__ import annotations

import pytest

from prachar_shared.agency_council import (
    COUNCIL_REVIEW_KEYWORDS,
    ConsensusDecision,
    is_council_review_request,
    summarise_council_decision,
)


class TestCouncilReviewDetection:
    @pytest.mark.parametrize("message", [
        "Can you review my campaign?",
        "Should I approve this campaign?",
        "Should we approve the campaign?",
        "I want a council review",
        "Can the agency council review this?",
        "Please review this campaign",
        "Is this campaign good enough?",
        "Should I run this campaign?",
        "I need a campaign review",
        "What does the council think?",
        "Can the directors review my campaign?",
        "I want an executive review",
    ])
    def test_detects_council_review_requests(self, message: str) -> None:
        assert is_council_review_request(message) is True

    @pytest.mark.parametrize("message", [
        "What's my visibility score?",
        "Generate content for Instagram",
        "How do I connect my Google account?",
        "Show me my campaigns",
        "What's my budget?",
        "Hello",
        "Help me with analytics",
    ])
    def test_does_not_trigger_on_non_review_requests(self, message: str) -> None:
        assert is_council_review_request(message) is False

    def test_case_insensitive(self) -> None:
        assert is_council_review_request("REVIEW MY CAMPAIGN") is True
        assert is_council_review_request("Should I APPROVE This Campaign?") is True

    def test_keywords_list_not_empty(self) -> None:
        assert len(COUNCIL_REVIEW_KEYWORDS) > 0


class TestCouncilDecisionSummary:
    def test_approved_summary(self) -> None:
        decision = ConsensusDecision(
            executive_decision="The Council approves this campaign.",
            confidence=0.85,
            approval_status="approved",
            final_recommendation="Proceed with the campaign.",
            campaign_score={"overall_score": 78.0},
            rounds_completed=1,
            total_tokens=900,
        )
        summary = summarise_council_decision(decision)
        assert "green light" in summary.lower() or "approved" in summary.lower()
        assert "78" in summary
        assert "85" in summary  # confidence percentage
        assert "Proceed" in summary

    def test_rejected_summary(self) -> None:
        decision = ConsensusDecision(
            executive_decision="The Council rejects this campaign.",
            confidence=0.3,
            approval_status="rejected",
            final_recommendation="Do not proceed.",
            risks=["Budget too low", "Compliance risk"],
            campaign_score={"overall_score": 35.0},
            rounds_completed=1,
        )
        summary = summarise_council_decision(decision)
        assert "against it" in summary.lower() or "rejected" in summary.lower()
        assert "35" in summary
        assert "Budget too low" in summary

    def test_revise_summary(self) -> None:
        decision = ConsensusDecision(
            executive_decision="The Council recommends revisions.",
            confidence=0.6,
            approval_status="revise",
            final_recommendation="Revise and resubmit.",
            campaign_score={"overall_score": 55.0},
            rounds_completed=1,
        )
        summary = summarise_council_decision(decision)
        assert "potential" in summary.lower() or "revisions" in summary.lower()
        assert "55" in summary

    def test_summary_includes_risks(self) -> None:
        decision = ConsensusDecision(
            approval_status="revise",
            confidence=0.6,
            risks=["Risk A", "Risk B", "Risk C", "Risk D"],
            campaign_score={"overall_score": 50.0},
        )
        summary = summarise_council_decision(decision)
        assert "Risk A" in summary
        assert "Risk B" in summary
        assert "Risk C" in summary
        # Only top 3 risks
        assert "Risk D" not in summary

    def test_summary_includes_disagreements(self) -> None:
        decision = ConsensusDecision(
            approval_status="revise",
            confidence=0.6,
            disagreements=["Split decision: 5 approve, 4 reject"],
            campaign_score={"overall_score": 50.0},
        )
        summary = summarise_council_decision(decision)
        assert "Split decision" in summary

    def test_summary_includes_self_critique(self) -> None:
        decision = ConsensusDecision(
            approval_status="approved",
            confidence=0.8,
            self_critique=["Campaign may be too generic", "Competitors could undercut"],
            campaign_score={"overall_score": 75.0},
        )
        summary = summarise_council_decision(decision)
        assert "what could go wrong" in summary.lower()
        assert "too generic" in summary

    def test_summary_includes_minority_count(self) -> None:
        decision = ConsensusDecision(
            approval_status="approved",
            confidence=0.8,
            minority_opinions=[{"director": "cfo"}, {"director": "compliance"}],
            campaign_score={"overall_score": 75.0},
        )
        summary = summarise_council_decision(decision)
        assert "2" in summary
        assert "minority" in summary.lower()

    def test_summary_includes_rounds_if_multiple(self) -> None:
        decision = ConsensusDecision(
            approval_status="approved",
            confidence=0.8,
            rounds_completed=3,
            campaign_score={"overall_score": 75.0},
        )
        summary = summarise_council_decision(decision)
        assert "3 rounds" in summary

    def test_summary_does_not_include_raw_director_discussions(self) -> None:
        """CURV AI must never expose raw director discussions."""
        decision = ConsensusDecision(
            approval_status="approved",
            confidence=0.8,
            executive_decision="Council approves",
            minority_opinions=[
                {"director": "chief_financial_officer", "role": "CFO",
                 "opinion": "I think the budget is too high",
                 "reasoning": "Based on my analysis of the ROI projections..."}
            ],
            campaign_score={"overall_score": 75.0},
        )
        summary = summarise_council_decision(decision)
        # Should NOT include the CFO's raw opinion or reasoning
        assert "I think the budget is too high" not in summary
        assert "Based on my analysis" not in summary
        # Should mention that there was a minority opinion (count only)
        assert "minority" in summary.lower()

    def test_summary_accepts_dict_input(self) -> None:
        decision_dict = {
            "approval_status": "approved",
            "confidence": 0.85,
            "executive_decision": "Council approves",
            "final_recommendation": "Proceed",
            "campaign_score": {"overall_score": 80.0},
            "rounds_completed": 1,
        }
        summary = summarise_council_decision(decision_dict)
        assert "80" in summary
        assert "Proceed" in summary

    def test_summary_handles_empty_decision(self) -> None:
        decision = ConsensusDecision()
        summary = summarise_council_decision(decision)
        # Should not crash, should produce some text
        assert len(summary) > 0
