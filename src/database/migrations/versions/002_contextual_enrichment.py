"""contextual enrichment — dimension reduction, context_prefix, chunk-level BM25

Revision ID: 002
Revises: 001
Create Date: 2026-03-14
"""

from collections.abc import Sequence

from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Invalidate old 3072-dim embeddings
    op.execute("UPDATE page_chunks SET content_embedding = NULL")

    # 2. Drop old halfvec HNSW index
    op.execute("DROP INDEX IF EXISTS ix_page_chunks_embedding")

    # 3. Change embedding dimension
    op.execute("ALTER TABLE page_chunks ALTER COLUMN content_embedding TYPE vector(1024)")

    # 4. Add context_prefix column
    op.execute("ALTER TABLE page_chunks ADD COLUMN context_prefix TEXT")

    # 5. Add search_vector as generated column (contextual BM25)
    op.execute(
        "ALTER TABLE page_chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS ("
        "  to_tsvector('english', coalesce(context_prefix, '') || ' ' || content)"
        ") STORED"
    )

    # 6. Create indexes
    op.execute(
        "CREATE INDEX ix_page_chunks_content_embedding ON page_chunks "
        "USING hnsw (content_embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute(
        "CREATE INDEX ix_page_chunks_search_vector ON page_chunks "
        "USING gin (search_vector)"
    )


def downgrade() -> None:
    # Drop new indexes
    op.execute("DROP INDEX IF EXISTS ix_page_chunks_search_vector")
    op.execute("DROP INDEX IF EXISTS ix_page_chunks_content_embedding")

    # Drop generated column
    op.execute("ALTER TABLE page_chunks DROP COLUMN IF EXISTS search_vector")

    # Drop context_prefix
    op.execute("ALTER TABLE page_chunks DROP COLUMN IF EXISTS context_prefix")

    # Invalidate embeddings before dimension change
    op.execute("UPDATE page_chunks SET content_embedding = NULL")

    # Restore original dimension
    op.execute("ALTER TABLE page_chunks ALTER COLUMN content_embedding TYPE vector(3072)")

    # Recreate original halfvec HNSW index
    op.execute(
        "CREATE INDEX ix_page_chunks_embedding ON page_chunks "
        "USING hnsw ((content_embedding::halfvec(3072)) halfvec_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
