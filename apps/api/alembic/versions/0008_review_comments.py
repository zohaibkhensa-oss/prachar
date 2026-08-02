"""review_comments table for Google Docs-style inline comments

Revision ID: 0008_review_comments
Revises: 0007_widen_status_columns
Create Date: 2026-07-25

Adds the ``review_comments`` table to support inline, threaded comments on
campaign previews. Comments are anchored to a snippet of highlighted text
(``anchor_text``) and may be threaded via the self-referential ``parent_id``
foreign key. Comments can be resolved (``resolved`` boolean).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_review_comments"
down_revision: Union[str, None] = "0007_widen_status_columns"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_comments",
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
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("review_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("anchor_text", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "resolved",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
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
    )
    op.create_index(
        "ix_review_comments_tenant_id", "review_comments", ["tenant_id"]
    )
    op.create_index(
        "ix_review_comments_campaign_id", "review_comments", ["campaign_id"]
    )
    op.create_index(
        "ix_review_comments_author_id", "review_comments", ["author_id"]
    )
    op.create_index(
        "ix_review_comments_parent_id", "review_comments", ["parent_id"]
    )
    op.create_index(
        "ix_review_comments_campaign_resolved",
        "review_comments",
        ["campaign_id", "resolved"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_review_comments_campaign_resolved", table_name="review_comments"
    )
    op.drop_index("ix_review_comments_parent_id", table_name="review_comments")
    op.drop_index("ix_review_comments_author_id", table_name="review_comments")
    op.drop_index(
        "ix_review_comments_campaign_id", table_name="review_comments"
    )
    op.drop_index("ix_review_comments_tenant_id", table_name="review_comments")
    op.drop_table("review_comments")
