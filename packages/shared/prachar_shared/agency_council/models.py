"""Domain models for the Agency Council.

Every model inherits from DomainModel (from the marketing_intelligence package)
for consistent serialization, validation, and versioning.

Models:
- DirectorOpinion: A single director's review of a campaign
- ConsensusDecision: The council's final decision after weighted consensus
- CampaignScore: Multi-dimensional campaign scoring (7 dimensions + overall)
- CouncilSession: A complete council review session (multiple rounds)
- CouncilLearning: Persistent learnings from council decisions

Architecture rules:
- Domain models never import infrastructure (no SQLAlchemy, no FastAPI)
- Domain models never import directors or the consensus engine
- All models are dataclasses with defaults for every field
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from prachar_shared.marketing_intelligence.domain_base import DomainModel


# ─── Director Opinion ───────────────────────────────────────────────────────


@dataclass
class DirectorOpinion(DomainModel):
    """A single director's opinion on a campaign.

    Every director returns exactly this contract — 9 fields.
    No director may return a partial opinion.
    """

    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    director: str = ""  # e.g., "chief_strategy_officer"
    role: str = ""  # Human-readable: "Chief Strategy Officer"
    opinion: str = ""  # The director's main opinion (1-3 sentences)
    reasoning: str = ""  # Detailed reasoning behind the opinion
    confidence: float = 0.5  # 0.0-1.0
    risks: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # Internal evidence cited
    priority: str = "medium"  # low, medium, high, critical
    approval: bool = False  # Does this director approve the campaign?
    # Phase I3 — deeper reasoning fields
    evidence_cited: list[str] = field(default_factory=list)  # Quoted brief sections
    alternatives_considered: list[str] = field(default_factory=list)  # ≥2 alternatives
    # Metadata
    latency_ms: float = 0.0
    tokens_used: int = 0
    cost_usd: float = 0.0
    model: str = ""
    provider: str = ""
    round_number: int = 1  # Which review round (1, 2, or 3)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.director:
            errors.append("director is required")
        if not self.opinion:
            errors.append("opinion is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0.0 and 1.0")
        if self.priority not in ("low", "medium", "high", "critical"):
            errors.append("priority must be low, medium, high, or critical")
        if self.round_number < 1 or self.round_number > 3:
            errors.append("round_number must be between 1 and 3")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, including Phase I3 reasoning fields."""
        result = super().to_dict()
        # evidence_cited and alternatives_considered are already lists
        return result


# ─── Campaign Score ─────────────────────────────────────────────────────────


@dataclass
class CampaignScore(DomainModel):
    """Multi-dimensional campaign scoring.

    7 dimension scores + 1 overall score. Each is 0.0-100.0.
    The overall score is NOT a simple average — it's weighted by the
    same weights used in the consensus engine.
    """

    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    strategy_score: float = 0.0
    creative_score: float = 0.0
    media_score: float = 0.0
    brand_score: float = 0.0
    performance_score: float = 0.0
    risk_score: float = 0.0  # Lower risk = higher score
    compliance_score: float = 0.0
    overall_score: float = 0.0
    # The weights used to compute overall (for transparency)
    weights_used: dict[str, float] = field(default_factory=dict)

    def validate(self) -> list[str]:
        errors: list[str] = []
        for fname in ("strategy_score", "creative_score", "media_score",
                      "brand_score", "performance_score", "risk_score",
                      "compliance_score", "overall_score"):
            val = getattr(self, fname)
            if not 0.0 <= val <= 100.0:
                errors.append(f"{fname} must be between 0.0 and 100.0")
        return errors


# ─── Consensus Decision ─────────────────────────────────────────────────────


