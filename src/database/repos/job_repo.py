"""Repository data-access object for the jobs table."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.job import Job
from src.errors import PermanentError

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"RUNNING", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "CANCELLED"},
    "FAILED": {"PENDING"},
}


class JobRepo:
    """Async data-access layer for :class:`Job` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        repository_id: uuid.UUID,
        status: str,
        mode: str,
        branch: str,
        force: bool = False,
        dry_run: bool = False,
        app_commit_sha: str | None = None,
        callback_url: str | None = None,
    ) -> Job:
        """Create and return a new Job."""
        job = Job(
            repository_id=repository_id,
            status=status,
            mode=mode,
            branch=branch,
            force=force,
            dry_run=dry_run,
            app_commit_sha=app_commit_sha,
            callback_url=callback_url,
        )
        self._session.add(job)
        await self._session.flush()
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        """Return a Job by primary key, or ``None``."""
        return await self._session.get(Job, job_id)

    async def list(
        self,
        *,
        repository_id: uuid.UUID | None = None,
        status: str | None = None,
        branch: str | None = None,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[Job]:
        """Return jobs with optional filters and cursor-based pagination."""
        stmt = sa.select(Job).order_by(
            Job.created_at.desc(),
            Job.id.desc(),
        )
        if repository_id is not None:
            stmt = stmt.where(Job.repository_id == repository_id)
        if status is not None:
            stmt = stmt.where(Job.status == status)
        if branch is not None:
            stmt = stmt.where(Job.branch == branch)
        if cursor is not None:
            cursor_row = await self._session.get(Job, cursor)
            if cursor_row is not None:
                stmt = stmt.where(
                    sa.or_(
                        Job.created_at < cursor_row.created_at,
                        sa.and_(
                            Job.created_at == cursor_row.created_at,
                            Job.id < cursor,
                        ),
                    )
                )
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
        self, job_id: uuid.UUID, status: str, **kwargs: object
    ) -> Job | None:
        """Transition a job to a new status.

        Raises :class:`PermanentError` if the transition is invalid.
        Returns ``None`` if the job does not exist.
        """
        job = await self._session.get(Job, job_id)
        if job is None:
            return None

        allowed = _VALID_TRANSITIONS.get(job.status, set())
        if status not in allowed:
            raise PermanentError(
                f"Invalid status transition: {job.status} -> {status}"
            )

        job.status = status
        for key, value in kwargs.items():
            setattr(job, key, value)
        await self._session.flush()
        return job

    async def get_active_for_repo(
        self,
        repository_id: uuid.UUID,
        branch: str,
        dry_run: bool = False,
    ) -> Job | None:
        """Find an active (PENDING/RUNNING) job for idempotency checks."""
        stmt = (
            sa.select(Job)
            .where(
                Job.repository_id == repository_id,
                Job.branch == branch,
                Job.dry_run == dry_run,
                Job.status.in_(["PENDING", "RUNNING"]),
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_running_jobs(self) -> list[Job]:
        """Return all jobs currently in RUNNING status."""
        stmt = sa.select(Job).where(Job.status == "RUNNING")
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
