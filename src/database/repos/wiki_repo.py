"""Repository data-access object for wiki structures, pages, and chunks."""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.page_chunk import PageChunk
from src.database.models.wiki_page import WikiPage
from src.database.models.wiki_structure import WikiStructure


class WikiRepo:
    """Async data-access layer for wiki-related tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_structure(
        self,
        *,
        repository_id: uuid.UUID,
        job_id: uuid.UUID | None,
        branch: str,
        scope_path: str,
        title: str,
        description: str,
        sections: dict,
        commit_sha: str,
    ) -> WikiStructure:
        """Create a new WikiStructure with automatic version management.

        At most 3 versions are retained per (repository_id, branch, scope_path).
        If 3 already exist the oldest (lowest version number) is deleted before
        inserting the new row.
        """
        # Fetch existing versions for this scope, ordered oldest-first.
        existing_stmt = (
            sa.select(WikiStructure)
            .where(
                WikiStructure.repository_id == repository_id,
                WikiStructure.branch == branch,
                WikiStructure.scope_path == scope_path,
            )
            .order_by(WikiStructure.version.asc())
        )
        result = await self._session.execute(existing_stmt)
        existing: list[WikiStructure] = list(result.scalars().all())

        # Determine next version number.
        next_version = existing[-1].version + 1 if existing else 1

        # Enforce the 3-version retention cap.
        if len(existing) >= 3:
            await self._session.delete(existing[0])

        structure = WikiStructure(
            repository_id=repository_id,
            job_id=job_id,
            branch=branch,
            scope_path=scope_path,
            version=next_version,
            title=title,
            description=description,
            sections=sections,
            commit_sha=commit_sha,
        )
        self._session.add(structure)
        await self._session.flush()
        return structure

    async def create_pages(self, pages: list[WikiPage]) -> list[WikiPage]:
        """Batch-insert wiki pages and return them with populated defaults."""
        self._session.add_all(pages)
        await self._session.flush()
        return pages

    async def create_chunks(self, chunks: list[PageChunk]) -> list[PageChunk]:
        """Batch-insert page chunks and return them with populated defaults."""
        self._session.add_all(chunks)
        await self._session.flush()
        return chunks

    async def get_latest_structure(
        self,
        repository_id: uuid.UUID,
        branch: str,
        scope_path: str = ".",
    ) -> WikiStructure | None:
        """Return the structure with the highest version for a given scope."""
        stmt = (
            sa.select(WikiStructure)
            .where(
                WikiStructure.repository_id == repository_id,
                WikiStructure.branch == branch,
                WikiStructure.scope_path == scope_path,
            )
            .order_by(WikiStructure.version.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_page_by_key(
        self,
        wiki_structure_id: uuid.UUID,
        page_key: str,
    ) -> WikiPage | None:
        """Return a single WikiPage by structure id and page_key."""
        stmt = sa.select(WikiPage).where(
            WikiPage.wiki_structure_id == wiki_structure_id,
            WikiPage.page_key == page_key,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_structures_for_repo(
        self,
        repository_id: uuid.UUID,
        branch: str | None = None,
    ) -> list[WikiStructure]:
        """Return all structures for a repository, optionally filtered by branch."""
        stmt = (
            sa.select(WikiStructure)
            .where(WikiStructure.repository_id == repository_id)
            .order_by(WikiStructure.scope_path.asc(), WikiStructure.version.asc())
        )
        if branch is not None:
            stmt = stmt.where(WikiStructure.branch == branch)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
