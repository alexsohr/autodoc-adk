"""FastMCP server exposing find_repository and query_documents tools.

A standalone MCP server for external AI agents to discover registered
repositories and search their generated documentation.  No ADK dependency —
only ``fastmcp`` and the application database layer.

Run via stdio (default)::

    python -m src.mcp_server

Or import the ``mcp`` instance for programmatic use.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

import sqlalchemy as sa
from fastmcp import Context, FastMCP

from src.database.engine import dispose_engine, get_session_factory
from src.database.models.repository import Repository
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.search_repo import SearchRepo
from src.errors import PermanentError
from src.services.search import search_documents

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — initialise DB session factory, clean up on shutdown
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(server: FastMCP):
    session_factory = get_session_factory()
    yield {"session_factory": session_factory}
    await dispose_engine()


mcp = FastMCP("autodoc", lifespan=_lifespan)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool
async def find_repository(
    search: str,
    ctx: Context,
) -> dict[str, Any]:
    """Find registered repositories by name, URL, or partial match.

    Args:
        search: Search term to match against repository name, URL,
                or organisation.  Supports partial/substring matching.

    Returns:
        A dict with a ``repositories`` key containing matching
        repositories, each with id, name, provider, url, and branches.
    """
    session_factory = ctx.request_context.lifespan_context["session_factory"]
    async with session_factory() as session:
        pattern = f"%{search}%"
        stmt = (
            sa.select(Repository)
            .where(
                sa.or_(
                    Repository.name.ilike(pattern),
                    Repository.url.ilike(pattern),
                    Repository.org.ilike(pattern),
                )
            )
            .order_by(Repository.name)
            .limit(20)
        )
        result = await session.execute(stmt)
        repos = list(result.scalars().all())

    return {
        "repositories": [
            {
                "id": str(repo.id),
                "name": repo.name,
                "provider": repo.provider,
                "url": repo.url,
                "branches": list(repo.branch_mappings.keys()),
            }
            for repo in repos
        ],
    }


@mcp.tool
async def query_documents(
    repository_id: str,
    query: str,
    search_type: str = "hybrid",
    limit: int = 10,
    ctx: Context = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Search documentation for a registered repository.

    Use ``find_repository`` first to obtain a valid *repository_id*.

    Args:
        repository_id: UUID of the target repository (from find_repository).
        query: Natural language search query.
        search_type: One of "text", "semantic", or "hybrid" (default).
        limit: Maximum number of results to return (default 10).

    Returns:
        Ranked search results with page key, title, snippet, score,
        and optional chunk-level context.
    """
    try:
        repo_uuid = uuid.UUID(repository_id)
    except ValueError:
        return {"error": f"Invalid repository_id: {repository_id}"}

    session_factory = ctx.request_context.lifespan_context["session_factory"]
    async with session_factory() as session:
        repo_repo = RepositoryRepo(session)
        repo = await repo_repo.get_by_id(repo_uuid)
        if repo is None:
            return {"error": f"Repository not found: {repository_id}"}

        search_repo = SearchRepo(session)
        try:
            response = await search_documents(
                query=query,
                search_type=search_type,
                repository_id=repo_uuid,
                branch=repo.public_branch,
                search_repo=search_repo,
                limit=limit,
            )
        except PermanentError as exc:
            return {"error": str(exc)}

    return {
        "results": [
            {
                "page_key": r.page_key,
                "title": r.title,
                "snippet": r.snippet,
                "score": r.score,
                "best_chunk_content": r.best_chunk_content,
                "best_chunk_heading_path": r.best_chunk_heading_path,
                "scope_path": r.scope_path,
            }
            for r in response.results
        ],
        "total": response.total,
        "search_type": response.search_type,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
