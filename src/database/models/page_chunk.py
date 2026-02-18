from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, UUIDPrimaryKeyMixin


class PageChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "page_chunks"
    __table_args__ = (
        UniqueConstraint("wiki_page_id", "chunk_index", name="uq_page_chunks_index"),
        CheckConstraint("chunk_index >= 0", name="ck_page_chunks_chunk_index"),
        CheckConstraint(
            "heading_level >= 0 AND heading_level <= 6",
            name="ck_page_chunks_heading_level",
        ),
        CheckConstraint("token_count >= 0", name="ck_page_chunks_token_count"),
        CheckConstraint("start_char >= 0", name="ck_page_chunks_start_char"),
        CheckConstraint("end_char > start_char", name="ck_page_chunks_end_char"),
        Index("ix_page_chunks_page_id", "wiki_page_id"),
        # HNSW index on halfvec(3072) cast — created via migration raw SQL
        # (pgvector HNSW max 2000 dims for vector, 4000 for halfvec)
    )

    wiki_page_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wiki_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_embedding = mapped_column(Vector(3072), nullable=True)
    heading_path: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    heading_level: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    has_code: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
