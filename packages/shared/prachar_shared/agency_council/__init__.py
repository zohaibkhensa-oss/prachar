"""Agency Council — the core IP of CURV AI.

Every campaign is reviewed by multiple specialist AI Directors before a
final recommendation is produced. No single AI agent is allowed to make
the final campaign decision.

Architecture:
    CURV AI → Campaign Brain → Agency Council → Consensus Engine
        → Creative Orchestrator → Workers → Publishing → Learning

The Council consists of 9 independent AI Directors:
1. Chief Strategy Officer — positioning, objective, market opportunity
2. Chief Creative Officer — creative concept, storytelling, visual language
3. Chief Media Officer — channel mix, schedule, frequency, reach
4. Chief Performance Officer — ROI, CAC, CPA, CTR, conversions
5. Chief Brand Officer — brand consistency, tone, messaging, brand safety
6. Chief Financial Officer — budget approval, return, risk, cost efficiency
7. Chief Compliance Officer — policies, legal, claims, regulatory
8. Chief Customer Officer — audience fit, psychology, pain points, journey
9. Chief Analytics Officer — historical performance, memory, insights

Every Director returns a 9-field contract:
    opinion, reasoning, confidence, risks, alternatives,
    recommendations, evidence, priority, approval

The Consensus Engine uses WEIGHTED consensus (not majority voting).
Weights depend on campaign objective, industry, budget, and campaign type.
If disagreement is high, the engine runs another round (max 3).
Before final approval, the engine runs a SELF-CRITIQUE step.

Clean architecture:
- Domain: models.py, director_base.py, directors.py, consensus.py, memory.py
- Application: CouncilOrchestrator (this package)
- Infrastructure: PostgresCouncilRepository (in api app)
- Presentation: agency_council router (in api app)
"""
from __future__ import annotations

from .director_base import Director
from .directors import (
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
)
from .models import (
    CampaignScore,
    CouncilLearning,
    CouncilSession,
    ConsensusDecision,
    DirectorOpinion,
)
from .memory import (
    CouncilMemoryRepository,
    CouncilMemoryStore,
    InMemoryCouncilRepository,
)
from .consensus import (
    ConsensusEngine,
    compute_weights,
    calculate_disagreement,
    extract_minority_opinions,
    extract_disagreements,
    extract_all_risks,
    compute_campaign_score,
    compute_agreement_score,
    analyze_disagreements,
    prioritize_risks,
    identify_missing_information,
    generate_suggested_revisions,
    compute_confidence_interval,
)
from .bro_integration import (
    is_council_review_request,
    summarise_council_decision,
    COUNCIL_REVIEW_KEYWORDS,
)

__all__ = [
    # Base
    "Director",
    # Directors
    "ChiefStrategyOfficer",
    "ChiefCreativeOfficer",
    "ChiefMediaOfficer",
    "ChiefPerformanceOfficer",
    "ChiefBrandOfficer",
    "ChiefFinancialOfficer",
    "ChiefComplianceOfficer",
    "ChiefCustomerOfficer",
    "ChiefAnalyticsOfficer",
    "ALL_DIRECTORS",
    "DIRECTOR_NAMES",
    # Models
    "DirectorOpinion",
    "ConsensusDecision",
    "CampaignScore",
    "CouncilSession",
    "CouncilLearning",
    # Memory
    "CouncilMemoryRepository",
    "CouncilMemoryStore",
    "InMemoryCouncilRepository",
    # Consensus
    "ConsensusEngine",
    "compute_weights",
    "calculate_disagreement",
    "extract_minority_opinions",
    "extract_disagreements",
    "extract_all_risks",
    "compute_campaign_score",
    "compute_agreement_score",
    "analyze_disagreements",
    "prioritize_risks",
    "identify_missing_information",
    "generate_suggested_revisions",
    "compute_confidence_interval",
    # CURV AI integration
    "is_council_review_request",
    "summarise_council_decision",
    "COUNCIL_REVIEW_KEYWORDS",
]
