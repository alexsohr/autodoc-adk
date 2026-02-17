from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import get_repository_repo, get_wiki_repo
from src.api.schemas.documents import ScopeInfo, ScopesResponse
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo

router = APIRouter(prefix="/documents", tags=["documents"])


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
