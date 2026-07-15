from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
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
    pw_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Brand(Base, UUIDPK, TenantScoped, Timestamped):
    __tablename__ = "brands"
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    website: Mapped[str | None] = mapped_column(String(2048))
    category: Mapped[str | None] = mapped_column(String(120))
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
        String(16), default=AssetStatus.pending, nullable=False
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
        String(16), default=CampaignStatus.draft, nullable=False
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