@dataclass
class ConsensusDecision(DomainModel):
    """The council's final decision after weighted consensus.

    This is the output of the Consensus Engine. It aggregates all director
    opinions into a single executive decision.
    """

    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    executive_decision: str = ""  # The final decision (1-3 sentences)
    confidence: float = 0.5  # 0.0-1.0
    approval_status: str = "pending"  # pending, approved, rejected, revise
    final_recommendation: str = ""  # What should be done next
    disagreements: list[str] = field(default_factory=list)
    minority_opinions: list[dict[str, Any]] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    # Weighted consensus details
    weights: dict[str, float] = field(default_factory=dict)
    weighted_scores: dict[str, float] = field(default_factory=dict)
    # Self-critique results
    self_critique: list[str] = field(default_factory=list)
    # Round info
    rounds_completed: int = 1
    # Score
    campaign_score: dict[str, Any] = field(default_factory=dict)
    # Phase I3 — deeper consensus intelligence fields
    agreement_score: float = 0.0  # 0.0-1.0 alignment among directors
    disagreement_analysis: list[dict[str, Any]] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    suggested_revisions: list[dict[str, Any]] = field(default_factory=list)
    confidence_interval: tuple[float, float] = (0.0, 1.0)  # (low, high)
    # Metadata
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.approval_status not in ("pending", "approved", "rejected", "revise"):
            errors.append("approval_status must be pending, approved, rejected, or revise")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0.0 and 1.0")
        if self.rounds_completed < 1 or self.rounds_completed > 3:
            errors.append("rounds_completed must be between 1 and 3")
        if not 0.0 <= self.agreement_score <= 1.0:
            errors.append("agreement_score must be between 0.0 and 1.0")
        low, high = self.confidence_interval
        if not (0.0 <= low <= 1.0 and 0.0 <= high <= 1.0 and low <= high):
            errors.append("confidence_interval must be (low, high) with 0<=low<=high<=1.0")
        return errors

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict, including Phase I3 consensus intelligence fields.

        The confidence_interval tuple is converted to a list for JSON safety.
        """
        result = super().to_dict()
        # Convert tuple → list for JSON-safe serialization
        result["confidence_interval"] = list(self.confidence_interval)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ConsensusDecision":
        """Deserialize from dict, converting confidence_interval list → tuple."""
        if data is None:
            data = {}
        if not isinstance(data, dict):
            data = {}
        ci = data.get("confidence_interval")
        if isinstance(ci, (list, tuple)) and len(ci) == 2:
            data = {**data, "confidence_interval": (float(ci[0]), float(ci[1]))}
        return super().from_dict(data)  # type: ignore[return-value]


# ─── Council Session ────────────────────────────────────────────────────────


@dataclass
class CouncilSession(DomainModel):
    """A complete council review session.

    A session may include multiple rounds of review if disagreement is high.
    Each round produces a set of director opinions. The final round produces
    the consensus decision.
    """

    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    session_id: str = ""  # UUID as string
    tenant_id: str = ""
    brand_id: str = ""
    campaign_id: str = ""  # The campaign being reviewed
    campaign_brief: dict[str, Any] = field(default_factory=dict)
    # All opinions from all rounds
    opinions_by_round: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # Final decision
    consensus_decision: dict[str, Any] = field(default_factory=dict)
    # Status
    status: str = "pending"  # pending, in_review, completed, failed
    rounds_completed: int = 0
    # Metadata
    created_at: str = ""
    completed_at: str = ""
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.status not in ("pending", "in_review", "completed", "failed"):
            errors.append("invalid status")
        return errors


# ─── Council Learning ───────────────────────────────────────────────────────


@dataclass
class CouncilLearning(DomainModel):
    """Persistent learnings from council decisions.

    Stored in the council_memories table. Used by the Analytics Director
    and the Learning Engine to improve future decisions.
    """

    SCHEMA_VERSION: ClassVar[str] = "1.0.0"

    session_id: str = ""
    campaign_id: str = ""
    decision: str = ""  # approved, rejected, revise
    outcome: str = ""  # success, failure, pending
    minority_opinions: list[str] = field(default_factory=list)
    rejected_ideas: list[str] = field(default_factory=list)
    successful_recommendations: list[str] = field(default_factory=list)
    failed_recommendations: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    # Score at decision time
    overall_score: float = 0.0
    # Metadata
    created_at: str = ""

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.decision not in ("approved", "rejected", "revise", ""):
            errors.append("decision must be approved, rejected, or revise")
        if self.outcome not in ("success", "failure", "pending", ""):
            errors.append("outcome must be success, failure, or pending")
        return errors
