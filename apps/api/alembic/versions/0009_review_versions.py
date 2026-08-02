"""review_versions table for Google Docs-style version history

Revision ID: 0009_review_versions
Revises: 0008_review_comments
Create Date: 2026-07-26

Adds the ``review_versions`` table to support version history on campaigns.
Every inline edit (``PATCH /review/{id}/field``) and every restore creates a
new row containing a full JSONB snapshot of the campaign at that point in
time. ``version_number`` is auto-incremented per campaign so any prior
version can be viewed and restored.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_review_versions"
down_revision: Union[str, None] = "0008_review_comments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("snapshot", postgresql.JSONB, nullable=False),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "campaign_id",
            "version_number",
            name="uq_review_versions_campaign_number",
        ),
    )
    op.create_index(
        "ix_review_versions_tenant_id", "review_versions", ["tenant_id"]
    )
    op.create_index(
        "ix_review_versions_campaign_id", "review_versions", ["campaign_id"]
    )
    op.create_index(
        "ix_review_versions_author_id", "review_versions", ["author_id"]
    )
    op.create_index(
        "ix_review_versions_campaign_number",
        "review_versions",
        ["campaign_id", "version_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_review_versions_campaign_number", table_name="review_versions"
    )
    op.drop_index("ix_review_versions_author_id", table_name="review_versions")
    op.drop_index("ix_review_versions_campaign_id", table_name="review_versions")
    op.drop_index("ix_review_versions_tenant_id", table_name="review_versions")
    op.drop_table("review_versions")
