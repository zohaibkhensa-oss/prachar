"""campaign_performance table

Revision ID: 0006_campaign_performance
Revises: 0005_review_statuses
Create Date: 2026-07-25

Adds the campaign_performance table to store daily performance metrics
(impressions, clicks, conversions, spend, revenue, ctr, cpa, roas) per
campaign, per channel. One row per campaign per day per channel.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_campaign_performance"
down_revision: Union[str, None] = "0005_review_statuses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_performance",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("impressions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer, nullable=False, server_default="0"),
        sa.Column("conversions", sa.Integer, nullable=False, server_default="0"),
        sa.Column("spend", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("revenue", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ctr", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("cpa", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("roas", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("channel", sa.String(32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "date",
            "channel",
            name="uq_campaign_performance_campaign_date_channel",
        ),
    )
    op.create_index(
        "ix_campaign_performance_campaign_id", "campaign_performance", ["campaign_id"]
    )
    op.create_index("ix_campaign_performance_date", "campaign_performance", ["date"])


def downgrade() -> None:
    op.drop_index("ix_campaign_performance_date", table_name="campaign_performance")
    op.drop_index(
        "ix_campaign_performance_campaign_id", table_name="campaign_performance"
    )
    op.drop_table("campaign_performance")
