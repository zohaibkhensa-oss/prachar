"""AWS deployment readiness: RLS coverage, tenant_id on campaign_performance,
dedicated app DB role, SSL config, and s3_key column for knowledge sources.

Revision ID: 0015_aws_readiness
Revises: 0014_social_login
Create Date: 2026-08-03

Changes:
1. Add s3_key column to knowledge_sources (for S3-backed file storage)
2. Add tenant_id to campaign_performance (was missing RLS scoping)
3. Enable RLS on tables identified as missing it
4. Create dedicated prachar_app role (non-owner) with limited privileges
5. Configure SSL verification for RDS connections
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_aws_readiness"
down_revision = "0016_dispatch_due"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add s3_key column to knowledge_sources
    op.add_column(
        "knowledge_sources",
        sa.Column("s3_key", sa.String(500), nullable=True),
    )

    # 2. Add tenant_id to campaign_performance if it doesn't exist
    #    (campaign_performance was created without tenant_id in migration 0006)
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'campaign_performance' AND column_name = 'tenant_id'"
    ))
    if not result.fetchone():
        op.add_column(
            "campaign_performance",
            sa.Column("tenant_id", sa.String(36), nullable=True, index=True),
        )
        # Backfill tenant_id from campaigns table
        op.execute("""
            UPDATE campaign_performance cp
            SET tenant_id = c.tenant_id
            FROM campaigns c
            WHERE cp.campaign_id = c.id
        """)
        # Now make it NOT NULL
        op.alter_column("campaign_performance", "tenant_id", nullable=False)

    # 3. Enable RLS on tables that were identified as missing it
    #    These tables exist but didn't have RLS policies
    rls_tables = [
        "campaign_performance",
        "runtime_events",
        "workspace_timeline",
        "knowledge_embeddings",
    ]

    for table in rls_tables:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            DO $$ BEGIN
                CREATE POLICY {table}_tenant_isolation
                ON {table}
                USING (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''))
                WITH CHECK (tenant_id::text = NULLIF(current_setting('app.tenant_id', true), ''));
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END $$;
        """)

    # 4. Create dedicated application role (non-owner)
    #    The app should NOT use the master/owner role in production
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prachar_app') THEN
                CREATE ROLE prachar_app WITH LOGIN PASSWORD 'CHANGE_ME_IN_PRODUCTION';
            END IF;
        END
        $$;
    """)

    # Grant limited privileges to app role
    op.execute("""
        GRANT CONNECT ON DATABASE prachar TO prachar_app;
        GRANT USAGE ON SCHEMA public TO prachar_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO prachar_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO prachar_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO prachar_app;
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
            GRANT USAGE, SELECT ON SEQUENCES TO prachar_app;
    """)

    # NOTE: TLS enforcement for prachar_app belongs in pg_hba / connection
    # strings (sslmode is a libpq client parameter, not a server config) —
    # ALTER ROLE ... SET sslmode is invalid and would abort the migration.


def downgrade() -> None:
    # Remove RLS from the tables we added it to
    rls_tables = [
        "campaign_performance",
        "runtime_events",
        "workspace_timeline",
        "knowledge_embeddings",
    ]
    for table in rls_tables:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.drop_column("knowledge_sources", "s3_key")

    # Note: We do NOT drop the prachar_app role in downgrade as it may
    # have been modified in production. Drop manually if needed.
