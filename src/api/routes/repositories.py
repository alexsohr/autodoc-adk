from __future__ import annotations

from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, Response
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo
from src.api.schemas.repositories import (
    PaginatedRepositoryResponse,
    RegisterRepositoryRequest,
    RepositoryResponse,
    UpdateRepositoryRequest,
)
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo

router = APIRouter(tags=["repositories"])

_JOB_STATUS_MAP: dict[str, str] = {
    "RUNNING": "running",
    "FAILED": "failed",
    "COMPLETED": "healthy",
    "PENDING": "running",
    "CANCELLED": "failed",
}


async def _enrich_repository_response(
    row: object,
    job_repo: JobRepo,
    wiki_repo: WikiRepo,
) -> RepositoryResponse:
    """Build a RepositoryResponse with computed fields from jobs and wiki data."""
    repo_id = row.id

    # Latest job → status + last_generated_at
    jobs = await job_repo.list(repository_id=repo_id, limit=1)
    if jobs:
        latest = jobs[0]
        status = _JOB_STATUS_MAP.get(latest.status, "pending")
        last_generated_at = latest.updated_at if latest.status == "COMPLETED" else None
    else:
        status = "pending"
        last_generated_at = None

    # Scope/page counts from wiki structures
    structures = await wiki_repo.get_structures_for_repo(
        repository_id=repo_id,
        branch=row.public_branch,
    )
    # De-duplicate by scope_path (keep latest)
    latest_by_scope: dict[str, object] = {}
    for s in structures:
        latest_by_scope[s.scope_path] = s

    scope_count = len(latest_by_scope)
    total_pages = 0
    quality_sum = 0.0
    quality_count = 0

    for structure in latest_by_scope.values():
        pages = await wiki_repo.get_pages_for_structure(structure.id)
        total_pages += len(pages)
        for page in pages:
            if page.quality_score is not None:
                quality_sum += page.quality_score
                quality_count += 1

    avg_quality_score = round(quality_sum / quality_count, 2) if quality_count > 0 else None

    resp = RepositoryResponse.model_validate(row)
    resp.default_branch = row.public_branch
    resp.status = status
    resp.page_count = total_pages
    resp.scope_count = scope_count
    resp.avg_quality_score = avg_quality_score
    resp.last_generated_at = last_generated_at
    return resp

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
    summary="Register a repository",
    description=(
        "Register a new repository for documentation generation. "
        "The URL must match the provider host (github.com for GitHub, "
        "bitbucket.org for Bitbucket). The public_branch must be one of "
        "the keys in branch_mappings."
    ),
    responses={
        409: {
            "description": "Repository URL already registered",
            "content": {
                "application/json": {
                    "example": {"detail": "Repository URL already registered"},
                },
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "URL host must be github.com for provider 'github'",
                    },
                },
            },
        },
    },
)
async def register_repository(
    body: RegisterRepositoryRequest = Body(
        openapi_examples={
            "github_private": {
                "summary": "GitHub private repository",
                "value": {
                    "url": "https://github.com/acme-corp/backend-api",
                    "provider": "github",
                    "branch_mappings": {
                        "main": "production",
                        "develop": "staging",
                    },
                    "public_branch": "main",
                    "access_token": "ghp_a1b2c3d4e5f6g7h8i9j0kLmNoPqRsTuVwXyZ",
                },
            },
            "bitbucket_public": {
                "summary": "Bitbucket public repository",
                "value": {
                    "url": "https://bitbucket.org/acme-corp/frontend-app",
                    "provider": "bitbucket",
                    "branch_mappings": {
                        "master": "latest",
                    },
                    "public_branch": "master",
                    "access_token": None,
                },
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
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
    return await _enrich_repository_response(row, job_repo, wiki_repo)


@router.get(
    "/repositories",
    response_model=PaginatedRepositoryResponse,
    summary="List repositories",
    description=(
        "Return a paginated list of registered repositories. "
        "Use cursor-based pagination by passing the next_cursor value "
        "from the previous response as the cursor parameter."
    ),
)
async def list_repositories(
    cursor: UUID | None = Query(
        None,
        description="UUID of the last item from the previous page. Omit for the first page.",
        openapi_examples={
            "first_page": {
                "summary": "First page (no cursor)",
                "value": None,
            },
            "next_page": {
                "summary": "Fetch next page",
                "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
        },
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of repositories to return per page.",
        openapi_examples={
            "default": {
                "summary": "Default page size",
                "value": 20,
            },
            "small": {
                "summary": "Small page",
                "value": 5,
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> PaginatedRepositoryResponse:
    rows = await repo.list(cursor=cursor, limit=limit)
    next_cursor = str(rows[-1].id) if len(rows) == limit else None
    items = [await _enrich_repository_response(r, job_repo, wiki_repo) for r in rows]
    return PaginatedRepositoryResponse(
        items=items,
        next_cursor=next_cursor,
        limit=limit,
    )


@router.get(
    "/repositories/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get a repository",
    description="Retrieve details of a single registered repository by its unique identifier.",
    responses={
        404: {
            "description": "Repository not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Repository not found"},
                },
            },
        },
    },
)
async def get_repository(
    repository_id: UUID = Path(
        description="Unique identifier of the repository.",
        openapi_examples={
            "example": {
                "summary": "Repository UUID",
                "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> RepositoryResponse:
    row = await repo.get_by_id(repository_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return await _enrich_repository_response(row, job_repo, wiki_repo)


@router.patch(
    "/repositories/{repository_id}",
    response_model=RepositoryResponse,
    summary="Update a repository",
    description=(
        "Partially update a registered repository. Only the fields included "
        "in the request body will be modified. If public_branch is updated, "
        "it must be one of the keys in the current or updated branch_mappings."
    ),
    responses={
        404: {
            "description": "Repository not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Repository not found"},
                },
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "public_branch 'staging' must be a key in branch_mappings",
                    },
                },
            },
        },
    },
)
async def update_repository(
    body: UpdateRepositoryRequest = Body(
        openapi_examples={
            "add_branch": {
                "summary": "Add a branch mapping",
                "value": {
                    "branch_mappings": {
                        "main": "production",
                        "develop": "staging",
                        "release/v2": "v2-preview",
                    },
                    "public_branch": "main",
                },
            },
            "rotate_token": {
                "summary": "Rotate access token",
                "value": {
                    "access_token": "ghp_NewRotatedToken9x8y7z6w5v4u3t2s1r0q",
                },
            },
        },
    ),
    repository_id: UUID = Path(
        description="Unique identifier of the repository.",
        openapi_examples={
            "example": {
                "summary": "Repository UUID",
                "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
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
    return await _enrich_repository_response(row, job_repo, wiki_repo)


@router.delete(
    "/repositories/{repository_id}",
    status_code=204,
    summary="Delete a repository",
    description=(
        "Delete a registered repository and all associated data "
        "(wiki structures, pages, chunks). This action is irreversible."
    ),
    responses={
        404: {
            "description": "Repository not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Repository not found"},
                },
            },
        },
    },
)
async def delete_repository(
    repository_id: UUID = Path(
        description="Unique identifier of the repository.",
        openapi_examples={
            "example": {
                "summary": "Repository UUID",
                "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> Response:
    deleted = await repo.delete(repository_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Repository not found")
    return Response(status_code=204)
