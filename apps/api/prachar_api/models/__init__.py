from __future__ import annotations

from .base import UUIDPK, Base, TenantScoped, Timestamped, utcnow
from .enums import *  # noqa: F403
from .tables import (
    Asset,
    AudienceProfileRecord,
    AuditEvent,
    AuditJob,
    Billing,
    Brand,
    BusinessMemoryRecord,
    BusinessProfileRecord,
    Campaign,
    CampaignPerformance,
    CampaignPlanRecord,
    CampaignScoreRecord,
    CompetitorProfileRecord,
    Connection,
    ConsensusDecisionRecord,
    ContentItem,
    CouncilLearningRecord,
    CouncilSessionRecord,
    Creative,
    CreativeDirectionRecord,
    Diagnosis,
    DirectorOpinionRecord,
    ExecutionPlanRecord,
    KnowledgeAttributionRecord,
    KnowledgeChunkRecord,
    KnowledgeEmbeddingRecord,
    KnowledgeSourceRecord,
    LearningReportRecord,
    MarketingStrategyRecord,
    MediaPlanRecord,
    MetricEvent,
    Report,
    ReviewComment,
    ReviewVersion,
    Tenant,
    User,
)

# AI Runtime — WorkspaceTimeline is defined in runtime/timeline.py to keep
# the runtime package self-contained, but it uses the same Base/metadata.
# NOTE: imported after .tables on purpose — runtime/__init__ imports
# context/tools which reference this package; loading timeline late avoids
# a partially-initialized models module (circular import guard).
from ..runtime.timeline import WorkspaceTimeline  # noqa: E402

__all__ = [
    "Base",
    "TenantScoped",
    "Timestamped",
    "UUIDPK",
    "utcnow",
    "Tenant",
    "User",
    "Brand",
    "Connection",
    "Asset",
    "ContentItem",
    "Campaign",
    "Creative",
    "MetricEvent",
    "Diagnosis",
    "AuditEvent",
    "Billing",
    "Report",
    "AuditJob",
    "ReviewComment",
    "ReviewVersion",
    # Marketing Intelligence Engine
    "BusinessMemoryRecord",
    "BusinessProfileRecord",
    "AudienceProfileRecord",
    "CompetitorProfileRecord",
    "MarketingStrategyRecord",
    "CreativeDirectionRecord",
    "MediaPlanRecord",
    "CampaignPlanRecord",
    "CampaignPerformance",
    "ExecutionPlanRecord",
    "LearningReportRecord",
    # Agency Council
    "CouncilSessionRecord",
    "DirectorOpinionRecord",
    "ConsensusDecisionRecord",
    "CampaignScoreRecord",
    "CouncilLearningRecord",
    # AI Runtime
    "WorkspaceTimeline",
    # Business Knowledge Hub
    "KnowledgeSourceRecord",
    "KnowledgeChunkRecord",
    "KnowledgeEmbeddingRecord",
    "KnowledgeAttributionRecord",
]
