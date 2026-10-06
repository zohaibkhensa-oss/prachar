"""Narrowly-scoped SECURITY DEFINER functions for worker dispatch.

The dispatcher must discover due brands across tenants, but the worker role
must not get BYPASSRLS. These functions expose only identifiers:

- ``due_brands_for_dispatch(now)`` -> (tenant_id, brand_id) pairs for brands
  whose weekly loop is due.
- ``brand_tenant_id(brand_id)`` -> tenant uuid for a single brand; used to
  establish ``app.tenant_id`` before tenant-scoped processing (resolving the
  brand's tenant is itself RLS-blocked, a chicken-and-egg problem).

Revision ID: 0016_dispatch_due
Revises: 0014_social_login
"""

from alembic import op

revision = "0016_dispatch_due"
down_revision = "0014_social_login"
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
    op.execute("""
        CREATE OR REPLACE FUNCTION due_brands_for_dispatch(p_now timestamptz DEFAULT now())
        RETURNS TABLE (tenant_id uuid, brand_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public SET row_security = off AS $$
          SELECT b.tenant_id, b.id
          FROM brands b
          WHERE b.next_loop_at <= p_now OR b.next_loop_at IS NULL;
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION brand_tenant_id(p_brand_id uuid)
        RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public SET row_security = off AS $$
          SELECT b.tenant_id FROM brands b WHERE b.id = p_brand_id;
        $$;
    """)
    _grant("due_brands_for_dispatch(timestamptz)")
    _grant("brand_tenant_id(uuid)")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS due_brands_for_dispatch(timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS brand_tenant_id(uuid)")
