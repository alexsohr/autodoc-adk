"""initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2026-02-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("org", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("branch_mappings", postgresql.JSONB(), nullable=False),
        sa.Column("public_branch", sa.String(), nullable=False),
        sa.Column("access_token", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
        sa.CheckConstraint("provider IN ('github', 'bitbucket')", name="ck_repositories_provider"),
    )

    # jobs table
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("branch", sa.String(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=True),
        sa.Column("force", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("dry_run", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("prefect_flow_run_id", sa.String(), nullable=True),
        sa.Column("app_commit_sha", sa.String(40), nullable=True),
        sa.Column("quality_report", postgresql.JSONB(), nullable=True),
        sa.Column("token_usage", postgresql.JSONB(), nullable=True),
        sa.Column("config_warnings", postgresql.JSONB(), nullable=True),
        sa.Column("callback_url", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pull_request_url", sa.String(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')", name="ck_jobs_status"),
        sa.CheckConstraint("mode IN ('full', 'incremental')", name="ck_jobs_mode"),
    )
    op.create_index("ix_jobs_repository_status", "jobs", ["repository_id", "status"])
    op.create_index("ix_jobs_idempotency_lookup", "jobs", ["repository_id", "branch", "dry_run", "status"])
    op.create_index(
        "uq_jobs_active_idempotency", "jobs",
        ["repository_id", "branch", "dry_run"],
        unique=True,
        postgresql_where=sa.text("status IN ('PENDING', 'RUNNING')"),
    )

    # wiki_structures table
    op.create_table(
        "wiki_structures",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("branch", sa.String(), nullable=False),
        sa.Column("scope_path", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("sections", postgresql.JSONB(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("repository_id", "branch", "scope_path", "version", name="uq_wiki_structures_scope_version"),
        sa.CheckConstraint("version >= 1", name="ck_wiki_structures_version"),
    )
    op.create_index("ix_wiki_structures_repo_branch", "wiki_structures", ["repository_id", "branch"])

    # wiki_pages table
    op.create_table(
        "wiki_pages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("wiki_structure_id", sa.Uuid(), nullable=False),
        sa.Column("page_key", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("importance", sa.String(), nullable=False),
        sa.Column("page_type", sa.String(), nullable=False),
        sa.Column("source_files", postgresql.JSONB(), nullable=False),
        sa.Column("related_pages", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["wiki_structure_id"], ["wiki_structures.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("wiki_structure_id", "page_key", name="uq_wiki_pages_structure_page_key"),
        sa.CheckConstraint("importance IN ('high', 'medium', 'low')", name="ck_wiki_pages_importance"),
        sa.CheckConstraint("page_type IN ('api', 'module', 'class', 'overview')", name="ck_wiki_pages_page_type"),
    )
    op.create_index("ix_wiki_pages_structure_id", "wiki_pages", ["wiki_structure_id"])
    op.execute("CREATE INDEX ix_wiki_pages_content_fts ON wiki_pages USING gin (to_tsvector('english', content))")

    # page_chunks table
    op.create_table(
        "page_chunks",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("wiki_page_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_embedding", Vector(3072), nullable=True),
        sa.Column("heading_path", postgresql.ARRAY(sa.String()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("heading_level", sa.Integer(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("has_code", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["wiki_page_id"], ["wiki_pages.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("wiki_page_id", "chunk_index", name="uq_page_chunks_index"),
        sa.CheckConstraint("chunk_index >= 0", name="ck_page_chunks_chunk_index"),
        sa.CheckConstraint("heading_level >= 0 AND heading_level <= 6", name="ck_page_chunks_heading_level"),
        sa.CheckConstraint("token_count >= 0", name="ck_page_chunks_token_count"),
        sa.CheckConstraint("start_char >= 0", name="ck_page_chunks_start_char"),
        sa.CheckConstraint("end_char > start_char", name="ck_page_chunks_end_char"),
    )
    op.create_index("ix_page_chunks_page_id", "page_chunks", ["wiki_page_id"])
    op.execute(
        "CREATE INDEX ix_page_chunks_embedding ON page_chunks "
        "USING hnsw ((content_embedding::halfvec(3072)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )


def downgrade() -> None:
    op.drop_table("page_chunks")
    op.drop_table("wiki_pages")
    op.drop_table("wiki_structures")
    op.drop_table("jobs")
    op.drop_table("repositories")
    op.execute("DROP EXTENSION IF EXISTS vector")
