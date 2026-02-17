from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo
from src.api.schemas.jobs import (
    CreateJobRequest,
    JobResponse,
    JobStatus,
    PaginatedJobResponse,
    WikiStructureResponse,
)
from src.config.settings import get_settings
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])


async def _submit_flow(
    mode: str,
    repository_id: UUID,
    job_id: UUID,
    branch: str,
    dry_run: bool,
) -> None:
    """Submit the appropriate Prefect flow run based on job mode."""
    if mode == "incremental":
        from src.flows.incremental_update import incremental_update_flow

        await incremental_update_flow(
            repository_id=repository_id,
            job_id=job_id,
            branch=branch,
            dry_run=dry_run,
        )
    else:
        from src.flows.full_generation import full_generation_flow

        await full_generation_flow(
            repository_id=repository_id,
            job_id=job_id,
            branch=branch,
            dry_run=dry_run,
        )


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=201,
    responses={200: {"model": JobResponse}},
)
async def create_job(
    body: CreateJobRequest,
    background_tasks: BackgroundTasks,
    job_repo: JobRepo = Depends(get_job_repo),
    repository_repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> JSONResponse | JobResponse:
    """Create a documentation generation job.

    Auto-determines full vs incremental mode unless ``force=true``.
    Returns 200 with the existing job if an active one already exists
    (idempotency), or 201 with the newly created job.

    The appropriate Prefect flow (full_generation or incremental_update)
    is submitted as a background task after the response is returned.
    """
    # 1. Look up repository
    repo = await repository_repo.get_by_id(body.repository_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    # 2. Determine branch
    branch = body.branch if body.branch else repo.public_branch

    # 3. Validate branch is in branch_mappings
    if branch not in repo.branch_mappings:
        raise HTTPException(
            status_code=422,
            detail=f"Branch '{branch}' is not in repository branch_mappings",
        )

    # 4. Idempotency: check for existing active job
    existing = await job_repo.get_active_for_repo(
        repository_id=body.repository_id,
        branch=branch,
        dry_run=body.dry_run,
    )
    if existing is not None:
        return JSONResponse(
            status_code=200,
            content=JobResponse.model_validate(existing).model_dump(mode="json"),
        )

    # 5. Determine mode
    if body.force:
        mode = "full"
    else:
        structure = await wiki_repo.get_latest_structure(
            repository_id=body.repository_id,
            branch=branch,
        )
        mode = "full" if structure is None else "incremental"

    # 6. Create job
    settings = get_settings()
    job = await job_repo.create(
        repository_id=body.repository_id,
        status="PENDING",
        mode=mode,
        branch=branch,
        force=body.force,
        dry_run=body.dry_run,
        app_commit_sha=settings.APP_COMMIT_SHA,
        callback_url=body.callback_url,
    )

    # 7. Submit flow as background task
    background_tasks.add_task(
        _submit_flow,
        mode=mode,
        repository_id=body.repository_id,
        job_id=job.id,
        branch=branch,
        dry_run=body.dry_run,
    )

    logger.info(
        "Created %s job %s for repo %s branch=%s",
        mode,
        job.id,
        body.repository_id,
        branch,
    )

    return JobResponse.model_validate(job)


@router.get(
    "/jobs",
    response_model=PaginatedJobResponse,
)
async def list_jobs(
    repository_id: UUID | None = Query(None),
    status: JobStatus | None = Query(None),
    branch: str | None = Query(None),
    cursor: UUID | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    job_repo: JobRepo = Depends(get_job_repo),
) -> PaginatedJobResponse:
    """List jobs with optional filters and cursor-based pagination."""
    rows = await job_repo.list(
        repository_id=repository_id,
        status=status.value if status else None,
        branch=branch,
        cursor=cursor,
        limit=limit,
    )
    next_cursor = str(rows[-1].id) if len(rows) == limit else None
    return PaginatedJobResponse(
        items=[JobResponse.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        limit=limit,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
)
async def get_job(
    job_id: UUID,
    job_repo: JobRepo = Depends(get_job_repo),
) -> JobResponse:
    """Return a single job by ID."""
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.get(
    "/jobs/{job_id}/structure",
    response_model=WikiStructureResponse,
)
async def get_job_structure(
    job_id: UUID,
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> WikiStructureResponse:
    """Return the latest wiki structure for the job's repository and branch."""
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    structure = await wiki_repo.get_latest_structure(
        repository_id=job.repository_id,
        branch=job.branch,
    )
    if structure is None:
        raise HTTPException(status_code=404, detail="No structure found for this job")

    return WikiStructureResponse.model_validate(structure)
