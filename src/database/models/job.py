from __future__ import annotations

import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "mode IN ('full', 'incremental')",
            name="ck_jobs_mode",
        ),
        Index("ix_jobs_repository_status", "repository_id", "status"),
        Index("ix_jobs_idempotency_lookup", "repository_id", "branch", "dry_run", "status"),
        Index(
            "uq_jobs_active_idempotency",
            "repository_id",
            "branch",
            "dry_run",
            unique=True,
            postgresql_where=text("status IN ('PENDING', 'RUNNING')"),
        ),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    branch: Mapped[str] = mapped_column(String, nullable=False)
    commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    force: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    prefect_flow_run_id: Mapped[str | None] = mapped_column(String, nullable=True)
    app_commit_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quality_report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    config_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    callback_url: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    pull_request_url: Mapped[str | None] = mapped_column(String, nullable=True)
