"""add customer_type to brands

Revision ID: 0004_customer_type
Revises: 0003_agency_council
Create Date: 2026-07-25

Adds customer_type column to brands table to support two customer segments:
- "business" (default): traditional businesses (restaurants, clinics, retail, etc.)
- "creator": content creators (YouTube creators, podcasters, influencers, etc.)

Existing brands default to "business".
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_customer_type"
down_revision: Union[str, None] = "0003_agency_council"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "brands",
        sa.Column("customer_type", sa.String(20), nullable=False, server_default="business"),
    )


def downgrade() -> None:
    op.drop_column("brands", "customer_type")
