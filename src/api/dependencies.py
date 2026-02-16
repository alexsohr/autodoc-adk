from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.engine import get_session_factory
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session, committing on success or rolling back on error."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_repository_repo(
    session: AsyncSession = Depends(get_db_session),
) -> RepositoryRepo:
    """Provide a RepositoryRepo instance."""
    return RepositoryRepo(session)


async def get_job_repo(
    session: AsyncSession = Depends(get_db_session),
) -> JobRepo:
    """Provide a JobRepo instance."""
    return JobRepo(session)


async def get_wiki_repo(
    session: AsyncSession = Depends(get_db_session),
) -> WikiRepo:
    """Provide a WikiRepo instance."""
    return WikiRepo(session)
