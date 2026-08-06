from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Timestamped, TenantScoped, UUIDPK, utcnow
from .enums import (
    Actor,
    AdsNetwork,
    AssetStatus,
    AssetType,
    BillingProvider,
    BillingStatus,
    CampaignObjective,
    CampaignStatus,
    Channel,
    ConnectionStatus,
    CreativeType,
    KnowledgeLevel,
    KnowledgeSourceStatus,
    KnowledgeSourceType,
    KnowledgeFileType,
    Plan,
    PolicyStatus,
    Role,
)


class Tenant(Base, UUIDPK):
    __tablename__ = "tenants"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    plan: Mapped[Plan] = mapped_column(String(16), default=Plan.starter, nullable=False)
    region: Mapped[str | None] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class User(Base, UUIDPK, Timestamped):
    __tablename__ = "users"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    role: Mapped[Role] = mapped_column(String(16), default=Role.owner, nullable=False)
    pw_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    provider_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)


class Brand(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "brands"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    category: Mapped[str | None] = mapped_column(String(120))
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False, default="business")
    locales: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    tone: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    brand_graph: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    visibility_score: Mapped[float | None] = mapped_column(Float)
    next_loop_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Connection(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "connections"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    channel: Mapped[Channel | AdsNetwork] = mapped_column(String(40), nullable=False)
    oauth_tokens_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    scopes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    status: Mapped[ConnectionStatus] = mapped_column(
        String(16), default=ConnectionStatus.pending, nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("tenant_id", "brand_id", "channel", name="uq_connection_brand_channel"),
    )


class Asset(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "assets"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[AssetType] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    s3_key: Mapped[str | None] = mapped_column(String(1024))
    transcript: Mapped[str | None] = mapped_column(Text)
    entities: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[AssetStatus] = mapped_column(
        String(24), default=AssetStatus.pending, nullable=False
    )


class ContentItem(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "content_items"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("assets.id", ondelete="SET NULL"), index=True
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    locale: Mapped[str | None] = mapped_column(String(16))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), index=True
    )
    policy_status: Mapped[PolicyStatus] = mapped_column(
        String(16), default=PolicyStatus.pending, nullable=False
    )
    published_ref: Mapped[str | None] = mapped_column(String(1024))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index("ix_content_items_brand_channel_version", "brand_id", "channel", "version"),
    )


class Campaign(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "campaigns"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    network: Mapped[AdsNetwork] = mapped_column(String(40), nullable=False, index=True)
    objective: Mapped[CampaignObjective] = mapped_column(
        String(24), nullable=False
    )
    audience_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    budget_daily: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="INR", nullable=False)
    bid_strategy: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[CampaignStatus] = mapped_column(
        String(24), default=CampaignStatus.draft, nullable=False
    )
    network_campaign_id: Mapped[str | None] = mapped_column(String(256))
    guardrails: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Creative(Base, UUIDPK, Timestamped):
    __tablename__ = "creatives"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=False
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_items.id", ondelete="SET NULL"), index=True
    )
    type: Mapped[CreativeType] = mapped_column(String(20), nullable=False)
    locale: Mapped[str | None] = mapped_column(String(16))
    s3_key: Mapped[str | None] = mapped_column(String(1024))
    variant_group: Mapped[str | None] = mapped_column(String(64), index=True)
    network_creative_id: Mapped[str | None] = mapped_column(String(256))
    policy_status: Mapped[PolicyStatus] = mapped_column(
        String(16), default=PolicyStatus.pending, nullable=False
    )
    perf: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class MetricEvent(Base):
    __tablename__ = "metric_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=False
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=False
    )
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    metric: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        Index("ix_metric_events_brand_channel_metric_ts", "brand_id", "channel", "metric", "ts"),
    )


