"""CURV AI Chat integration helpers for the Agency Council.

CURV AI never exposes raw Director discussions. CURV AI summarises *why* the Council
made the decision in conversational language.

This module provides:
- is_council_review_request(): Detects when a user is asking for a council review
- summarise_council_decision(): Converts a ConsensusDecision into a CURV AI-voiced summary
"""
from __future__ import annotations

from typing import Any

from .models import ConsensusDecision


# Keywords that indicate the user is asking for a council review
COUNCIL_REVIEW_KEYWORDS = [
    "review my campaign",
    "should i approve",
    "should we approve",
    "council review",
    "agency council",
    "review this campaign",
    "is this campaign good",
    "should i run this campaign",
    "campaign review",
    "the council",
    "directors review",
    "executive review",
]


def is_council_review_request(message: str) -> bool:
    """Detect if the user is asking for a council review.

    Returns True if the message contains any of the council review keywords.
    """
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in COUNCIL_REVIEW_KEYWORDS)


def summarise_council_decision(decision: ConsensusDecision | dict[str, Any]) -> str:
    """Convert a ConsensusDecision into a CURV AI-voiced summary.

    CURV AI never exposes raw Director discussions. This function produces a
    conversational summary that explains *why* the Council made the decision.

    Args:
        decision: A ConsensusDecision object or dict.

    Returns:
        A user-friendly summary string in CURV AI's voice.
    """
    if isinstance(decision, dict):
        approval_status = decision.get("approval_status", "pending")
        confidence = decision.get("confidence", 0.5)
        executive_decision = decision.get("executive_decision", "")
        final_recommendation = decision.get("final_recommendation", "")
        disagreements = decision.get("disagreements", [])
        risks = decision.get("risks", [])
        score = decision.get("campaign_score", {})
        overall_score = score.get("overall_score", 0.0)
        rounds = decision.get("rounds_completed", 1)
        minorities = decision.get("minority_opinions", [])
        self_critique = decision.get("self_critique", [])
    else:
        approval_status = decision.approval_status
        confidence = decision.confidence
        executive_decision = decision.executive_decision
        final_recommendation = decision.final_recommendation
        disagreements = decision.disagreements
        risks = decision.risks
        score = decision.campaign_score
        overall_score = score.get("overall_score", 0.0) if isinstance(score, dict) else 0.0
        rounds = decision.rounds_completed
        minorities = decision.minority_opinions
        self_critique = decision.self_critique

    parts: list[str] = []

    # Opening — the decision
    if approval_status == "approved":
        parts.append(
            f"Great news! The Agency Council has reviewed your campaign and given it the green light. "
            f"The council is {round(confidence * 100)}% confident in this decision, "
            f"with an overall campaign score of {overall_score}/100."
        )
    elif approval_status == "rejected":
        parts.append(
            f"I've run your campaign through the Agency Council, and unfortunately they've recommended "
            f"against it for now. The overall score came in at {overall_score}/100. "
            f"Don't worry — let me explain why and what we can do about it."
        )
    else:  # revise
        parts.append(
            f"The Agency Council has reviewed your campaign and they see potential, "
            f"but they've recommended some revisions before approval. "
            f"The overall score is {overall_score}/100 with {round(confidence * 100)}% confidence."
        )

    # Why — the reasoning (without exposing raw director discussions)
    if executive_decision:
        parts.append(f"\nHere's the council's take: {executive_decision}")

    # Key concerns (if any)
    if risks:
        top_risks = risks[:3]
        parts.append("\nKey concerns the council raised:")
        for risk in top_risks:
            parts.append(f"  • {risk}")

    # Disagreements (high-level, not raw)
    if disagreements:
        parts.append("\nThe council had some internal debates:")
        for d in disagreements[:2]:
            parts.append(f"  • {d}")

    # Self-critique (what could go wrong)
    if self_critique:
        parts.append("\nBefore deciding, the council asked itself 'what could go wrong?':")
        for critique in self_critique[:3]:
            parts.append(f"  • {critique}")

    # Minority opinions (acknowledged but not exposed in detail)
    if minorities:
        parts.append(
            f"\n{len(minorities)} director(s) had a minority opinion — "
            f"their concerns have been noted and will inform future campaigns."
        )

    # Rounds
    if rounds > 1:
        parts.append(
            f"\nThe council went through {rounds} rounds of review "
            f"to reach this decision."
        )

    # Final recommendation
    if final_recommendation:
        parts.append(f"\n{final_recommendation}")

    return "\n".join(parts)
