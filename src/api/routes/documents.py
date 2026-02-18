from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_repository_repo, get_search_repo, get_wiki_repo
from src.api.schemas.documents import (
    PaginatedWikiResponse,
    ScopeInfo,
    ScopesResponse,
    SearchResponse,
    WikiPageResponse,
    WikiPageSummary,
    WikiSection,
)
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.search_repo import SearchRepo
from src.database.repos.wiki_repo import WikiRepo
from src.services.search import search_documents

router = APIRouter(prefix="/documents", tags=["documents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_section(data: dict) -> WikiSection:
    """Recursively parse a raw section dict into a WikiSection schema object."""
    pages = [
        WikiPageSummary(
            page_key=p.get("page_key", ""),
            title=p.get("title", ""),
            description=p.get("description"),
            importance=p.get("importance", "medium"),
            page_type=p.get("page_type", "overview"),
        )
        for p in data.get("pages", [])
    ]
    subsections = [_parse_section(s) for s in data.get("subsections", [])]
    return WikiSection(
        title=data.get("title", ""),
        description=data.get("description"),
        pages=pages,
        subsections=subsections,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{repository_id}/scopes", response_model=ScopesResponse)
async def list_scopes(
    repository_id: uuid.UUID,
    branch: str | None = Query(default=None, description="Branch name (defaults to public_branch)"),
    repo_repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> ScopesResponse:
    """List documentation scopes for a repository.

    Returns all scopes discovered for the repository on the given branch.
    Each scope corresponds to a .autodoc.yaml file found in the repository.
    """
    # Verify repository exists
    repository = await repo_repo.get_by_id(repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Default to public_branch if not specified
    target_branch = branch or repository.public_branch

    # Get all structures for this repo+branch (each has a unique scope_path)
    structures = await wiki_repo.get_structures_for_repo(
        repository_id=repository_id,
        branch=target_branch,
    )

    # Build scope info from latest structure per scope_path.
    # get_structures_for_repo returns all versions ordered by
    # (scope_path ASC, version ASC), so the last entry per scope_path
    # is the latest version.
    latest_by_scope: dict[str, object] = {}
    for structure in structures:
        latest_by_scope[structure.scope_path] = structure

    scopes: list[ScopeInfo] = []
    for structure in latest_by_scope.values():
        # Count pages for this structure
        page_count = await wiki_repo.count_pages_for_structure(structure.id)
        scopes.append(
            ScopeInfo(
                scope_path=structure.scope_path,
                title=structure.title,
                description=structure.description,
                page_count=page_count,
            )
        )

    return ScopesResponse(scopes=scopes)


@router.get("/{repository_id}/search", response_model=SearchResponse)
async def search_wiki(
    repository_id: uuid.UUID,
    query: str = Query(description="Search query string"),
    search_type: str = Query(default="hybrid", description="Search type: text, semantic, or hybrid"),
    branch: str | None = Query(default=None, description="Branch name (defaults to public_branch)"),
    scope: str | None = Query(default=None, description="Scope path to restrict results"),
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of results"),
    repo_repo: RepositoryRepo = Depends(get_repository_repo),
    search_repo: SearchRepo = Depends(get_search_repo),
) -> SearchResponse:
    """Search wiki pages using text, semantic, or hybrid search.

    Delegates to the search orchestrator service which handles embedding
    generation (for semantic/hybrid) and result formatting.
    """
    repository = await repo_repo.get_by_id(repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    target_branch = branch or repository.public_branch

    return await search_documents(
        query=query,
        search_type=search_type,
        repository_id=repository_id,
        branch=target_branch,
        scope=scope,
        limit=limit,
        search_repo=search_repo,
    )


@router.get("/{repository_id}/pages/{page_key:path}", response_model=WikiPageResponse)
async def get_page(
    repository_id: uuid.UUID,
    page_key: str,
    branch: str | None = Query(default=None, description="Branch name (defaults to public_branch)"),
    scope: str = Query(default=".", description="Scope path"),
    repo_repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> WikiPageResponse:
    """Get a single wiki page by its page key.

    Returns full page content, metadata, and quality score.
    """
    repository = await repo_repo.get_by_id(repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    target_branch = branch or repository.public_branch

    structure = await wiki_repo.get_latest_structure(
        repository_id=repository_id,
        branch=target_branch,
        scope_path=scope,
    )
    if structure is None:
        raise HTTPException(status_code=404, detail="No wiki found for this repository/branch/scope")

    page = await wiki_repo.get_page_by_key(
        wiki_structure_id=structure.id,
        page_key=page_key,
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    return WikiPageResponse(
        page_key=page.page_key,
        title=page.title,
        description=page.description,
        importance=page.importance,
        page_type=page.page_type,
        content=page.content,
        source_files=page.source_files,
        related_pages=page.related_pages,
        quality_score=page.quality_score,
    )


@router.get("/{repository_id}", response_model=PaginatedWikiResponse)
async def get_wiki(
    repository_id: uuid.UUID,
    branch: str | None = Query(default=None, description="Branch name (defaults to public_branch)"),
    scope: str = Query(default=".", description="Scope path"),
    cursor: str | None = Query(default=None, description="Pagination cursor (integer index)"),
    limit: int = Query(default=20, ge=1, le=100, description="Number of sections per page"),
    repo_repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> PaginatedWikiResponse:
    """Get the structured wiki for a repository.

    Returns top-level sections of the wiki structure with cursor-based
    pagination. Each section may contain pages and nested subsections.
    """
    repository = await repo_repo.get_by_id(repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    target_branch = branch or repository.public_branch

    structure = await wiki_repo.get_latest_structure(
        repository_id=repository_id,
        branch=target_branch,
        scope_path=scope,
    )
    if structure is None:
        raise HTTPException(status_code=404, detail="No wiki found for this repository/branch/scope")

    # Parse sections from the stored JSON structure.
    raw_sections = structure.sections.get("sections", [])
    all_sections = [_parse_section(s) for s in raw_sections]

    # Apply cursor-based pagination on top-level sections.
    start_index = 0
    if cursor is not None:
        try:
            start_index = int(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor value") from None

    end_index = start_index + limit
    page_sections = all_sections[start_index:end_index]

    next_cursor: str | None = None
    if end_index < len(all_sections):
        next_cursor = str(end_index)

    return PaginatedWikiResponse(
        items=page_sections,
        next_cursor=next_cursor,
        limit=limit,
    )
