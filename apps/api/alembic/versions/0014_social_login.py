"""social login columns on users

Revision ID: 0014_social_login
Revises: 0013_knowledge_hub
Create Date: 2026-08-07

Adds provider, provider_id, full_name, avatar_url columns to users.
Makes pw_hash nullable (social login users don't have passwords).
Updates auth_lookup functions to handle passwordless users.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0014_social_login"
down_revision = "0013_knowledge_hub"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add social login columns
    op.add_column("users", sa.Column("provider", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("provider_id", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("full_name", sa.String(160), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(2048), nullable=True))

    # Make pw_hash nullable (social login users don't have passwords)
    op.alter_column("users", "pw_hash", nullable=True)

    # Index for fast OAuth lookups
    op.create_index("ix_users_provider", "users", ["provider", "provider_id"])

    # Update auth_lookup to handle NULL pw_hash
    op.execute("""
        DROP FUNCTION IF EXISTS auth_lookup(text);
        CREATE FUNCTION auth_lookup(p_email TEXT)
        RETURNS TABLE (id uuid, tenant_id uuid, pw_hash text, role text, is_active boolean, email_verified boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT id, tenant_id, pw_hash, role::text, is_active, email_verified FROM users WHERE email = p_email LIMIT 1;
        $$;
        DO $$ BEGIN
            GRANT EXECUTE ON FUNCTION auth_lookup(text) TO prachar;
        EXCEPTION WHEN undefined_object THEN
            GRANT EXECUTE ON FUNCTION auth_lookup(text) TO postgres;
        END $$;
    """)

    # Update auth_lookup_by_id too
    op.execute("""
        CREATE OR REPLACE FUNCTION auth_lookup_by_id(p_uid TEXT)
        RETURNS TABLE (id uuid, tenant_id uuid, pw_hash text, role text, is_active boolean, email_verified boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT id, tenant_id, pw_hash, role::text, is_active, email_verified FROM users WHERE id::text = p_uid LIMIT 1;
        $$;
        DO $$ BEGIN
            GRANT EXECUTE ON FUNCTION auth_lookup_by_id(text) TO prachar;
        EXCEPTION WHEN undefined_object THEN
            GRANT EXECUTE ON FUNCTION auth_lookup_by_id(text) TO postgres;
        END $$;
    """)


def downgrade() -> None:
    op.drop_index("ix_users_provider", table_name="users")
    op.alter_column("users", "pw_hash", nullable=False)
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "full_name")
    op.drop_column("users", "provider_id")
    op.drop_column("users", "provider")