class Diagnosis(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "diagnoses"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    week: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # ISO YYYY-Www
    channel: Mapped[str] = mapped_column(String(40), nullable=False)
    findings: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    actions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=False
    )
    actor: Mapped[Actor] = mapped_column(String(16), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    __table_args__ = (
        # immutable: no UPDATE/DELETE grants applied via migration RLS/DCL
        Index("ix_audit_events_tenant_entity_ts", "tenant_id", "entity_type", "entity_id", "ts"),
    )


class Billing(Base, UUIDPK):
    __tablename__ = "billing"
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    provider: Mapped[BillingProvider] = mapped_column(String(16), nullable=False)
    sub_id: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[BillingStatus] = mapped_column(
        String(16), default=BillingStatus.trialing, nullable=False
    )
    ai_tokens_used_month: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    ai_budget_month: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class Report(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "reports"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    week: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    pdf_s3_key: Mapped[str | None] = mapped_column(String(1024))
    score_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    sent_via: Mapped[list[str] | None] = mapped_column(ARRAY(String))


class AuditJob(Base, UUIDPK, Timestamped):
    """Free-funnel audit (no auth). Rate-limited by IP + domain."""

    __tablename__ = "audit_jobs"
    input: Mapped[str] = mapped_column(String(2048), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(2048), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    score_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    findings: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    ip_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─── Marketing Intelligence Engine tables ───────────────────────────────────
# These 9 entities + the memory record form the persistent brain of PRACHAR.
# Every entity is tenant-scoped (RLS) and linked to a brand.


class BusinessMemoryRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Persistent business memory per brand. Updated by the Learning Engine."""

    __tablename__ = "business_memories"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    memory: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("tenant_id", "brand_id", name="uq_business_memories_brand"),
    )


class BusinessProfileRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Structured business understanding produced by BusinessIntelligenceEngine."""

    __tablename__ = "business_profiles"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class AudienceProfileRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Audience analysis produced by AudienceIntelligenceEngine."""

    __tablename__ = "audience_profiles"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class CompetitorProfileRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Competitor analysis produced by CompetitorIntelligenceEngine."""

    __tablename__ = "competitor_profiles"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class MarketingStrategyRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Marketing objective + campaign strategy (combined for query efficiency)."""

    __tablename__ = "marketing_strategies"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    objective: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    strategy: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class CreativeDirectionRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Creative direction produced by CreativeDirectionEngine."""

    __tablename__ = "creative_directions"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    direction: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class MediaPlanRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Media plan produced by MediaPlanningEngine."""

    __tablename__ = "media_plans"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class CampaignPlanRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Full campaign plan — the master record linking all intelligence outputs."""

    __tablename__ = "campaign_plans"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[str | None] = mapped_column(String(120))
    locale: Mapped[str] = mapped_column(String(16), default="en-IN", nullable=False)
    # Full campaign as JSONB (all 9 analyses)
    campaign: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Links to individual records
    business_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("business_profiles.id", ondelete="SET NULL"), index=True
    )
    audience_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("audience_profiles.id", ondelete="SET NULL"), index=True
    )
    competitor_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("competitor_profiles.id", ondelete="SET NULL"), index=True
    )
    marketing_strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("marketing_strategies.id", ondelete="SET NULL"), index=True
    )
    creative_direction_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("creative_directions.id", ondelete="SET NULL"), index=True
    )
    media_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("media_plans.id", ondelete="SET NULL"), index=True
    )
    overall_confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False, index=True)


class ExecutionPlanRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Execution plan produced by ExecutionPlanner."""

    __tablename__ = "execution_plans"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    campaign_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaign_plans.id", ondelete="SET NULL"),
        index=True,
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


class LearningReportRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Post-campaign learning report produced by LearningEngine."""

    __tablename__ = "learning_reports"
    brand_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    campaign_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaign_plans.id", ondelete="SET NULL"),
        index=True,
    )
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    performance_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(120))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(64))


# ─── Agency Council tables (migration 0003) ─────────────────────────────────


class CouncilSessionRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """A complete council review session (multiple rounds of director review)."""

    __tablename__ = "council_sessions"
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
    )
    campaign_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaign_plans.id", ondelete="SET NULL"),
        index=True,
    )
    campaign_brief: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    opinions_by_round: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    consensus_decision: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    rounds_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DirectorOpinionRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """A single director's opinion from a council session."""

    __tablename__ = "director_opinions"
    council_session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    director: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(120), nullable=False)
    opinion: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), default="medium", nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(120))


class ConsensusDecisionRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """The final consensus decision for a council session."""

    __tablename__ = "consensus_decisions"
    council_session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    decision: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    campaign_score: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rounds_completed: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class CampaignScoreRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Multi-dimensional campaign score from a council session."""

    __tablename__ = "campaign_scores"
    council_session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    campaign_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaign_plans.id", ondelete="SET NULL"),
        index=True,
    )
    strategy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    creative_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    media_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    brand_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    performance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    compliance_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weights_used: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class CouncilLearningRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Persistent learnings from council decisions."""

    __tablename__ = "council_learnings"
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True,
    )
    council_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("council_sessions.id", ondelete="SET NULL"),
        index=True,
    )
    campaign_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaign_plans.id", ondelete="SET NULL"),
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    minority_opinions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rejected_ideas: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    successful_recommendations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    failed_recommendations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    lessons: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class CampaignPerformance(Base, UUIDPK, Timestamped):
    """Daily performance metrics per campaign, per channel.

    Populated by channel adapters (P4.2) and the attribution pixel.
    One row per campaign per day per channel.
    """

    __tablename__ = "campaign_performance"
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spend: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    revenue: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cpa: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    roas: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    channel: Mapped[str | None] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "date", "channel", name="uq_campaign_performance_campaign_date_channel"
        ),
    )


class ReviewComment(Base, UUIDPK, TenantScoped, Timestamped):
    """Google Docs-style inline comment on a campaign preview.

    Comments are anchored to a snippet of highlighted text (``anchor_text``)
    so reviewers can point at a specific part of the campaign. Threading is
    supported via the self-referential ``parent_id`` FK — top-level comments
    have ``parent_id = NULL``; replies point at their parent comment.
    """

    __tablename__ = "review_comments"
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("review_comments.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    anchor_text: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    __table_args__ = (
        Index("ix_review_comments_campaign_resolved", "campaign_id", "resolved"),
    )


class ReviewVersion(Base, UUIDPK, TenantScoped, Timestamped):
    """Version snapshot of a campaign — Google Docs-style version history.

    Every inline edit (``PATCH /review/{id}/field``) and every restore creates a
    new ``ReviewVersion`` row containing a full JSONB snapshot of the campaign
    at that point in time. ``version_number`` is auto-incremented per campaign
    (1, 2, 3, …) so the history can be browsed and any prior version restored.
    """

    __tablename__ = "review_versions"
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "version_number", name="uq_review_versions_campaign_number"
        ),
        Index("ix_review_versions_campaign_number", "campaign_id", "version_number"),
    )


# ─── AI Runtime event stream (Phase E2.1) ────────────────────────────────────
# Every event published to the EventBus is persisted here so sessions can be
# reconstructed, debugged, and replayed without re-running the tools.


class RuntimeEventRecord(Base, UUIDPK, TenantScoped):
    """A single persisted runtime event — the durable event stream.

    Every event published to the EventBus is also written to this table.
    This enables debugging, visual replay of orb state transitions,
    deterministic testing without re-running tools, and full session
    reconstruction. Follows the same pattern as WorkspaceTimelineRecord.
    """

    __tablename__ = "runtime_events"
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(24), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(120), nullable=True)
    orb_state: Mapped[str] = mapped_column(String(24), nullable=False)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    __table_args__ = (
        Index("idx_runtime_events_session", "session_id"),
        Index("idx_runtime_events_type", "type"),
        Index("idx_runtime_events_timestamp", "timestamp"),
    )


# ─── Business Knowledge Hub ─────────────────────────────────────────────────
# Four-level knowledge system: Brand, Business, Marketing, Live Data
# Every document has full governance: source, version, owner, permissions, expiry
# Source attribution traces every AI answer back to the source documents.


class KnowledgeSourceRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """A knowledge source — a document, file, URL, or integration data feed.

    This is the top-level entity. Each source contains one or more chunks
    that are embedded and searchable.

    Governance fields:
    - source: where it came from (upload, URL, integration, generated, manual)
    - version: document version (user can upload v2, v3, etc.)
    - owner: who owns this knowledge (user ID or "system")
    - confidence: 0-1, how confident we are in this source
    - permissions: who can see/use this (private, shared, public)
    - expires_at: when this knowledge becomes stale
    - tags: user-defined tags for categorisation
    - workspace_id: workspace isolation (each workspace has its own KB)
    """

    __tablename__ = "knowledge_sources"
    # Workspace isolation — each workspace has its own knowledge base
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=True,
    )
    # Brand association (optional — some knowledge is brand-specific)
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("brands.id", ondelete="CASCADE"),
        index=True, nullable=True,
    )
    # Knowledge level (brand, business, marketing, live)
    level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Source type (upload, url, integration, generated, manual)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # File type (pdf, word, excel, csv, image, url, youtube, etc.)
    file_type: Mapped[str | None] = mapped_column(String(20))
    # Document metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Original file info
    file_name: Mapped[str | None] = mapped_column(String(500))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_url: Mapped[str | None] = mapped_column(String(2000))  # S3/storage URL
    mime_type: Mapped[str | None] = mapped_column(String(100))
    # Processing status
    status: Mapped[str] = mapped_column(
        String(20), default=KnowledgeSourceStatus.pending, nullable=False, index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Content stats
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    # ─── Governance ───
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    owner_name: Mapped[str | None] = mapped_column(String(200))
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    permissions: Mapped[str] = mapped_column(
        String(20), default="shared", nullable=False,
    )  # private, shared, public
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    tags: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    # Integration source (if source_type=integration)
    integration_name: Mapped[str | None] = mapped_column(String(50), index=True)
    # Content hash for deduplication
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    __table_args__ = (
        Index("idx_knowledge_sources_workspace", "workspace_id"),
        Index("idx_knowledge_sources_level", "level"),
        Index("idx_knowledge_sources_status", "status"),
        Index("idx_knowledge_sources_brand", "brand_id"),
        Index("idx_knowledge_sources_expires", "expires_at"),
    )


class KnowledgeChunkRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """A chunk of text extracted from a knowledge source.

    Chunks are the searchable units. Each chunk is embedded and stored
    in the vector store for similarity search.

    A chunk knows its parent source for source attribution.
    """

    __tablename__ = "knowledge_chunks"
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=True,
    )
    # Chunk metadata
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    # Location in original document (page number, slide number, etc.)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(200))
    # Embedding status
    embedded: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    # Metadata for filtering during search
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    __table_args__ = (
        Index("idx_knowledge_chunks_source", "source_id"),
        Index("idx_knowledge_chunks_workspace", "workspace_id"),
        Index("idx_knowledge_chunks_embedded", "embedded"),
    )


class KnowledgeEmbeddingRecord(Base, UUIDPK, TenantScoped):
    """Vector embedding for a knowledge chunk.

    Stored separately from the chunk for efficient vector operations.
    Uses pgvector if available, otherwise stores as JSONB array.

    In production with pgvector:
        embedding VECTOR(1536)
    For portability (no pgvector extension):
        embedding JSONB  (list of floats)
    """

    __tablename__ = "knowledge_embeddings"
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True, nullable=True,
    )
    # Embedding vector (stored as JSONB array of floats for portability)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB)
    embedding_dim: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False,
    )
    __table_args__ = (
        Index("idx_knowledge_embeddings_chunk", "chunk_id"),
        Index("idx_knowledge_embeddings_source", "source_id"),
        Index("idx_knowledge_embeddings_workspace", "workspace_id"),
    )


class KnowledgeAttributionRecord(Base, UUIDPK, TenantScoped, Timestamped):
    """Source attribution — traces AI answers back to source documents.

    When CampaignBrain, Creative Studio, or any AI engine uses knowledge
    from the hub, an attribution record is created. This lets every AI
    answer say:

        "Based on:
         - Brand Guidelines v3
         - Pricing Catalogue 2026
         - Campaign 'Diwali 2025'
         - GA4 Report (Last 90 Days)"
    """

    __tablename__ = "knowledge_attributions"
    # What AI output is being attributed
    output_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # e.g. campaign_id, creative_id, chat_message_id
    output_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Which sources were used
    source_ids: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    # Which chunks were retrieved (for precise citation)
    chunk_ids: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    # The query that was used to retrieve this knowledge
    query: Mapped[str | None] = mapped_column(Text)
    # Relevance scores for each source
    relevance_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    # The AI engine that used this knowledge
    engine: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (
        Index("idx_knowledge_attributions_output", "output_type", "output_id"),
        Index("idx_knowledge_attributions_engine", "engine"),
    )
