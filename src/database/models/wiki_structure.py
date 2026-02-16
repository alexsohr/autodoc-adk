from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WikiStructure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wiki_structures"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "branch",
            "scope_path",
            "version",
            name="uq_wiki_structures_scope_version",
        ),
        CheckConstraint("version >= 1", name="ck_wiki_structures_version"),
        Index("ix_wiki_structures_repo_branch", "repository_id", "branch"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    branch: Mapped[str] = mapped_column(String, nullable=False)
    scope_path: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[dict] = mapped_column(JSONB, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
