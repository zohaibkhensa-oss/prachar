"""workspace_timeline table — AI Runtime source of truth

Revision ID: 0011_workspace_timeline
Revises: 0010_email_verified
Create Date: 2026-07-28

Adds the ``workspace_timeline`` table — the immutable, append-only source of
truth for the AI Runtime. Every decision, every action, every output, every
learning is recorded here. Like Git history for marketing.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0011_workspace_timeline"
down_revision = "0010_email_verified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_timeline",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("brand_id", PGUUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("session_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("decision_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("entry_type", sa.String(40), nullable=False, index=True),
        sa.Column("actor", sa.String(16), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("detail", JSONB, nullable=True),
        sa.Column("replayable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("replay_inputs", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_timeline_brand_created", "workspace_timeline", ["brand_id", "created_at"])
    op.create_index("idx_timeline_session", "workspace_timeline", ["session_id"])
    op.create_index("idx_timeline_decision", "workspace_timeline", ["decision_id"])
    op.create_index("idx_timeline_type", "workspace_timeline", ["entry_type"])

    # Enable RLS
    op.execute("ALTER TABLE workspace_timeline ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON workspace_timeline
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    # Allow SECURITY DEFINER functions to bypass RLS (for system/worker writes)
    op.execute("ALTER TABLE workspace_timeline FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON workspace_timeline")
    op.execute("ALTER TABLE workspace_timeline NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE workspace_timeline DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_timeline_type", table_name="workspace_timeline")
    op.drop_index("idx_timeline_decision", table_name="workspace_timeline")
    op.drop_index("idx_timeline_session", table_name="workspace_timeline")
    op.drop_index("idx_timeline_brand_created", table_name="workspace_timeline")
    op.drop_table("workspace_timeline")
