"""Scheduled content publishing.

Adds ``content_items.scheduled_at`` and the SECURITY DEFINER functions the
worker uses to discover due items across tenants (same pattern as
``due_brands_for_dispatch`` — the worker role must not get BYPASSRLS):

- ``due_scheduled_content(now)`` -> (tenant_id, content_item_id) for items
  whose scheduled_at has passed and which have not published/failed yet.
- ``content_item_tenant(item_id)`` -> tenant uuid so the worker can set
  ``app.tenant_id`` before RLS-scoped reads.

Revision ID: 0017_scheduled_content
Revises: 0015_aws_readiness
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_scheduled_content"
down_revision = "0015_aws_readiness"
branch_labels = None
depends_on = None


def _grant(fn: str) -> None:
    op.execute(f"""
        DO $$ BEGIN
            REVOKE ALL ON FUNCTION {fn} FROM PUBLIC;
            IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'prachar') THEN
                GRANT EXECUTE ON FUNCTION {fn} TO prachar;
            END IF;
            EXECUTE format('GRANT EXECUTE ON FUNCTION {fn} TO %I', current_user);
        END $$;
    """)


def upgrade() -> None:
    op.add_column(
        "content_items",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_content_items_scheduled_at", "content_items", ["scheduled_at"])

    op.execute("""
        CREATE OR REPLACE FUNCTION due_scheduled_content(p_now timestamptz DEFAULT now())
        RETURNS TABLE (tenant_id uuid, content_item_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public SET row_security = off AS $$
          SELECT c.tenant_id, c.id
          FROM content_items c
          WHERE c.scheduled_at IS NOT NULL
            AND c.scheduled_at <= p_now
            AND c.published_at IS NULL
            AND COALESCE(c.payload->>'schedule_state', 'scheduled') NOT IN ('failed', 'publishing');
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION content_item_tenant(p_item_id uuid)
        RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public SET row_security = off AS $$
          SELECT c.tenant_id FROM content_items c WHERE c.id = p_item_id;
        $$;
    """)
    _grant("due_scheduled_content(timestamptz)")
    _grant("content_item_tenant(uuid)")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS due_scheduled_content(timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS content_item_tenant(uuid)")
    op.drop_index("ix_content_items_scheduled_at", table_name="content_items")
    op.drop_column("content_items", "scheduled_at")
