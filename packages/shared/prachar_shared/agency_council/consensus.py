"""Consensus Engine for the Agency Council.

The Consensus Engine gathers every Director's opinion and produces a
single ConsensusDecision. It does NOT use majority voting. Instead, it
uses WEIGHTED CONSENSUS where weights depend on:
- campaign objective
- industry
- budget
- campaign type

If disagreement is high, the engine runs another review round (max 3).
Before final approval, the engine runs a SELF-CRITIQUE step.

Output:
- Executive Decision
- Confidence
- Disagreements
- Minority Opinions
- Risks
- Final Recommendation
- Approval Status
- Campaign Score (7 dimensions + overall)

The engine is deterministic where possible:
- Weight calculation is deterministic (based on objective/industry/budget)
- Score calculation is deterministic (weighted sum of director confidences)
- Self-critique uses the AI gateway (non-deterministic but bounded)
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from prachar_shared.ai_gateway import AIGateway, Completion, Tier

from .director_base import Director
from .directors import ALL_DIRECTORS, DIRECTOR_NAMES
from .models import CampaignScore, ConsensusDecision, CouncilSession, DirectorOpinion

logger = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── Weight Profiles ────────────────────────────────────────────────────────


# Default weights (sum to 1.0). Used when no specific profile matches.
DEFAULT_WEIGHTS: dict[str, float] = {
    "chief_strategy_officer": 0.15,
    "chief_creative_officer": 0.15,
    "chief_media_officer": 0.10,
    "chief_performance_officer": 0.10,
    "chief_brand_officer": 0.10,
    "chief_financial_officer": 0.10,
    "chief_compliance_officer": 0.15,
    "chief_customer_officer": 0.10,
    "chief_analytics_officer": 0.05,
}

# Industry-specific weight profiles
INDUSTRY_WEIGHTS: dict[str, dict[str, float]] = {
    "restaurant": {
        "chief_strategy_officer": 0.25,
        "chief_creative_officer": 0.20,
        "chief_media_officer": 0.15,
        "chief_performance_officer": 0.10,
        "chief_brand_officer": 0.05,
        "chief_financial_officer": 0.05,
        "chief_compliance_officer": 0.05,
        "chief_customer_officer": 0.10,
        "chief_analytics_officer": 0.05,
    },
    "ecommerce": {
        "chief_strategy_officer": 0.15,
        "chief_creative_officer": 0.15,
        "chief_media_officer": 0.15,
        "chief_performance_officer": 0.20,
        "chief_brand_officer": 0.05,
        "chief_financial_officer": 0.10,
        "chief_compliance_officer": 0.05,
        "chief_customer_officer": 0.10,
        "chief_analytics_officer": 0.05,
    },
    "healthcare": {
        "chief_strategy_officer": 0.15,
        "chief_creative_officer": 0.10,
        "chief_media_officer": 0.10,
        "chief_performance_officer": 0.05,
        "chief_brand_officer": 0.10,
        "chief_financial_officer": 0.05,
        "chief_compliance_officer": 0.25,
        "chief_customer_officer": 0.15,
        "chief_analytics_officer": 0.05,
    },
    "finance": {
        "chief_strategy_officer": 0.15,
        "chief_creative_officer": 0.10,
        "chief_media_officer": 0.10,
        "chief_performance_officer": 0.10,
        "chief_brand_officer": 0.10,
        "chief_financial_officer": 0.15,
        "chief_compliance_officer": 0.20,
        "chief_customer_officer": 0.05,
        "chief_analytics_officer": 0.05,
    },
    "technology": {
        "chief_strategy_officer": 0.20,
        "chief_creative_officer": 0.15,
        "chief_media_officer": 0.10,
        "chief_performance_officer": 0.15,
        "chief_brand_officer": 0.10,
        "chief_financial_officer": 0.10,
        "chief_compliance_officer": 0.05,
        "chief_customer_officer": 0.10,
        "chief_analytics_officer": 0.05,
    },
}

# Objective-specific weight adjustments
OBJECTIVE_WEIGHT_ADJUSTMENTS: dict[str, dict[str, float]] = {
    "increase_sales": {
        "chief_performance_officer": 1.3,
        "chief_financial_officer": 1.2,
    },
    "brand_awareness": {
        "chief_creative_officer": 1.3,
        "chief_brand_officer": 1.2,
        "chief_media_officer": 1.2,
    },
    "lead_generation": {
        "chief_performance_officer": 1.2,
        "chief_media_officer": 1.2,
        "chief_customer_officer": 1.1,
    },
    "customer_retention": {
        "chief_customer_officer": 1.3,
        "chief_brand_officer": 1.2,
        "chief_analytics_officer": 1.2,
    },
    "product_launch": {
        "chief_strategy_officer": 1.3,
        "chief_creative_officer": 1.2,
        "chief_media_officer": 1.1,
    },
}


def compute_weights(
    *,
    industry: str = "",
    objective: str = "",
    budget: str = "",
    campaign_type: str = "",
) -> dict[str, float]:
    """Compute director weights for a campaign.

    Deterministic. Weights always sum to 1.0.

    Args:
        industry: e.g., "restaurant", "ecommerce", "healthcare"
        objective: e.g., "increase_sales", "brand_awareness"
        budget: budget string (affects finance weight if very low/high)
        campaign_type: e.g., "launch", "always-on", "promotional"

    Returns:
        Dict mapping director name to weight (0.0-1.0, sum to 1.0).
    """
    # Start with industry profile or default
    industry_lower = industry.lower()
    weights = dict(INDUSTRY_WEIGHTS.get(industry_lower, DEFAULT_WEIGHTS))

    # Apply objective adjustments
    objective_lower = objective.lower()
    adjustments = OBJECTIVE_WEIGHT_ADJUSTMENTS.get(objective_lower, {})
    for director, multiplier in adjustments.items():
        if director in weights:
            weights[director] *= multiplier

    # Budget-based adjustment: very low budgets increase CFO weight
    budget_lower = (budget or "").lower()
    if any(x in budget_lower for x in ["₹5,000", "₹10,000", "$100", "$500", "low", "small"]):
        weights["chief_financial_officer"] = weights.get("chief_financial_officer", 0.1) * 1.3
    elif any(x in budget_lower for x in ["₹10,00,000", "₹50,00,000", "$50,000", "$100,000", "high", "large"]):
        weights["chief_financial_officer"] = weights.get("chief_financial_officer", 0.1) * 0.8
        weights["chief_strategy_officer"] = weights.get("chief_strategy_officer", 0.15) * 1.2

    # Campaign type adjustments
    ct_lower = (campaign_type or "").lower()
    if "launch" in ct_lower:
        weights["chief_strategy_officer"] = weights.get("chief_strategy_officer", 0.15) * 1.2
        weights["chief_creative_officer"] = weights.get("chief_creative_officer", 0.15) * 1.2
    elif "promotional" in ct_lower or "sale" in ct_lower:
        weights["chief_performance_officer"] = weights.get("chief_performance_officer", 0.10) * 1.3
        weights["chief_financial_officer"] = weights.get("chief_financial_officer", 0.10) * 1.2

    # Normalize to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}
    return weights


# ─── Disagreement Calculation ───────────────────────────────────────────────


def calculate_disagreement(opinions: list[DirectorOpinion]) -> float:
    """Calculate the disagreement level among directors.

    Returns a float 0.0-1.0 where:
    - 0.0 = full consensus (all agree)
    - 1.0 = maximum disagreement

    Based on:
    1. Approval split (how many approve vs reject)
    2. Confidence variance (wide variance = more disagreement)
    3. Priority conflicts (critical risks from multiple directors)
    """
    if not opinions:
        return 0.0

    # 1. Approval split
    approvals = sum(1 for o in opinions if o.approval)
    approval_rate = approvals / len(opinions)
    approval_disagreement = 1.0 - abs(approval_rate - 0.5) * 2  # 0 if 50/50, 1 if unanimous

    # 2. Confidence variance
    confidences = [o.confidence for o in opinions]
    if len(confidences) > 1:
        mean_conf = sum(confidences) / len(confidences)
        variance = sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)
        # Normalize: variance of 0.25 (max for 0-1 range) = 1.0 disagreement
        confidence_disagreement = min(variance / 0.25, 1.0)
    else:
        confidence_disagreement = 0.0

    # 3. Priority conflicts (directors marking critical priority)
    critical_count = sum(1 for o in opinions if o.priority == "critical")
    priority_disagreement = min(critical_count / len(opinions), 1.0)

    # Weighted combination
    disagreement = (
        approval_disagreement * 0.5
        + confidence_disagreement * 0.3
        + priority_disagreement * 0.2
    )
    return round(disagreement, 4)


def extract_minority_opinions(
    opinions: list[DirectorOpinion], weights: dict[str, float]
) -> list[dict[str, Any]]:
    """Identify minority opinions — directors who disagree with the majority.

    A director is in the minority if:
    - Their approval differs from the weighted majority, OR
    - Their confidence is significantly below the weighted average, OR
    - They flagged critical priority
    """
    if not opinions:
        return []

    # Weighted approval
    total_weight = sum(weights.get(o.director, 0) for o in opinions)
    if total_weight == 0:
        weighted_approval = sum(1 for o in opinions if o.approval) / len(opinions)
    else:
        weighted_approval = (
            sum(weights.get(o.director, 0) for o in opinions if o.approval) / total_weight
        )
    majority_approves = weighted_approval >= 0.5

    # Weighted average confidence
    if total_weight > 0:
        weighted_conf = (
            sum(weights.get(o.director, 0) * o.confidence for o in opinions) / total_weight
        )
    else:
        weighted_conf = sum(o.confidence for o in opinions) / len(opinions)

    minorities: list[dict[str, Any]] = []
    for op in opinions:
        is_minority = False
        reasons: list[str] = []

        if op.approval != majority_approves:
            is_minority = True
            reasons.append("differs from majority on approval")

        if op.confidence < weighted_conf - 0.2:
            is_minority = True
            reasons.append("significantly lower confidence")

        if op.priority == "critical":
            is_minority = True
            reasons.append("flagged critical priority")

        if is_minority:
            minorities.append({
                "director": op.director,
                "role": op.role,
                "opinion": op.opinion,
                "reasoning": op.reasoning,
                "confidence": op.confidence,
                "approval": op.approval,
                "priority": op.priority,
                "reasons": reasons,
            })
    return minorities


def extract_disagreements(opinions: list[DirectorOpinion]) -> list[str]:
    """Extract specific disagreement points between directors."""
    disagreements: list[str] = []
    # Check for conflicting approvals
    approvals = [o for o in opinions if o.approval]
    rejections = [o for o in opinions if not o.approval]
    if approvals and rejections:
        disagreements.append(
            f"Split decision: {len(approvals)} directors approve, "
            f"{len(rejections)} reject"
        )
    # Check for conflicting risk assessments
    critical_risks = [o for o in opinions if o.priority == "critical"]
    if critical_risks:
        directors = ", ".join(o.role for o in critical_risks)
        disagreements.append(f"Critical risks raised by: {directors}")
    # Check for low confidence directors
    low_conf = [o for o in opinions if o.confidence < 0.4]
    if low_conf:
        directors = ", ".join(o.role for o in low_conf)
        disagreements.append(f"Low confidence from: {directors}")
    return disagreements


def extract_all_risks(opinions: list[DirectorOpinion]) -> list[str]:
    """Aggregate all risks from all directors, deduplicated."""
    seen: set[str] = set()
    risks: list[str] = []
    for op in opinions:
        for risk in op.risks:
            key = risk.lower().strip()
            if key and key not in seen:
                seen.add(key)
                risks.append(f"[{op.role}] {risk}")
    return risks


# ─── Phase I3: Deeper Consensus Intelligence ─────────────────────────────────


# Priority ranking for sorting (higher = more urgent)
_PRIORITY_RANK: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def compute_agreement_score(opinions: list[DirectorOpinion]) -> float:
    """Compute how aligned the directors are (0.0-1.0).

    1.0 = perfect consensus, 0.0 = maximum disagreement.
    This is the complement of calculate_disagreement().
    """
    if not opinions:
        return 1.0
    disagreement = calculate_disagreement(opinions)
    return round(max(0.0, min(1.0, 1.0 - disagreement)), 4)


def analyze_disagreements(
    opinions: list[DirectorOpinion], weights: dict[str, float]
) -> list[dict[str, Any]]:
    """Identify which directors disagree and WHY (not just that they disagree).

    Returns a list of disagreement clusters, each containing:
    - issue: a description of the disagreement axis
    - directors: list of {director, role, position, confidence, reasoning}
    - severity: how significant this disagreement is (0.0-1.0)
    """
    if not opinions:
        return []

    analyses: list[dict[str, Any]] = []

    # 1. Approval split analysis
    approvers = [o for o in opinions if o.approval]
    rejecters = [o for o in opinions if not o.approval]
    if approvers and rejecters:
        analyses.append({
            "issue": "Approval split — directors disagree on whether to approve",
            "directors": [
                {
                    "director": o.director,
                    "role": o.role,
                    "position": "approve",
                    "confidence": o.confidence,
                    "reasoning": o.reasoning[:200] if o.reasoning else "",
                }
                for o in approvers
            ] + [
                {
                    "director": o.director,
                    "role": o.role,
                    "position": "reject",
                    "confidence": o.confidence,
                    "reasoning": o.reasoning[:200] if o.reasoning else "",
                }
                for o in rejecters
            ],
            "severity": round(abs(len(approvers) - len(rejecters)) / len(opinions), 4),
        })

    # 2. Confidence divergence analysis
    if len(opinions) > 1:
        confidences = [o.confidence for o in opinions]
        mean_conf = sum(confidences) / len(confidences)
        divergent = [
            o for o in opinions
            if abs(o.confidence - mean_conf) > 0.25
        ]
        if divergent:
            analyses.append({
                "issue": (
                    "Confidence divergence — some directors are significantly "
                    f"more/less confident than the council average ({mean_conf:.2f})"
                ),
                "directors": [
                    {
                        "director": o.director,
                        "role": o.role,
                        "position": "above average" if o.confidence > mean_conf else "below average",
                        "confidence": o.confidence,
                        "reasoning": o.reasoning[:200] if o.reasoning else "",
                    }
                    for o in sorted(divergent, key=lambda x: abs(x.confidence - mean_conf), reverse=True)
                ],
                "severity": round(
                    max(abs(o.confidence - mean_conf) for o in divergent), 4
                ),
            })

    # 3. Priority conflict analysis
    critical_or_high = [o for o in opinions if o.priority in ("critical", "high")]
    if critical_or_high:
        analyses.append({
            "issue": (
                "Priority conflict — some directors flagged high/critical risks "
                "while others did not"
            ),
            "directors": [
                {
                    "director": o.director,
                    "role": o.role,
                    "position": f"priority={o.priority}",
                    "confidence": o.confidence,
                    "reasoning": o.reasoning[:200] if o.reasoning else "",
                }
                for o in critical_or_high
            ],
            "severity": round(len(critical_or_high) / len(opinions), 4),
        })

    return analyses


def prioritize_risks(opinions: list[DirectorOpinion]) -> list[str]:
    """Aggregate all risks into a prioritised risk register.

    Risks are sorted by the priority of the director who raised them
    (critical > high > medium > low), then by frequency (risks raised
    by multiple directors rank higher). Format is preserved as
    '[Role] risk' strings for backward compatibility.
    """
    # Collect (risk_text, director_role, director_priority) tuples
    raw: list[tuple[str, str, str]] = []
    for op in opinions:
        for risk in op.risks:
            if risk.strip():
                raw.append((risk.strip(), op.role, op.priority))

    if not raw:
        return []

    # Deduplicate case-insensitively, keeping the highest-priority director's role
    seen: dict[str, tuple[str, str, str]] = {}
    for risk_text, role, priority in raw:
        key = risk_text.lower()
        existing = seen.get(key)
        if existing is None or _PRIORITY_RANK.get(priority, 0) > _PRIORITY_RANK.get(existing[2], 0):
            seen[key] = (risk_text, role, priority)

    # Sort by priority rank (descending), then alphabetically
    sorted_risks = sorted(
        seen.values(),
        key=lambda x: (-_PRIORITY_RANK.get(x[2], 0), x[0].lower()),
    )
    return [f"[{role}] {risk_text}" for risk_text, role, _ in sorted_risks]


def identify_missing_information(
    opinions: list[DirectorOpinion], campaign_brief: dict[str, Any]
) -> list[str]:
    """Identify what the council needs but doesn't have.

    Detects:
    - Directors with very low confidence (likely missing data)
    - Directors who mention 'unknown', 'unclear', 'missing', 'not available'
    - Key brief sections that are absent
    """
    missing: list[str] = []

    # 1. Low-confidence directors likely lack information
    for op in opinions:
        if op.confidence < 0.4:
            missing.append(
                f"{op.role} has low confidence ({op.confidence:.2f}) — "
                f"likely missing key information for their assessment"
            )

    # 2. Scan reasoning for explicit mentions of missing data
    missing_keywords = ("unknown", "unclear", "missing", "not available",
                        "not provided", "insufficient", "lack of", "no data",
                        "no historical", "not specified")
    for op in opinions:
        text = (op.reasoning + " " + op.opinion).lower()
        for kw in missing_keywords:
            if kw in text:
                missing.append(
                    f"{op.role} indicates '{kw}' — information gap detected"
                )
                break  # One mention per director

    # 3. Key brief sections that are absent
    expected_keys = {"business_name", "industry", "goal", "budget", "objective",
                     "campaign_strategy", "media_plan"}
    absent = expected_keys - set(campaign_brief.keys())
    if absent:
        missing.append(
            f"Campaign brief is missing sections: {', '.join(sorted(absent))}"
        )

    return missing


def generate_suggested_revisions(
    opinions: list[DirectorOpinion],
) -> list[dict[str, Any]]:
    """Generate specific, actionable revision suggestions from director feedback.

    Returns a list of dicts:
    - revision: the actionable change
    - director: which director suggested it
    - priority: the priority level
    - rationale: why this revision matters
    """
    revisions: list[dict[str, Any]] = []
    for op in opinions:
        for rec in op.recommendations:
            if rec.strip():
                revisions.append({
                    "revision": rec.strip(),
                    "director": op.director,
                    "role": op.role,
                    "priority": op.priority,
                    "rationale": op.reasoning[:200] if op.reasoning else "",
                })
        # Directors who rejected should have their risks turned into revisions
        if not op.approval and op.risks:
            for risk in op.risks[:2]:  # Top 2 risks
                revisions.append({
                    "revision": f"Address risk raised by {op.role}: {risk}",
                    "director": op.director,
                    "role": op.role,
                    "priority": op.priority,
                    "rationale": op.reasoning[:200] if op.reasoning else "",
                })

    # Sort by priority (critical first)
    revisions.sort(key=lambda r: -_PRIORITY_RANK.get(r["priority"], 0))
    return revisions


def compute_confidence_interval(
    opinions: list[DirectorOpinion], weights: dict[str, float]
) -> tuple[float, float]:
    """Compute a confidence interval (low, high) for the consensus.

    The interval reflects the spread of director confidences:
    - low = weighted confidence minus 1 standard deviation (clamped to 0)
    - high = weighted confidence plus 1 standard deviation (clamped to 1)

    This gives a range (e.g., 0.72-0.85) rather than a single point estimate.
    """
    if not opinions:
        return (0.0, 1.0)

    total_weight = sum(weights.get(o.director, 0) for o in opinions)
    if total_weight > 0:
        weighted_conf = (
            sum(weights.get(o.director, 0) * o.confidence for o in opinions)
            / total_weight
        )
    else:
        weighted_conf = sum(o.confidence for o in opinions) / len(opinions)

    if len(opinions) > 1:
        confidences = [o.confidence for o in opinions]
        mean = sum(confidences) / len(confidences)
        variance = sum((c - mean) ** 2 for c in confidences) / len(confidences)
        std_dev = variance ** 0.5
    else:
        std_dev = 0.0

    low = max(0.0, weighted_conf - std_dev)
    high = min(1.0, weighted_conf + std_dev)
    # Ensure low <= high (degenerate case when std_dev is 0)
    if low > high:
        low, high = high, low
    return (round(low, 4), round(high, 4))


# ─── Campaign Scoring ───────────────────────────────────────────────────────


def compute_campaign_score(
    opinions: list[DirectorOpinion],
    weights: dict[str, float],
) -> CampaignScore:
    """Compute the multi-dimensional campaign score.

    Maps each director's confidence + approval to a 0-100 score for their
    dimension. The overall score is the weighted average.

    Dimension mapping:
    - strategy_score ← ChiefStrategyOfficer
    - creative_score ← ChiefCreativeOfficer
    - media_score ← ChiefMediaOfficer
    - brand_score ← ChiefBrandOfficer
    - performance_score ← ChiefPerformanceOfficer
    - risk_score ← aggregate (inverted: low risks = high score)
    - compliance_score ← ChiefComplianceOfficer
    """
    # Map director to score
    director_scores: dict[str, float] = {}
    for op in opinions:
        # Score = confidence * 100, adjusted by approval
        base = op.confidence * 100
        if not op.approval:
            base *= 0.5  # Disapproval halves the score
        # Priority penalty
        if op.priority == "critical":
            base *= 0.6
        elif op.priority == "high":
            base *= 0.8
        director_scores[op.director] = round(base, 2)

    # Risk score: fewer risks = higher score
    total_risks = sum(len(op.risks) for op in opinions)
    critical_count = sum(1 for op in opinions if op.priority == "critical")
    # 0 risks = 100, 20+ risks = 0
    risk_score = max(0.0, 100.0 - (total_risks * 5) - (critical_count * 10))

    score = CampaignScore(
        strategy_score=director_scores.get("chief_strategy_officer", 50.0),
        creative_score=director_scores.get("chief_creative_officer", 50.0),
        media_score=director_scores.get("chief_media_officer", 50.0),
        brand_score=director_scores.get("chief_brand_officer", 50.0),
        performance_score=director_scores.get("chief_performance_officer", 50.0),
        risk_score=round(risk_score, 2),
        compliance_score=director_scores.get("chief_compliance_officer", 50.0),
        weights_used=weights,
    )

    # Overall = weighted average of all 7 dimensions
    dim_weights = {
        "strategy_score": weights.get("chief_strategy_officer", 0.15),
        "creative_score": weights.get("chief_creative_officer", 0.15),
        "media_score": weights.get("chief_media_officer", 0.10),
        "brand_score": weights.get("chief_brand_officer", 0.10),
        "performance_score": weights.get("chief_performance_officer", 0.10),
        "risk_score": 0.15,  # Risk is always important
        "compliance_score": weights.get("chief_compliance_officer", 0.15),
    }
    total_w = sum(dim_weights.values())
    overall = sum(
        getattr(score, dim) * dim_weights[dim]
        for dim in dim_weights
    ) / total_w
    score.overall_score = round(overall, 2)
    return score


# ─── Consensus Engine ───────────────────────────────────────────────────────


# Threshold for triggering another round
DISAGREEMENT_THRESHOLD = 0.45  # If disagreement > this, run another round
MAX_ROUNDS = 3
# Threshold for approval
APPROVAL_CONFIDENCE_THRESHOLD = 0.55
APPROVAL_SCORE_THRESHOLD = 60.0


class ConsensusEngine:
    """The Consensus Engine gathers director opinions and produces a decision.

    Usage:
        engine = ConsensusEngine(gateway=gw)
        decision = await engine.reach_consensus(
            tenant_id=uuid.uuid4(),
            campaign_brief={...},
            directors=[ChiefStrategyOfficer(), ...],
            industry="restaurant",
            objective="increase_sales",
        )
    """

    def __init__(
        self,
        gateway: AIGateway | None = None,
        directors: list[Director] | None = None,
    ) -> None:
        self._gateway = gateway
        self._directors = directors

    @property
    def gateway(self) -> AIGateway:
        if self._gateway is None:
            self._gateway = AIGateway()
        return self._gateway

    def _get_directors(self) -> list[Director]:
        """Get the directors to use. Lazy-init if not provided."""
        if self._directors is not None:
            return self._directors
        # Instantiate all 9 directors with the gateway
        return [d(gateway=self.gateway) for d in ALL_DIRECTORS]

    async def reach_consensus(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str = "agency",
        campaign_brief: dict[str, Any],
        industry: str = "",
        objective: str = "",
        budget: str = "",
        campaign_type: str = "",
        brand_id: uuid.UUID | None = None,
        additional_context: str = "",
        max_rounds: int = MAX_ROUNDS,
    ) -> tuple[ConsensusDecision, CouncilSession]:
        """Run the full council review and reach consensus.

        Returns:
            (ConsensusDecision, CouncilSession) — the decision and the
            full session record (all opinions from all rounds).
        """
        session_id = str(uuid.uuid4())
        session = CouncilSession(
            session_id=session_id,
            tenant_id=str(tenant_id),
            brand_id=str(brand_id or ""),
            campaign_brief=campaign_brief,
            status="in_review",
            created_at=_utcnow_iso(),
        )

        weights = compute_weights(
            industry=industry,
            objective=objective,
            budget=budget,
            campaign_type=campaign_type,
        )

        directors = self._get_directors()
        all_opinions: list[DirectorOpinion] = []
        opinions_by_round: dict[str, list[dict[str, Any]]] = {}
        total_tokens = 0
        total_cost = 0.0
        total_latency = 0.0

        for round_num in range(1, max_rounds + 1):
            session.rounds_completed = round_num
            round_opinions: list[DirectorOpinion] = []
            round_dicts: list[dict[str, Any]] = []

            # Previous round opinions (for rounds 2+)
            prev_for_directors = round_dicts if round_num > 1 else None
            prev_opinions = opinions_by_round.get(str(round_num - 1), [])

            for director in directors:
                op = director.review(
                    tenant_id=tenant_id,
                    plan=plan,
                    campaign_brief=campaign_brief,
                    round_number=round_num,
                    previous_opinions=prev_opinions if round_num > 1 else None,
                    additional_context=additional_context,
                )
                round_opinions.append(op)
                round_dicts.append(op.to_dict())
                total_tokens += op.tokens_used
                total_cost += op.cost_usd
                total_latency += op.latency_ms

            opinions_by_round[str(round_num)] = round_dicts
            all_opinions.extend(round_opinions)

            # Calculate disagreement
            disagreement = calculate_disagreement(round_opinions)

            # If disagreement is low, or we've hit max rounds, finalize
            if disagreement <= DISAGREEMENT_THRESHOLD or round_num >= max_rounds:
                break

            logger.info(
                "council round %d disagreement=%.2f (>%.2f, running another round)",
                round_num, disagreement, DISAGREEMENT_THRESHOLD,
            )

        # Build the final decision from the last round's opinions
        final_opinions = [
            DirectorOpinion.from_dict(d)
            for d in opinions_by_round[str(session.rounds_completed)]
        ]

        # Self-critique step
        self_critique = self._run_self_critique(
            tenant_id=tenant_id,
            plan=plan,
            campaign_brief=campaign_brief,
            opinions=final_opinions,
        )

        # Compute campaign score
        score = compute_campaign_score(final_opinions, weights)

        # Extract disagreements, minorities, risks
        disagreements = extract_disagreements(final_opinions)
        minorities = extract_minority_opinions(final_opinions, weights)
        all_risks = prioritize_risks(final_opinions)

        # Phase I3: Deeper consensus intelligence
        agreement_score = compute_agreement_score(final_opinions)
        disagreement_analysis = analyze_disagreements(final_opinions, weights)
        missing_info = identify_missing_information(final_opinions, campaign_brief)
        suggested_revisions = generate_suggested_revisions(final_opinions)
        confidence_interval = compute_confidence_interval(final_opinions, weights)

        # Determine approval status
        weighted_approval = self._compute_weighted_approval(final_opinions, weights)
        approval_status = self._determine_approval(
            weighted_approval=weighted_approval,
            score=score,
            self_critique=self_critique,
        )

        # Build executive decision
        executive_decision = self._build_executive_decision(
            approval_status=approval_status,
            weighted_approval=weighted_approval,
            score=score,
            opinions=final_opinions,
        )

        # Build final recommendation
        final_recommendation = self._build_final_recommendation(
            approval_status=approval_status,
            opinions=final_opinions,
            score=score,
        )

        # Weighted confidence
        total_weight = sum(weights.get(o.director, 0) for o in final_opinions)
        if total_weight > 0:
            weighted_confidence = (
                sum(weights.get(o.director, 0) * o.confidence for o in final_opinions)
                / total_weight
            )
        else:
            weighted_confidence = sum(o.confidence for o in final_opinions) / len(final_opinions)

        decision = ConsensusDecision(
            executive_decision=executive_decision,
            confidence=round(weighted_confidence, 4),
            approval_status=approval_status,
            final_recommendation=final_recommendation,
            disagreements=disagreements,
            minority_opinions=minorities,
            risks=all_risks,
            weights=weights,
            weighted_scores={
                o.director: o.confidence for o in final_opinions
            },
            self_critique=self_critique,
            rounds_completed=session.rounds_completed,
            campaign_score=score.to_dict(),
            agreement_score=agreement_score,
            disagreement_analysis=disagreement_analysis,
            missing_information=missing_info,
            suggested_revisions=suggested_revisions,
            confidence_interval=confidence_interval,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 6),
            total_latency_ms=round(total_latency, 2),
        )

        # Finalize session
        session.opinions_by_round = opinions_by_round
        session.consensus_decision = decision.to_dict()
        session.status = "completed"
        session.completed_at = _utcnow_iso()
        session.total_tokens = total_tokens
        session.total_cost_usd = round(total_cost, 6)
        session.total_latency_ms = round(total_latency, 2)

        return decision, session

    def _compute_weighted_approval(
        self, opinions: list[DirectorOpinion], weights: dict[str, float]
    ) -> float:
        """Compute the weighted approval rate (0.0-1.0)."""
        total_weight = sum(weights.get(o.director, 0) for o in opinions)
        if total_weight == 0:
            return sum(1 for o in opinions if o.approval) / len(opinions)
        return sum(weights.get(o.director, 0) for o in opinions if o.approval) / total_weight

    def _determine_approval(
        self,
        weighted_approval: float,
        score: CampaignScore,
        self_critique: list[str],
    ) -> str:
        """Determine the approval status. Deterministic given inputs."""
        # Compliance has veto power
        # (checked via score — if compliance_score < 40, reject)
        if score.compliance_score < 40:
            return "rejected"
        # If risk score is very low, reject
        if score.risk_score < 30:
            return "rejected"
        # If overall score is below threshold, revise
        if score.overall_score < APPROVAL_SCORE_THRESHOLD:
            return "revise"
        # If weighted approval is below threshold, revise
        if weighted_approval < APPROVAL_CONFIDENCE_THRESHOLD:
            return "revise"
        # If self-critique found critical issues, revise
        critical_critiques = [c for c in self_critique if "critical" in c.lower()]
        if critical_critiques:
            return "revise"
        return "approved"

    def _build_executive_decision(
        self,
        approval_status: str,
        weighted_approval: float,
        score: CampaignScore,
        opinions: list[DirectorOpinion],
    ) -> str:
        """Build the executive decision statement. Deterministic."""
        approval_pct = round(weighted_approval * 100, 1)
        if approval_status == "approved":
            return (
                f"The Agency Council approves this campaign with {approval_pct}% "
                f"weighted approval and an overall score of {score.overall_score}/100. "
                f"The council is confident in the campaign's strategic direction, "
                f"creative approach, and expected performance."
            )
        elif approval_status == "rejected":
            return (
                f"The Agency Council rejects this campaign. "
                f"Overall score: {score.overall_score}/100. "
                f"Compliance score: {score.compliance_score}/100. "
                f"Risk score: {score.risk_score}/100. "
                f"The campaign has critical issues that must be addressed before resubmission."
            )
        else:  # revise
            return (
                f"The Agency Council recommends revisions before approval. "
                f"Overall score: {score.overall_score}/100. "
                f"Weighted approval: {approval_pct}%. "
                f"The campaign has potential but needs improvements in key areas."
            )

    def _build_final_recommendation(
        self,
        approval_status: str,
        opinions: list[DirectorOpinion],
        score: CampaignScore,
    ) -> str:
        """Build the final recommendation. Deterministic."""
        if approval_status == "approved":
            # Collect top recommendations
            all_recs: list[str] = []
            for op in opinions:
                if op.approval and op.recommendations:
                    all_recs.extend(op.recommendations[:2])
            if all_recs:
                return "Proceed with the campaign. Key recommendations:\n" + "\n".join(
                    f"  - {r}" for r in all_recs[:5]
                )
            return "Proceed with the campaign as planned."

        elif approval_status == "rejected":
            rejections = [op for op in opinions if not op.approval]
            reasons: list[str] = []
            for op in rejections:
                if op.risks:
                    reasons.append(f"[{op.role}] {op.risks[0]}")
            if reasons:
                return "Do not proceed. Critical issues:\n" + "\n".join(
                    f"  - {r}" for r in reasons[:5]
                )
            return "Do not proceed. The campaign does not meet council standards."

        else:  # revise
            improvements: list[str] = []
            for op in opinions:
                if op.recommendations:
                    improvements.extend(op.recommendations[:1])
            if improvements:
                return "Revise the campaign before resubmission:\n" + "\n".join(
                    f"  - {r}" for r in improvements[:5]
                )
            return "Revise the campaign based on council feedback and resubmit."

    def _run_self_critique(
        self,
        *,
        tenant_id: uuid.UUID,
        plan: str,
        campaign_brief: dict[str, Any],
        opinions: list[DirectorOpinion],
    ) -> list[str]:
        """Run the self-critique step.

        The council asks:
        - What is wrong with this campaign?
        - What could fail?
        - What would a competitor do?
        - What would the customer dislike?
        - What assumptions are weak?

        Returns a list of critique points.
        """
        # Build a summary of opinions for the critique
        opinions_summary = "\n".join(
            f"- {op.role}: {op.opinion} (confidence: {op.confidence}, "
            f"approval: {op.approval}, priority: {op.priority})"
            for op in opinions
        )
        brief_summary = self._format_brief_for_critique(campaign_brief)

        prompt = (
            f"{self._safety_preamble()}\n"
            f"You are the Agency Council in self-critique mode.\n"
            f"Before making a final decision, the council must ask:\n"
            f"  1. What is wrong with this campaign?\n"
            f"  2. What could fail?\n"
            f"  3. What would a competitor do?\n"
            f"  4. What would the customer dislike?\n"
            f"  5. What assumptions are weak?\n\n"
            f"CAMPAIGN BRIEF:\n{brief_summary}\n\n"
            f"DIRECTOR OPINIONS:\n{opinions_summary}\n\n"
            f"List the top critique points (one per line, max 8). "
            f"Be honest and specific. Cite evidence from the brief."
        )

        schema = {
            "type": "object",
            "properties": {
                "critiques": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                },
            },
            "required": ["critiques"],
            "additionalProperties": False,
        }

        try:
            comp = self.gateway.complete(
                prompt=prompt,
                tier=Tier.large,
                schema=schema,
                task="council_self_critique",
                tenant_id=tenant_id,
                plan=plan,
                max_tokens=1024,
                temperature=0.3,
                prompt_version="council_self_critique_v1.0",
            )
            data = comp.json_value if comp.json_value else {}
            return list(data.get("critiques", []))
        except Exception as exc:
            logger.warning("self-critique failed: %s", exc)
            return ["Self-critique step failed — proceeding with director opinions only."]

    def _format_brief_for_critique(self, brief: dict[str, Any]) -> str:
        """Format the brief for the self-critique prompt (shorter)."""
        parts: list[str] = []
        for key in ("business_name", "industry", "goal", "budget", "objective"):
            if key in brief:
                parts.append(f"{key}: {brief[key]}")
        if "campaign_strategy" in brief:
            strat = brief["campaign_strategy"]
            if isinstance(strat, dict):
                parts.append(f"core_message: {strat.get('core_message', '')}")
        if "media_plan" in brief:
            media = brief["media_plan"]
            if isinstance(media, dict):
                channels = media.get("recommended_channels", [])
                parts.append(f"channels: {', '.join(str(c) for c in channels[:5])}")
        return "\n".join(parts) if parts else "Brief not available."

    def _safety_preamble(self) -> str:
        return (
            "You are part of an AI advertising agency council. "
            "SAFETY: Only cite evidence from the brief. "
            "Never invent features, statistics, or case studies. "
            "Be honest about risks.\n"
        )
