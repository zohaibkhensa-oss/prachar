"""add review workflow statuses to CampaignStatus and AssetStatus

Revision ID: 0005_review_statuses
Revises: 0004_customer_type
Create Date: 2026-07-25

Adds three new values to the CampaignStatus and AssetStatus enums to support
the human-in-the-loop review workflow:

CampaignStatus (existing: draft, active, paused, ended):
  - in_review
  - changes_requested
  - approved

AssetStatus (existing: pending, processing, ready, failed):
  - in_review
  - changes_requested
  - approved

Both enums are stored as plain VARCHAR/string columns in PostgreSQL (the
SQLAlchemy models use StrEnum, which serialises to text), so no column type
changes or CHECK-constraint edits are required. This migration is a no-op
schema-wise and exists purely for tracking/auditability of the additive
enum-value change. It is fully reversible (downgrade is also a no-op).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0005_review_statuses"
down_revision: Union[str, None] = "0004_customer_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: StrEnum values are stored as strings in PostgreSQL, so adding
    # new enum members does not require any schema changes. Existing rows
    # remain valid; new rows may use the additional statuses.
    pass


def downgrade() -> None:
    # No-op: removing the new enum members from the Python StrEnum is safe
    # at the database level. Rows holding the new values (if any) would need
    # to be cleaned up by application code before downgrading the app.
    pass
