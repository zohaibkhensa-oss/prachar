"""runtime_events table — persisted event stream for replay/debugging

Revision ID: 0012_runtime_events
Revises: 0011_workspace_timeline
Create Date: 2026-07-29

Adds the ``runtime_events`` table — every event published to the EventBus is
persisted here. This enables debugging, visual replay of orb state transitions,
deterministic testing without re-running tools, and full session reconstruction.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0012_runtime_events"
down_revision = "0011_workspace_timeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_events",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PGUUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("session_id", sa.String(64), nullable=False, index=True),
        sa.Column("decision_id", sa.String(64), nullable=True, index=True),
        sa.Column("type", sa.String(120), nullable=False, index=True),
        sa.Column("phase", sa.String(24), nullable=False),
        sa.Column("tool", sa.String(120), nullable=True),
        sa.Column("orb_state", sa.String(24), nullable=False),
        sa.Column("data", JSONB, nullable=True),
        sa.Column("progress", JSONB, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.create_index("idx_runtime_events_session", "runtime_events", ["session_id"])
    op.create_index("idx_runtime_events_type", "runtime_events", ["type"])
    op.create_index("idx_runtime_events_timestamp", "runtime_events", ["timestamp"])

    # Enable RLS
    op.execute("ALTER TABLE runtime_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON runtime_events
        USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    # Allow SECURITY DEFINER functions to bypass RLS (for system/worker writes)
    op.execute("ALTER TABLE runtime_events FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON runtime_events")
    op.execute("ALTER TABLE runtime_events NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE runtime_events DISABLE ROW LEVEL SECURITY")
    op.drop_index("idx_runtime_events_timestamp", table_name="runtime_events")
    op.drop_index("idx_runtime_events_type", table_name="runtime_events")
    op.drop_index("idx_runtime_events_session", table_name="runtime_events")
    op.drop_table("runtime_events")
