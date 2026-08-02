"""widen status columns for review workflow enum values

Revision ID: 0007_widen_status_columns
Revises: 0006_campaign_performance
Create Date: 2026-07-25

The CampaignStatus and AssetStatus enums gained three new members in
revision 0005 (in_review, changes_requested, approved). The longest of
these — "changes_requested" — is 18 characters, but the existing
``campaigns.status`` and ``assets.status`` columns are VARCHAR(16).
This migration widens both columns to VARCHAR(24) so the new enum
values can be stored without truncation.

Revision 0005 was a no-op (it assumed no column change was needed);
this migration corrects that oversight.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_widen_status_columns"
down_revision: Union[str, None] = "0006_campaign_performance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "campaigns", "status",
        existing_type=sa.String(16),
        type_=sa.String(24),
        existing_nullable=False,
    )
    op.alter_column(
        "assets", "status",
        existing_type=sa.String(16),
        type_=sa.String(24),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "assets", "status",
        existing_type=sa.String(24),
        type_=sa.String(16),
        existing_nullable=False,
    )
    op.alter_column(
        "campaigns", "status",
        existing_type=sa.String(24),
        type_=sa.String(16),
        existing_nullable=False,
    )
