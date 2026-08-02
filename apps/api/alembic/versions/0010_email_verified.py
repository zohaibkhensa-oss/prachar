"""email_verified column on users

Revision ID: 0010_email_verified
Revises: 0009_review_versions
Create Date: 2026-07-26

Adds ``email_verified`` boolean column to the ``users`` table. Defaults to
``false`` for new users. Existing users are backfilled to ``true`` so they
don't get locked out after the migration.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0010_email_verified"
down_revision = "0009_review_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    # Backfill existing users as verified so they don't get locked out
    op.execute("UPDATE users SET email_verified = true")
    # Update auth_lookup function to include email_verified column
    op.execute("""
        DROP FUNCTION IF EXISTS auth_lookup(text);
        CREATE FUNCTION auth_lookup(p_email TEXT)
        RETURNS TABLE (id uuid, tenant_id uuid, pw_hash text, role text, is_active boolean, email_verified boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT id, tenant_id, pw_hash, role::text, is_active, email_verified FROM users WHERE email = p_email LIMIT 1;
        $$;
        GRANT EXECUTE ON FUNCTION auth_lookup(text) TO prachar;
    """)
    # Add auth_lookup_by_id for token-based flows (verify email, reset password)
    op.execute("""
        CREATE OR REPLACE FUNCTION auth_lookup_by_id(p_uid TEXT)
        RETURNS TABLE (id uuid, tenant_id uuid, pw_hash text, role text, is_active boolean, email_verified boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT id, tenant_id, pw_hash, role::text, is_active, email_verified FROM users WHERE id::text = p_uid LIMIT 1;
        $$;
        GRANT EXECUTE ON FUNCTION auth_lookup_by_id(text) TO prachar;
    """)


def downgrade() -> None:
    # Restore old auth_lookup signature
    op.execute("""
        DROP FUNCTION IF EXISTS auth_lookup(text);
        CREATE FUNCTION auth_lookup(p_email TEXT)
        RETURNS TABLE (id uuid, tenant_id uuid, pw_hash text, role text, is_active boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT id, tenant_id, pw_hash, role::text, is_active FROM users WHERE email = p_email LIMIT 1;
        $$;
        GRANT EXECUTE ON FUNCTION auth_lookup(text) TO prachar;
    """)
    op.drop_column("users", "email_verified")
