from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import get_repository_repo
from src.api.schemas.repositories import (
    PaginatedRepositoryResponse,
    RegisterRepositoryRequest,
    RepositoryResponse,
    UpdateRepositoryRequest,
)
from src.database.repos.repository_repo import RepositoryRepo

router = APIRouter(tags=["repositories"])

_PROVIDER_HOSTS = {
    "github": "github.com",
    "bitbucket": "bitbucket.org",
}


def _parse_org_name(url: str, provider: str) -> tuple[str, str]:
    """Extract org and repository name from a provider URL."""
    parsed = urlparse(url)
    expected_host = _PROVIDER_HOSTS.get(provider)
    if expected_host and parsed.hostname != expected_host:
        raise HTTPException(
            status_code=422,
            detail=f"URL host must be {expected_host} for provider '{provider}'",
        )
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise HTTPException(
            status_code=422,
            detail="URL must contain /{org}/{name}",
        )
    return parts[0], parts[1].removesuffix(".git")


@router.post(
    "/repositories",
    response_model=RepositoryResponse,
    status_code=201,
)
async def register_repository(
    body: RegisterRepositoryRequest,
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> RepositoryResponse:
    org, name = _parse_org_name(body.url, body.provider)
    try:
        row = await repo.create(
            provider=body.provider,
            url=body.url,
            org=org,
            name=name,
            branch_mappings=body.branch_mappings,
            public_branch=body.public_branch,
            access_token=body.access_token,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="Repository URL already registered"
        ) from exc
    return RepositoryResponse.model_validate(row)


@router.get(
    "/repositories",
    response_model=PaginatedRepositoryResponse,
)
async def list_repositories(
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> PaginatedRepositoryResponse:
    rows = await repo.list(cursor=cursor, limit=limit)
    next_cursor = str(rows[-1].id) if len(rows) == limit else None
    return PaginatedRepositoryResponse(
        items=[RepositoryResponse.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        limit=limit,
    )


@router.get(
    "/repositories/{repository_id}",
    response_model=RepositoryResponse,
)
async def get_repository(
    repository_id: UUID,
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> RepositoryResponse:
    row = await repo.get_by_id(repository_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryResponse.model_validate(row)


@router.patch(
    "/repositories/{repository_id}",
    response_model=RepositoryResponse,
)
async def update_repository(
    repository_id: UUID,
    body: UpdateRepositoryRequest,
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> RepositoryResponse:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No fields to update")

    # Validate public_branch against branch_mappings
    if "public_branch" in updates:
        new_public = updates["public_branch"]
        if "branch_mappings" in updates:
            valid_branches = updates["branch_mappings"]
        else:
            existing = await repo.get_by_id(repository_id)
            if existing is None:
                raise HTTPException(status_code=404, detail="Repository not found")
            valid_branches = existing.branch_mappings
        if new_public not in valid_branches:
            raise HTTPException(
                status_code=422,
                detail=f"public_branch '{new_public}' must be a key in branch_mappings",
            )

    row = await repo.update(repository_id, **updates)
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return RepositoryResponse.model_validate(row)


@router.delete(
    "/repositories/{repository_id}",
    status_code=204,
)
async def delete_repository(
    repository_id: UUID,
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> Response:
    deleted = await repo.delete(repository_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Repository not found")
    return Response(status_code=204)
