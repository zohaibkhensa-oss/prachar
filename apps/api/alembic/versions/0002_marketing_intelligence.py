"""marketing intelligence engine tables

Revision ID: 0002_marketing_intelligence
Revises: 0001_initial
Create Date: 2026-07-25

Adds the 9 marketing intelligence entities + business memory record.
All tables are tenant-scoped (RLS) and linked to brands.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_marketing_intelligence"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── business_memories: persistent memory per brand ─────────────────────
    op.create_table(
        "business_memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "brand_id", name="uq_business_memories_brand"),
    )
    op.create_index("ix_business_memories_tenant_id", "business_memories", ["tenant_id"])
    op.create_index("ix_business_memories_brand_id", "business_memories", ["brand_id"])

    # ─── business_profiles ──────────────────────────────────────────────────
    op.create_table(
        "business_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_business_profiles_tenant_id", "business_profiles", ["tenant_id"])
    op.create_index("ix_business_profiles_brand_id", "business_profiles", ["brand_id"])

    # ─── audience_profiles ──────────────────────────────────────────────────
    op.create_table(
        "audience_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audience_profiles_tenant_id", "audience_profiles", ["tenant_id"])
    op.create_index("ix_audience_profiles_brand_id", "audience_profiles", ["brand_id"])

    # ─── competitor_profiles ────────────────────────────────────────────────
    op.create_table(
        "competitor_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_competitor_profiles_tenant_id", "competitor_profiles", ["tenant_id"])
    op.create_index("ix_competitor_profiles_brand_id", "competitor_profiles", ["brand_id"])

    # ─── marketing_strategies (objective + strategy combined) ───────────────
    op.create_table(
        "marketing_strategies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("objective", postgresql.JSONB, nullable=False),
        sa.Column("strategy", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_marketing_strategies_tenant_id", "marketing_strategies", ["tenant_id"])
    op.create_index("ix_marketing_strategies_brand_id", "marketing_strategies", ["brand_id"])

    # ─── creative_directions ────────────────────────────────────────────────
    op.create_table(
        "creative_directions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_creative_directions_tenant_id", "creative_directions", ["tenant_id"])
    op.create_index("ix_creative_directions_brand_id", "creative_directions", ["brand_id"])

    # ─── media_plans ────────────────────────────────────────────────────────
    op.create_table(
        "media_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_media_plans_tenant_id", "media_plans", ["tenant_id"])
    op.create_index("ix_media_plans_brand_id", "media_plans", ["brand_id"])

    # ─── campaign_plans (master record) ─────────────────────────────────────
    op.create_table(
        "campaign_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("goal", sa.Text, nullable=False),
        sa.Column("budget", sa.String(120)),
        sa.Column("locale", sa.String(16), nullable=False, server_default="en-IN"),
        sa.Column("campaign", postgresql.JSONB, nullable=False),
        sa.Column("business_profile_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("business_profiles.id", ondelete="SET NULL")),
        sa.Column("audience_profile_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("audience_profiles.id", ondelete="SET NULL")),
        sa.Column("competitor_profile_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("competitor_profiles.id", ondelete="SET NULL")),
        sa.Column("marketing_strategy_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("marketing_strategies.id", ondelete="SET NULL")),
        sa.Column("creative_direction_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("creative_directions.id", ondelete="SET NULL")),
        sa.Column("media_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("media_plans.id", ondelete="SET NULL")),
        sa.Column("overall_confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_campaign_plans_tenant_id", "campaign_plans", ["tenant_id"])
    op.create_index("ix_campaign_plans_brand_id", "campaign_plans", ["brand_id"])
    op.create_index("ix_campaign_plans_status", "campaign_plans", ["status"])

    # ─── execution_plans ────────────────────────────────────────────────────
    op.create_table(
        "execution_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaign_plans.id", ondelete="SET NULL")),
        sa.Column("plan", postgresql.JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_execution_plans_tenant_id", "execution_plans", ["tenant_id"])
    op.create_index("ix_execution_plans_brand_id", "execution_plans", ["brand_id"])
    op.create_index("ix_execution_plans_campaign_plan_id", "execution_plans", ["campaign_plan_id"])

    # ─── learning_reports ───────────────────────────────────────────────────
    op.create_table(
        "learning_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaign_plans.id", ondelete="SET NULL")),
        sa.Column("report", postgresql.JSONB, nullable=False),
        sa.Column("performance_data", postgresql.JSONB),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("reasoning", sa.Text),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("prompt_version", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_learning_reports_tenant_id", "learning_reports", ["tenant_id"])
    op.create_index("ix_learning_reports_brand_id", "learning_reports", ["brand_id"])
    op.create_index("ix_learning_reports_campaign_plan_id", "learning_reports", ["campaign_plan_id"])

    # ─── RLS: enable + policies on all new tenant-scoped tables ─────────────
    rls_tables = [
        "business_memories", "business_profiles", "audience_profiles",
        "competitor_profiles", "marketing_strategies", "creative_directions",
        "media_plans", "campaign_plans", "execution_plans", "learning_reports",
    ]
    for t in rls_tables:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {t}_tenant_isolation ON {t} "
            f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )


def downgrade() -> None:
    tables = [
        "learning_reports", "execution_plans", "campaign_plans",
        "media_plans", "creative_directions", "marketing_strategies",
        "competitor_profiles", "audience_profiles", "business_profiles",
        "business_memories",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
