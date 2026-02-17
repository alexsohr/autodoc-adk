"""Search orchestrator service.

Accepts search parameters, generates query embeddings when needed,
delegates to :class:`SearchRepo`, and formats results with snippets.
"""

from __future__ import annotations

import logging
import re
import uuid

from src.api.schemas.documents import SearchResponse, SearchResult
from src.database.repos.search_repo import (
    HybridSearchResult,
    SearchRepo,
    SemanticSearchResult,
    TextSearchResult,
)
from src.errors import PermanentError
from src.services.embedding import embed_query

logger = logging.getLogger(__name__)

_VALID_SEARCH_TYPES = {"text", "semantic", "hybrid"}

# Regex to strip leading markdown heading markers (e.g. "## Title\n")
_HEADING_RE = re.compile(r"^#{1,6}\s+")


# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------


def _extract_snippet(content: str, max_length: int = 200) -> str:
    """Return a short plain-text snippet from *content*.

    * Strips leading markdown heading markers.
    * Truncates to approximately *max_length* characters at a word boundary.
    * Appends ``"..."`` when the text was truncated.
    """
    if not content:
        return ""

    # Strip leading heading markers (first line only).
    text = _HEADING_RE.sub("", content, count=1)

    if len(text) <= max_length:
        return text.strip()

    truncated = text[:max_length]

    # Find the last space so we don't cut in the middle of a word.
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]

    return truncated.strip() + "..."


# ---------------------------------------------------------------------------
# Result mapping helpers
# ---------------------------------------------------------------------------


def _map_text_result(row: TextSearchResult) -> SearchResult:
    return SearchResult(
        page_key=row.page_key,
        title=row.title,
        snippet=_extract_snippet(row.content),
        score=row.score,
        scope_path=row.scope_path,
    )


def _map_semantic_result(row: SemanticSearchResult) -> SearchResult:
    return SearchResult(
        page_key=row.page_key,
        title=row.title,
        snippet=_extract_snippet(row.content),
        score=row.score,
        best_chunk_content=row.best_chunk_content,
        best_chunk_heading_path=row.best_chunk_heading_path,
        scope_path=row.scope_path,
    )


def _map_hybrid_result(row: HybridSearchResult) -> SearchResult:
    return SearchResult(
        page_key=row.page_key,
        title=row.title,
        snippet=_extract_snippet(row.content),
        score=row.score,
        best_chunk_content=row.best_chunk_content,
        best_chunk_heading_path=row.best_chunk_heading_path,
        scope_path=row.scope_path,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def search_documents(
    *,
    query: str,
    search_type: str,
    repository_id: uuid.UUID,
    branch: str,
    scope: str | None = None,
    limit: int = 10,
    search_repo: SearchRepo,
) -> SearchResponse:
    """Execute a documentation search and return formatted results.

    Args:
        query: The user's search query string.
        search_type: One of ``"text"``, ``"semantic"``, or ``"hybrid"``.
        repository_id: Target repository UUID.
        branch: Git branch to search within.
        scope: Optional scope path to restrict results.
        limit: Maximum number of results to return.
        search_repo: Data-access object for search queries.

    Returns:
        A :class:`SearchResponse` containing scored, snippet-enriched results.

    Raises:
        PermanentError: If *search_type* is not a recognised value.
    """
    if search_type not in _VALID_SEARCH_TYPES:
        raise PermanentError(
            f"Invalid search_type '{search_type}'. "
            f"Must be one of: {', '.join(sorted(_VALID_SEARCH_TYPES))}"
        )

    logger.info(
        "Searching documents: type=%s repo=%s branch=%s scope=%s limit=%d",
        search_type,
        repository_id,
        branch,
        scope,
        limit,
    )

    results: list[SearchResult]

    if search_type == "text":
        rows = await search_repo.text_search(
            query=query,
            repository_id=repository_id,
            branch=branch,
            scope_path=scope,
            limit=limit,
        )
        results = [_map_text_result(r) for r in rows]

    elif search_type == "semantic":
        query_embedding = await embed_query(query)
        rows = await search_repo.semantic_search(
            query_embedding=query_embedding,
            repository_id=repository_id,
            branch=branch,
            scope_path=scope,
            limit=limit,
        )
        results = [_map_semantic_result(r) for r in rows]

    else:  # hybrid
        query_embedding = await embed_query(query)
        rows = await search_repo.hybrid_search(
            query=query,
            query_embedding=query_embedding,
            repository_id=repository_id,
            branch=branch,
            scope_path=scope,
            limit=limit,
        )
        results = [_map_hybrid_result(r) for r in rows]

    logger.info("Search returned %d results", len(results))

    return SearchResponse(
        results=results,
        total=len(results),
        search_type=search_type,
    )
