from __future__ import annotations

from pydantic import BaseModel


class ScopeInfo(BaseModel):
    """Information about a documentation scope."""

    scope_path: str
    title: str | None = None
    description: str | None = None
    page_count: int = 0


class ScopesResponse(BaseModel):
    """Response for the list scopes endpoint."""

    scopes: list[ScopeInfo]


class WikiPageSummary(BaseModel):
    """Summary of a wiki page within a structure section."""

    page_key: str
    title: str
    description: str | None = None
    importance: str  # high | medium | low
    page_type: str  # api | module | class | overview


class WikiSection(BaseModel):
    """A section in the wiki structure, possibly containing nested subsections."""

    title: str
    description: str | None = None
    pages: list[WikiPageSummary] = []
    subsections: list[WikiSection] = []  # recursive


WikiSection.model_rebuild()


class WikiPageResponse(BaseModel):
    """Full wiki page content and metadata."""

    page_key: str
    title: str
    description: str | None = None
    importance: str
    page_type: str
    content: str
    source_files: list[str] = []
    related_pages: list[str] = []
    quality_score: float | None = None


class PaginatedWikiResponse(BaseModel):
    """Paginated response for wiki structure sections."""

    items: list[WikiSection] = []
    next_cursor: str | None = None
    limit: int = 20


class SearchResult(BaseModel):
    """A single search result with relevance scoring."""

    page_key: str
    title: str
    snippet: str
    score: float
    best_chunk_content: str | None = None
    best_chunk_heading_path: list[str] | None = None
    scope_path: str | None = None


class SearchResponse(BaseModel):
    """Response for the search endpoint."""

    results: list[SearchResult]
    total: int
    search_type: str  # text | semantic | hybrid
