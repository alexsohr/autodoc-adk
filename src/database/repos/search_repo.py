"""Repository data-access object for documentation search (text, semantic, hybrid)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TextSearchResult:
    page_id: uuid.UUID
    page_key: str
    title: str
    content: str
    score: float  # ts_rank
    scope_path: str


@dataclass
class SemanticSearchResult:
    page_id: uuid.UUID
    page_key: str
    title: str
    content: str
    score: float  # cosine similarity
    best_chunk_content: str
    best_chunk_heading_path: list[str]
    scope_path: str


@dataclass
class HybridSearchResult:
    page_id: uuid.UUID
    page_key: str
    title: str
    content: str
    score: float  # RRF score
    best_chunk_content: str | None
    best_chunk_heading_path: list[str] | None
    scope_path: str


# ---------------------------------------------------------------------------
# Latest-version subquery fragment (reused across all three methods)
# ---------------------------------------------------------------------------

_LATEST_VERSION_SUBQUERY = (
    "ws.version = ("
    "  SELECT MAX(version) FROM wiki_structures"
    "  WHERE repository_id = :repo_id"
    "    AND branch = :branch"
    "    AND scope_path = ws.scope_path"
    ")"
)


# ---------------------------------------------------------------------------
# SearchRepo
# ---------------------------------------------------------------------------


class SearchRepo:
    """Async data-access layer for wiki search operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Text search
    # ------------------------------------------------------------------

    async def text_search(
        self,
        *,
        query: str,
        repository_id: uuid.UUID,
        branch: str,
        scope_path: str | None = None,
        limit: int = 10,
    ) -> list[TextSearchResult]:
        """Full-text search using PostgreSQL ts_rank on the GIN index."""

        scope_filter = "AND ws.scope_path = :scope_path" if scope_path is not None else ""

        sql = text(f"""
            SELECT
                wp.id         AS page_id,
                wp.page_key,
                wp.title,
                wp.content,
                ts_rank(
                    to_tsvector('english', wp.content),
                    plainto_tsquery('english', :query)
                ) AS score,
                ws.scope_path
            FROM wiki_pages wp
            JOIN wiki_structures ws ON wp.wiki_structure_id = ws.id
            WHERE ws.repository_id = :repo_id
              AND ws.branch = :branch
              {scope_filter}
              AND {_LATEST_VERSION_SUBQUERY}
              AND to_tsvector('english', wp.content)
                  @@ plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :limit
        """)

        params: dict = {
            "query": query,
            "repo_id": repository_id,
            "branch": branch,
            "limit": limit,
        }
        if scope_path is not None:
            params["scope_path"] = scope_path

        result = await self._session.execute(sql, params)
        return [
            TextSearchResult(
                page_id=row.page_id,
                page_key=row.page_key,
                title=row.title,
                content=row.content,
                score=row.score,
                scope_path=row.scope_path,
            )
            for row in result
        ]

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    async def semantic_search(
        self,
        *,
        query_embedding: list[float],
        repository_id: uuid.UUID,
        branch: str,
        scope_path: str | None = None,
        limit: int = 10,
        chunk_limit: int = 100,
    ) -> list[SemanticSearchResult]:
        """Cosine similarity on page_chunks with best-chunk-wins aggregation."""

        scope_filter = "AND ws.scope_path = :scope_path" if scope_path is not None else ""

        sql = text(f"""
            WITH chunk_matches AS (
                SELECT
                    pc.wiki_page_id,
                    pc.content    AS chunk_content,
                    pc.heading_path,
                    1 - (pc.content_embedding <=> :query_embedding) AS similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY pc.wiki_page_id
                        ORDER BY pc.content_embedding <=> :query_embedding
                    ) AS rn
                FROM page_chunks pc
                JOIN wiki_pages wp ON pc.wiki_page_id = wp.id
                JOIN wiki_structures ws ON wp.wiki_structure_id = ws.id
                WHERE ws.repository_id = :repo_id
                  AND ws.branch = :branch
                  {scope_filter}
                  AND {_LATEST_VERSION_SUBQUERY}
                  AND pc.content_embedding IS NOT NULL
                ORDER BY pc.content_embedding <=> :query_embedding
                LIMIT :chunk_limit
            )
            SELECT
                wp.id         AS page_id,
                wp.page_key,
                wp.title,
                wp.content,
                cm.similarity AS score,
                cm.chunk_content AS best_chunk_content,
                cm.heading_path  AS best_chunk_heading_path,
                ws.scope_path
            FROM chunk_matches cm
            JOIN wiki_pages wp ON cm.wiki_page_id = wp.id
            JOIN wiki_structures ws ON wp.wiki_structure_id = ws.id
            WHERE cm.rn = 1
            ORDER BY cm.similarity DESC
            LIMIT :limit
        """)

        params: dict = {
            "query_embedding": str(query_embedding),
            "repo_id": repository_id,
            "branch": branch,
            "chunk_limit": chunk_limit,
            "limit": limit,
        }
        if scope_path is not None:
            params["scope_path"] = scope_path

        result = await self._session.execute(sql, params)
        return [
            SemanticSearchResult(
                page_id=row.page_id,
                page_key=row.page_key,
                title=row.title,
                content=row.content,
                score=row.score,
                best_chunk_content=row.best_chunk_content,
                best_chunk_heading_path=list(row.best_chunk_heading_path),
                scope_path=row.scope_path,
            )
            for row in result
        ]

    # ------------------------------------------------------------------
    # Hybrid search (RRF)
    # ------------------------------------------------------------------

    async def hybrid_search(
        self,
        *,
        query: str,
        query_embedding: list[float],
        repository_id: uuid.UUID,
        branch: str,
        scope_path: str | None = None,
        limit: int = 10,
        chunk_limit: int = 100,
        rrf_k: int = 60,
    ) -> list[HybridSearchResult]:
        """Reciprocal Rank Fusion combining text and semantic search."""

        scope_filter = "AND ws.scope_path = :scope_path" if scope_path is not None else ""

        sql = text(f"""
            WITH semantic_chunks AS (
                SELECT
                    pc.wiki_page_id,
                    pc.content    AS chunk_content,
                    pc.heading_path,
                    1 - (pc.content_embedding <=> :query_embedding) AS similarity,
                    ROW_NUMBER() OVER (
                        PARTITION BY pc.wiki_page_id
                        ORDER BY pc.content_embedding <=> :query_embedding
                    ) AS rn
                FROM page_chunks pc
                JOIN wiki_pages wp ON pc.wiki_page_id = wp.id
                JOIN wiki_structures ws ON wp.wiki_structure_id = ws.id
                WHERE ws.repository_id = :repo_id
                  AND ws.branch = :branch
                  {scope_filter}
                  AND {_LATEST_VERSION_SUBQUERY}
                  AND pc.content_embedding IS NOT NULL
                ORDER BY pc.content_embedding <=> :query_embedding
                LIMIT :chunk_limit
            ),
            semantic_pages AS (
                SELECT
                    wiki_page_id,
                    chunk_content,
                    heading_path,
                    similarity,
                    ROW_NUMBER() OVER (ORDER BY similarity DESC) AS rank_semantic
                FROM semantic_chunks
                WHERE rn = 1
            ),
            text_results AS (
                SELECT
                    wp.id AS wiki_page_id,
                    ts_rank(
                        to_tsvector('english', wp.content),
                        plainto_tsquery('english', :query)
                    ) AS text_rank,
                    ROW_NUMBER() OVER (
                        ORDER BY ts_rank(
                            to_tsvector('english', wp.content),
                            plainto_tsquery('english', :query)
                        ) DESC
                    ) AS rank_text
                FROM wiki_pages wp
                JOIN wiki_structures ws ON wp.wiki_structure_id = ws.id
                WHERE ws.repository_id = :repo_id
                  AND ws.branch = :branch
                  {scope_filter}
                  AND {_LATEST_VERSION_SUBQUERY}
                  AND to_tsvector('english', wp.content)
                      @@ plainto_tsquery('english', :query)
            ),
            combined AS (
                SELECT
                    COALESCE(sp.wiki_page_id, tr.wiki_page_id) AS wiki_page_id,
                    sp.chunk_content  AS best_chunk_content,
                    sp.heading_path   AS best_chunk_heading_path,
                    1.0 / (:rrf_k + COALESCE(tr.rank_text, 1000))
                        + 1.0 / (:rrf_k + COALESCE(sp.rank_semantic, 1000))
                        AS rrf_score
                FROM semantic_pages sp
                FULL OUTER JOIN text_results tr
                    ON sp.wiki_page_id = tr.wiki_page_id
            )
            SELECT
                wp.id         AS page_id,
                wp.page_key,
                wp.title,
                wp.content,
                c.rrf_score   AS score,
                c.best_chunk_content,
                c.best_chunk_heading_path,
                ws.scope_path
            FROM combined c
            JOIN wiki_pages wp ON c.wiki_page_id = wp.id
            JOIN wiki_structures ws ON wp.wiki_structure_id = ws.id
            ORDER BY c.rrf_score DESC
            LIMIT :limit
        """)

        params: dict = {
            "query": query,
            "query_embedding": str(query_embedding),
            "repo_id": repository_id,
            "branch": branch,
            "chunk_limit": chunk_limit,
            "rrf_k": rrf_k,
            "limit": limit,
        }
        if scope_path is not None:
            params["scope_path"] = scope_path

        result = await self._session.execute(sql, params)
        return [
            HybridSearchResult(
                page_id=row.page_id,
                page_key=row.page_key,
                title=row.title,
                content=row.content,
                score=row.score,
                best_chunk_content=row.best_chunk_content,
                best_chunk_heading_path=(
                    list(row.best_chunk_heading_path)
                    if row.best_chunk_heading_path is not None
                    else None
                ),
                scope_path=row.scope_path,
            )
            for row in result
        ]
