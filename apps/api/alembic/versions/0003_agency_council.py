"""agency council tables

Revision ID: 0003_agency_council
Revises: 0002_marketing_intelligence
Create Date: 2026-07-25

Adds the 5 Agency Council tables:
- council_sessions: complete review sessions (multiple rounds)
- director_opinions: individual director opinions
- consensus_decisions: final consensus decisions
- campaign_scores: multi-dimensional campaign scores
- council_learnings: persistent learnings from council decisions

All tables are tenant-scoped (RLS).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_agency_council"
down_revision: Union[str, None] = "0002_marketing_intelligence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── council_sessions ───────────────────────────────────────────────────
    op.create_table(
        "council_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True),
        sa.Column("campaign_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaign_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_brief", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opinions_by_round", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("consensus_decision", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("rounds_completed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("total_latency_ms", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_council_sessions_tenant_id", "council_sessions", ["tenant_id"])
    op.create_index("ix_council_sessions_brand_id", "council_sessions", ["brand_id"])
    op.create_index("ix_council_sessions_campaign_plan_id", "council_sessions", ["campaign_plan_id"])

    # ─── director_opinions ──────────────────────────────────────────────────
    op.create_table(
        "director_opinions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("council_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("council_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("director", sa.String(64), nullable=False),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("opinion", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("round_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("approval", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="medium"),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("model_used", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_director_opinions_tenant_id", "director_opinions", ["tenant_id"])
    op.create_index("ix_director_opinions_council_session_id", "director_opinions", ["council_session_id"])
    op.create_index("ix_director_opinions_director", "director_opinions", ["director"])

    # ─── consensus_decisions ────────────────────────────────────────────────
    op.create_table(
        "consensus_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("council_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("council_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("decision", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("campaign_score", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("approval_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("overall_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("rounds_completed", sa.Integer, nullable=False, server_default="1"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_consensus_decisions_tenant_id", "consensus_decisions", ["tenant_id"])
    op.create_index("ix_consensus_decisions_council_session_id", "consensus_decisions", ["council_session_id"])

    # ─── campaign_scores ────────────────────────────────────────────────────
    op.create_table(
        "campaign_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("council_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("council_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaign_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("strategy_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("creative_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("media_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("brand_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("performance_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("risk_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("compliance_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("overall_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("weights_used", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_campaign_scores_tenant_id", "campaign_scores", ["tenant_id"])
    op.create_index("ix_campaign_scores_council_session_id", "campaign_scores", ["council_session_id"])
    op.create_index("ix_campaign_scores_campaign_plan_id", "campaign_scores", ["campaign_plan_id"])

    # ─── council_learnings ──────────────────────────────────────────────────
    op.create_table(
        "council_learnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True),
        sa.Column("council_session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("council_sessions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("campaign_plan_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaign_plans.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("minority_opinions", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("rejected_ideas", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("successful_recommendations", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("failed_recommendations", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("lessons", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("overall_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_council_learnings_tenant_id", "council_learnings", ["tenant_id"])
    op.create_index("ix_council_learnings_brand_id", "council_learnings", ["brand_id"])
    op.create_index("ix_council_learnings_council_session_id", "council_learnings", ["council_session_id"])
    op.create_index("ix_council_learnings_campaign_plan_id", "council_learnings", ["campaign_plan_id"])


def downgrade() -> None:
    op.drop_table("council_learnings")
    op.drop_table("campaign_scores")
    op.drop_table("consensus_decisions")
    op.drop_table("director_opinions")
    op.drop_table("council_sessions")
