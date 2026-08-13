"""initial schema with RLS

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-16

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ─── tenants (no RLS — root tenancy table) ──────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("plan", sa.String(16), nullable=False, server_default="starter"),
        sa.Column("region", sa.String(8)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # ─── users (tenant-scoped, RLS) ─────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="owner"),
        sa.Column("pw_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # ─── brands ─────────────────────────────────────────────────────────────
    op.create_table(
        "brands",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("website", sa.String(2048)),
        sa.Column("category", sa.String(120)),
        sa.Column("locales", postgresql.ARRAY(sa.String)),
        sa.Column("tone", postgresql.JSONB),
        sa.Column("brand_graph", postgresql.JSONB),
        sa.Column("visibility_score", sa.Float),
        sa.Column("next_loop_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_brands_tenant_id", "brands", ["tenant_id"])
    op.create_index("ix_brands_next_loop_at", "brands", ["next_loop_at"])

    # ─── connections ────────────────────────────────────────────────────────
    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("oauth_tokens_enc", sa.LargeBinary),
        sa.Column("scopes", postgresql.ARRAY(sa.String)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("tenant_id", "brand_id", "channel",
                            name="uq_connection_brand_channel"),
    )
    op.create_index("ix_connections_tenant_id", "connections", ["tenant_id"])
    op.create_index("ix_connections_brand_id", "connections", ["brand_id"])

    # ─── assets ─────────────────────────────────────────────────────────────
    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("source_url", sa.String(2048)),
        sa.Column("s3_key", sa.String(1024)),
        sa.Column("transcript", sa.Text),
        sa.Column("entities", postgresql.JSONB),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_assets_tenant_id", "assets", ["tenant_id"])
    op.create_index("ix_assets_brand_id", "assets", ["brand_id"])

    # ─── content_items ──────────────────────────────────────────────────────
    op.create_table(
        "content_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("assets.id", ondelete="SET NULL")),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("locale", sa.String(16)),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("content_items.id", ondelete="SET NULL")),
        sa.Column("policy_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("published_ref", sa.String(1024)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_content_items_tenant_id", "content_items", ["tenant_id"])
    op.create_index("ix_content_items_brand_id", "content_items", ["brand_id"])
    op.create_index("ix_content_items_channel", "content_items", ["channel"])
    op.create_index("ix_content_items_brand_channel_version",
                    "content_items", ["brand_id", "channel", "version"])

    # ─── campaigns ──────────────────────────────────────────────────────────
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("network", sa.String(40), nullable=False),
        sa.Column("objective", sa.String(24), nullable=False),
        sa.Column("audience_spec", postgresql.JSONB, nullable=False),
        sa.Column("budget_daily", sa.Float, nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="INR"),
        sa.Column("bid_strategy", postgresql.JSONB),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("network_campaign_id", sa.String(256)),
        sa.Column("guardrails", postgresql.JSONB),
        sa.Column("dry_run", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_campaigns_tenant_id", "campaigns", ["tenant_id"])
    op.create_index("ix_campaigns_brand_id", "campaigns", ["brand_id"])
    op.create_index("ix_campaigns_network", "campaigns", ["network"])

    # ─── creatives ──────────────────────────────────────────────────────────
    op.create_table(
        "creatives",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_item_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("content_items.id", ondelete="SET NULL")),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("locale", sa.String(16)),
        sa.Column("s3_key", sa.String(1024)),
        sa.Column("variant_group", sa.String(64)),
        sa.Column("network_creative_id", sa.String(256)),
        sa.Column("policy_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("perf", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_creatives_tenant_id", "creatives", ["tenant_id"])
    op.create_index("ix_creatives_campaign_id", "creatives", ["campaign_id"])
    op.create_index("ix_creatives_variant_group", "creatives", ["variant_group"])

    # ─── metric_events (partitioned by month) ───────────────────────────────
    op.create_table(
        "metric_events",
        sa.Column("id", sa.BigInteger, autoincrement=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", "ts"),
        postgresql_partition_by="RANGE (ts)",
    )
    op.create_index("ix_metric_events_tenant_id", "metric_events", ["tenant_id"])
    op.create_index("ix_metric_events_brand_channel_metric_ts",
                    "metric_events", ["brand_id", "channel", "metric", "ts"])
    op.execute(
        "CREATE TABLE metric_events_2026_07 PARTITION OF metric_events "
        "FOR VALUES FROM ('2026-07-01') TO ('2026-08-01')"
    )
    op.execute(
        "CREATE TABLE metric_events_default PARTITION OF metric_events DEFAULT"
    )

    # ─── diagnoses ──────────────────────────────────────────────────────────
    op.create_table(
        "diagnoses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week", sa.String(10), nullable=False),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("findings", postgresql.JSONB, nullable=False),
        sa.Column("actions", postgresql.JSONB, nullable=False),
        sa.Column("model_used", sa.String(120)),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_diagnoses_tenant_id", "diagnoses", ["tenant_id"])
    op.create_index("ix_diagnoses_brand_id", "diagnoses", ["brand_id"])
    op.create_index("ix_diagnoses_week", "diagnoses", ["week"])

    # ─── audit_events (immutable) ───────────────────────────────────────────
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor", sa.String(16), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(120), nullable=False),
        sa.Column("payload", postgresql.JSONB),
        sa.Column("ts", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_tenant_entity_ts",
                    "audit_events", ["tenant_id", "entity_type", "entity_id", "ts"])

    # ─── billing ────────────────────────────────────────────────────────────
    op.create_table(
        "billing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("sub_id", sa.String(256)),
        sa.Column("status", sa.String(16), nullable=False, server_default="trialing"),
        sa.Column("ai_tokens_used_month", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("ai_budget_month", sa.BigInteger, nullable=False, server_default="0"),
    )

    # ─── reports ────────────────────────────────────────────────────────────
    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week", sa.String(10), nullable=False),
        sa.Column("pdf_s3_key", sa.String(1024)),
        sa.Column("score_snapshot", postgresql.JSONB),
        sa.Column("sent_via", postgresql.ARRAY(sa.String)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    op.create_index("ix_reports_brand_id", "reports", ["brand_id"])
    op.create_index("ix_reports_week", "reports", ["week"])

    # ─── audit_jobs (free funnel, no auth, RLS-exempt) ──────────────────────
    op.create_table(
        "audit_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("input", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(2048)),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("score_snapshot", postgresql.JSONB),
        sa.Column("findings", postgresql.JSONB),
        sa.Column("error", sa.Text),
        sa.Column("ip_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_audit_jobs_input", "audit_jobs", ["input"])
    op.create_index("ix_audit_jobs_domain", "audit_jobs", ["domain"])
    op.create_index("ix_audit_jobs_ip_hash", "audit_jobs", ["ip_hash"])

    # ─── RLS: enable + policies on all tenant-scoped tables ─────────────────
    rls_tables = [
        "users", "brands", "connections", "assets", "content_items",
        "campaigns", "creatives", "metric_events", "diagnoses",
        "audit_events", "reports",
    ]
    for t in rls_tables:
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {t}_tenant_isolation ON {t} "
            f"USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid) "
            f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)"
        )

    # audit_events is immutable: revoke UPDATE/DELETE.
    op.execute("REVOKE UPDATE, DELETE ON audit_events FROM PUBLIC")

    # app.tenant_id setting (RLS enforces isolation; setting is open).
    # Set default app.tenant_id for RLS (skip on managed DBs like Supabase where ALTER DATABASE is restricted)
    op.execute("""
        DO $$ BEGIN
            EXECUTE 'ALTER DATABASE ' || current_database() || ' SET app.tenant_id = ''''';
        EXCEPTION WHEN insufficient_privilege THEN
            -- Managed Postgres (Supabase, RDS) may not allow ALTER DATABASE;
            -- the app sets app.tenant_id per-session via SET LOCAL anyway.
            RAISE NOTICE 'Skipping ALTER DATABASE app.tenant_id (insufficient privilege)';
        END $$;
    """)

    # ─── auth_lookup: SECURITY DEFINER function for login (bypasses RLS) ─────
    # NOTE: row_security=off is required so the function can bypass RLS
    # regardless of who owns the function (non-superuser owners need this).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_lookup(p_email TEXT)
        RETURNS TABLE (id uuid, tenant_id uuid, pw_hash text, role text, is_active boolean)
        LANGUAGE sql SECURITY DEFINER SET search_path = public, row_security = off AS $$
          SELECT id, tenant_id, pw_hash, role::text, is_active
          FROM users WHERE email = p_email LIMIT 1;
        $$;
        """
    )
    # Grant to prachar role if it exists (local dev), else grant to postgres (Supabase)
    op.execute("""
        DO $$ BEGIN
            GRANT EXECUTE ON FUNCTION auth_lookup(text) TO prachar;
        EXCEPTION WHEN undefined_object THEN
            GRANT EXECUTE ON FUNCTION auth_lookup(text) TO postgres;
        END $$;
    """)


def downgrade() -> None:
    tables = [
        "audit_jobs", "reports", "billing", "audit_events", "diagnoses",
        "metric_events_default", "metric_events_2026_07", "metric_events",
        "creatives", "campaigns", "content_items", "assets",
        "connections", "brands", "users", "tenants",
    ]
    for t in tables:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
