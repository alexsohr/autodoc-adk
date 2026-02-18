from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WikiPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        UniqueConstraint(
            "wiki_structure_id",
            "page_key",
            name="uq_wiki_pages_structure_page_key",
        ),
        CheckConstraint(
            "importance IN ('high', 'medium', 'low')",
            name="ck_wiki_pages_importance",
        ),
        CheckConstraint(
            "page_type IN ('api', 'module', 'class', 'overview')",
            name="ck_wiki_pages_page_type",
        ),
        Index("ix_wiki_pages_structure_id", "wiki_structure_id"),
        Index(
            "ix_wiki_pages_content_fts",
            text("to_tsvector('english', content)"),
            postgresql_using="gin",
        ),
    )

    wiki_structure_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("wiki_structures.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_key: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[str] = mapped_column(String, nullable=False)
    page_type: Mapped[str] = mapped_column(String, nullable=False)
    source_files: Mapped[list] = mapped_column(JSONB, nullable=False)
    related_pages: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="'[]'")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
