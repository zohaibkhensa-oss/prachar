"""Business Knowledge Hub — knowledge sources, chunks, embeddings, attributions

Revision ID: 0013_knowledge_hub
Revises: 0012_runtime_events
Create Date: 2026-07-29

Adds the Business Knowledge Hub tables:
- knowledge_sources: uploaded documents with governance (level, version, owner, permissions, expiry)
- knowledge_chunks: text chunks extracted from sources, ready for embedding
- knowledge_embeddings: vector embeddings for similarity search
- knowledge_attributions: source attribution tracing AI answers to source documents

Four knowledge levels: brand, business, marketing, live
Workspace isolation: each workspace has its own knowledge base
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0013_knowledge_hub"
down_revision = "0012_runtime_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── knowledge_sources ─────────────────────────────────────────────
    op.create_table(
        "knowledge_sources",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("workspace_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("brand_id", PGUUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("level", sa.String(20), nullable=False, index=True),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("file_name", sa.String(500), nullable=True),
        sa.Column("file_size", sa.BigInteger, nullable=True),
        sa.Column("file_url", sa.String(2000), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("processing_error", sa.Text, nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chunk_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer, nullable=True),
        # Governance
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("owner_id", PGUUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_name", sa.String(200), nullable=True),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.8"),
        sa.Column("permissions", sa.String(20), nullable=False, server_default="shared"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("tags", JSONB, nullable=True, server_default="[]"),
        sa.Column("integration_name", sa.String(50), nullable=True, index=True),
        sa.Column("content_hash", sa.String(64), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_sources_workspace", "knowledge_sources", ["workspace_id"])
    op.create_index("idx_knowledge_sources_level", "knowledge_sources", ["level"])
    op.create_index("idx_knowledge_sources_status", "knowledge_sources", ["status"])
    op.create_index("idx_knowledge_sources_brand", "knowledge_sources", ["brand_id"])
    op.create_index("idx_knowledge_sources_expires", "knowledge_sources", ["expires_at"])

    # ─── knowledge_chunks ──────────────────────────────────────────────
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("source_id", PGUUID(as_uuid=True), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section", sa.String(200), nullable=True),
        sa.Column("embedded", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("chunk_metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_chunks_source", "knowledge_chunks", ["source_id"])
    op.create_index("idx_knowledge_chunks_workspace", "knowledge_chunks", ["workspace_id"])
    op.create_index("idx_knowledge_chunks_embedded", "knowledge_chunks", ["embedded"])

    # ─── knowledge_embeddings ──────────────────────────────────────────
    op.create_table(
        "knowledge_embeddings",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("chunk_id", PGUUID(as_uuid=True), sa.ForeignKey("knowledge_chunks.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("source_id", PGUUID(as_uuid=True), sa.ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("workspace_id", PGUUID(as_uuid=True), nullable=True, index=True),
        sa.Column("embedding", JSONB, nullable=True),
        sa.Column("embedding_dim", sa.Integer, nullable=True),
        sa.Column("embedding_model", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_embeddings_chunk", "knowledge_embeddings", ["chunk_id"])
    op.create_index("idx_knowledge_embeddings_source", "knowledge_embeddings", ["source_id"])
    op.create_index("idx_knowledge_embeddings_workspace", "knowledge_embeddings", ["workspace_id"])

    # ─── knowledge_attributions ────────────────────────────────────────
    op.create_table(
        "knowledge_attributions",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", PGUUID(as_uuid=True), nullable=False, index=True),
        sa.Column("output_type", sa.String(50), nullable=False, index=True),
        sa.Column("output_id", sa.String(100), nullable=False, index=True),
        sa.Column("source_ids", JSONB, nullable=True, server_default="[]"),
        sa.Column("chunk_ids", JSONB, nullable=True, server_default="[]"),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("relevance_scores", JSONB, nullable=True),
        sa.Column("engine", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_knowledge_attributions_output", "knowledge_attributions", ["output_type", "output_id"])
    op.create_index("idx_knowledge_attributions_engine", "knowledge_attributions", ["engine"])


def downgrade() -> None:
    op.drop_table("knowledge_attributions")
    op.drop_table("knowledge_embeddings")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_sources")
