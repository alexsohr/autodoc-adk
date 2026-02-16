"""Repository data-access object for the repositories table."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.repository import Repository


class RepositoryRepo:
    """Async data-access layer for :class:`Repository` rows."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        provider: str,
        url: str,
        org: str,
        name: str,
        branch_mappings: dict,
        public_branch: str,
        access_token: str | None = None,
    ) -> Repository:
        """Create and return a new Repository."""
        repo = Repository(
            provider=provider,
            url=url,
            org=org,
            name=name,
            branch_mappings=branch_mappings,
            public_branch=public_branch,
            access_token=access_token,
        )
        self._session.add(repo)
        await self._session.flush()
        return repo

    async def get_by_id(self, repository_id: uuid.UUID) -> Repository | None:
        """Return a Repository by primary key, or ``None``."""
        return await self._session.get(Repository, repository_id)

    async def get_by_url(self, url: str) -> Repository | None:
        """Return the first Repository matching *url*, or ``None``."""
        stmt = sa.select(Repository).where(Repository.url == url)
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        *,
        cursor: uuid.UUID | None = None,
        limit: int = 20,
    ) -> list[Repository]:
        """Return repositories with cursor-based pagination (newest first)."""
        stmt = sa.select(Repository).order_by(
            Repository.created_at.desc(),
            Repository.id.desc(),
        )
        if cursor is not None:
            cursor_row = await self._session.get(Repository, cursor)
            if cursor_row is not None:
                stmt = stmt.where(
                    sa.or_(
                        Repository.created_at < cursor_row.created_at,
                        sa.and_(
                            Repository.created_at == cursor_row.created_at,
                            Repository.id < cursor,
                        ),
                    )
                )
        stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self, repository_id: uuid.UUID, **kwargs: object
    ) -> Repository | None:
        """Update arbitrary fields on a Repository. Returns ``None`` if not found."""
        repo = await self._session.get(Repository, repository_id)
        if repo is None:
            return None
        for key, value in kwargs.items():
            setattr(repo, key, value)
        await self._session.flush()
        return repo

    async def delete(self, repository_id: uuid.UUID) -> bool:
        """Delete a Repository by id. Returns ``True`` if deleted, ``False`` otherwise."""
        repo = await self._session.get(Repository, repository_id)
        if repo is None:
            return False
        await self._session.delete(repo)
        await self._session.flush()
        return True
