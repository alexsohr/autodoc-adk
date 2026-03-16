from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from fastapi.responses import JSONResponse

from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo
from src.api.schemas.jobs import (
    CreateJobRequest,
    JobResponse,
    JobStatus,
    LogEntry,
    PaginatedJobResponse,
    TaskState,
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
    """Submit the appropriate Prefect flow run.

    In dev mode (AUTODOC_FLOW_DEPLOYMENT_PREFIX == "dev"), uses
    asyncio.create_task() to run flows in-process.

    In K8s modes (dev-k8s, prod), uses Prefect's run_deployment() to
    dispatch flow runs via Prefect workers, which create K8s Jobs.
    """
    settings = get_settings()
    prefix = settings.AUTODOC_FLOW_DEPLOYMENT_PREFIX

    if prefix == "dev":
        # Dev mode: run flow in-process as a detached asyncio task
        if mode == "incremental":
            from src.flows.incremental_update import incremental_update_flow

            coro = incremental_update_flow(
                repository_id=repository_id,
                job_id=job_id,
                branch=branch,
                dry_run=dry_run,
            )
        else:
            from src.flows.full_generation import full_generation_flow

            coro = full_generation_flow(
                repository_id=repository_id,
                job_id=job_id,
                branch=branch,
                dry_run=dry_run,
            )

        task = asyncio.create_task(coro, name=f"flow-{mode}-{job_id}")
        task.add_done_callback(_flow_task_done)
    else:
        # K8s mode: dispatch via Prefect run_deployment()
        from prefect.deployments import run_deployment

        if mode == "incremental":
            flow_name = "incremental_update"
            deployment_name = f"{prefix}-incremental"
        else:
            flow_name = "full_generation"
            deployment_name = f"{prefix}-full-generation"

        logger.info(
            "Dispatching flow via run_deployment: %s/%s",
            flow_name,
            deployment_name,
        )

        try:
            await run_deployment(
                name=f"{flow_name}/{deployment_name}",
                parameters={
                    "repository_id": repository_id,
                    "job_id": job_id,
                    "branch": branch,
                    "dry_run": dry_run,
                },
                timeout=0,  # non-blocking: fire and forget
            )
        except Exception:
            logger.exception(
                "Failed to dispatch flow via run_deployment: %s/%s",
                flow_name,
                deployment_name,
            )
            raise


def _flow_task_done(task: asyncio.Task) -> None:
    """Log unhandled exceptions from detached flow tasks."""
    if task.cancelled():
        logger.warning("Flow task %s was cancelled", task.get_name())
    elif exc := task.exception():
        logger.error("Flow task %s failed: %s", task.get_name(), exc)


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=201,
    summary="Create a documentation job",
    description=(
        "Create a documentation generation job. Auto-determines full vs "
        "incremental mode unless force=true. Returns 200 with existing job "
        "if an active one already exists (idempotency), or 201 with the "
        "newly created job."
    ),
    responses={
        200: {
            "model": JobResponse,
            "description": "An active job already exists (idempotency).",
        },
        404: {
            "description": "Repository not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Repository not found"},
                },
            },
        },
        422: {
            "description": "Branch not in repository branch_mappings.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Branch 'develop' is not in repository branch_mappings",
                    },
                },
            },
        },
    },
)
async def create_job(
    body: CreateJobRequest = Body(
        ...,
        openapi_examples={
            "full_generation": {
                "summary": "Force full generation",
                "description": (
                    "Force a full documentation generation for a repository on "
                    "the main branch, with a webhook callback."
                ),
                "value": {
                    "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "branch": "main",
                    "force": True,
                    "dry_run": False,
                    "callback_url": "https://example.com/webhooks/autodoc",
                },
            },
            "incremental_dry_run": {
                "summary": "Incremental dry run",
                "description": (
                    "Let the system auto-determine the mode (incremental if a "
                    "prior structure exists) and perform a dry run without "
                    "committing changes."
                ),
                "value": {
                    "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "branch": None,
                    "force": False,
                    "dry_run": True,
                    "callback_url": None,
                },
            },
        },
    ),
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

    # 7. Submit flow
    try:
        await _submit_flow(
            mode=mode,
            repository_id=body.repository_id,
            job_id=job.id,
            branch=branch,
            dry_run=body.dry_run,
        )
    except Exception as exc:
        logger.error(
            "Failed to submit %s flow for job %s: %s", mode, job.id, exc
        )
        job = await job_repo.update_status(
            job.id,
            "FAILED",
            error_message=f"Flow submission failed: {exc}",
        )
        return JSONResponse(
            status_code=201,
            content=JobResponse.model_validate(job).model_dump(mode="json"),
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
    summary="List jobs",
    description=(
        "List documentation jobs with optional filters and cursor-based "
        "pagination. Pass `cursor` from the previous response's "
        "`next_cursor` field to retrieve subsequent pages."
    ),
)
async def list_jobs(
    repository_id: UUID | None = Query(
        None,
        description="Filter jobs by repository UUID.",
        openapi_examples={
            "all": {
                "summary": "All repositories",
                "value": None,
            },
            "filter": {
                "summary": "Filter by repository",
                "value": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            },
        },
    ),
    status: JobStatus | None = Query(
        None,
        description="Filter jobs by status.",
        openapi_examples={
            "all": {
                "summary": "All statuses",
                "value": None,
            },
            "failed_only": {
                "summary": "Failed jobs only",
                "value": "FAILED",
            },
        },
    ),
    branch: str | None = Query(
        None,
        description="Filter jobs by branch name.",
        openapi_examples={
            "all": {
                "summary": "All branches",
                "value": None,
            },
            "main_only": {
                "summary": "Main branch only",
                "value": "main",
            },
        },
    ),
    cursor: UUID | None = Query(
        None,
        description="Cursor for pagination. Use next_cursor from the previous response.",
        openapi_examples={
            "first_page": {
                "summary": "First page",
                "value": None,
            },
            "next_page": {
                "summary": "Next page",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
        description="Maximum number of results per page.",
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
    summary="Get a job",
    description="Return a single documentation job by its unique identifier.",
    responses={
        404: {
            "description": "Job not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Job not found"},
                },
            },
        },
    },
)
async def get_job(
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the job.",
        openapi_examples={
            "example": {
                "summary": "Job UUID",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
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
    summary="Get job wiki structure",
    description=(
        "Return the latest wiki structure for the job's repository and branch. "
        "Returns 404 if the job does not exist or no structure has been "
        "generated yet."
    ),
    responses={
        404: {
            "description": "Job or structure not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "job_not_found": {
                            "summary": "Job not found",
                            "value": {"detail": "Job not found"},
                        },
                        "structure_not_found": {
                            "summary": "Structure not found",
                            "value": {"detail": "No structure found for this job"},
                        },
                    },
                },
            },
        },
    },
)
async def get_job_structure(
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the job.",
        openapi_examples={
            "example": {
                "summary": "Job UUID",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
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


# ---------------------------------------------------------------------------
# T071: POST /jobs/{job_id}/cancel
# ---------------------------------------------------------------------------


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel a job",
    description=(
        "Cancel a PENDING or RUNNING job. For RUNNING jobs with a Prefect "
        "flow run, cancellation is propagated via the Prefect API. "
        "Returns 409 for non-cancellable states."
    ),
    responses={
        404: {
            "description": "Job not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Job not found"},
                },
            },
        },
        409: {
            "description": "Job cannot be cancelled in its current state.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Job is in COMPLETED state and cannot be cancelled",
                    },
                },
            },
        },
    },
)
async def cancel_job(
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the job.",
        openapi_examples={
            "example": {
                "summary": "Job UUID",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
    job_repo: JobRepo = Depends(get_job_repo),
) -> JobResponse:
    """Cancel a PENDING or RUNNING job.

    For RUNNING jobs with a prefect_flow_run_id, cancels via Prefect API.
    For PENDING jobs with no prefect_flow_run_id, updates status directly.
    Returns 409 for non-cancellable states.
    """
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(
            status_code=409,
            detail=f"Job is in {job.status} state and cannot be cancelled",
        )

    # For RUNNING jobs with a Prefect flow run, cancel via Prefect API
    if job.status == "RUNNING" and job.prefect_flow_run_id:
        try:
            import prefect.states
            from prefect.client.orchestration import get_client

            async with get_client() as client:
                await client.set_flow_run_state(
                    flow_run_id=UUID(job.prefect_flow_run_id),
                    state=prefect.states.Cancelling(),
                )
        except Exception:
            logger.warning(
                "Failed to cancel Prefect flow run %s, proceeding with DB update",
                job.prefect_flow_run_id,
            )

    updated = await job_repo.update_status(job_id, "CANCELLED")
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found")

    logger.info("Cancelled job %s (was %s)", job_id, job.status)
    return JobResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# T072: POST /jobs/{job_id}/retry
# ---------------------------------------------------------------------------


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry a failed job",
    description=(
        "Retry a FAILED job by resetting it to PENDING and submitting a new "
        "Prefect flow run. The mode is re-determined based on current state. "
        "Returns 409 for non-FAILED states."
    ),
    responses={
        404: {
            "description": "Job not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Job not found"},
                },
            },
        },
        409: {
            "description": "Only FAILED jobs can be retried.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Only FAILED jobs can be retried. Current status: COMPLETED",
                    },
                },
            },
        },
    },
)
async def retry_job(
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the job.",
        openapi_examples={
            "example": {
                "summary": "Job UUID",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
    job_repo: JobRepo = Depends(get_job_repo),
    repository_repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> JobResponse:
    """Retry a FAILED job. Resets to PENDING and triggers new flow run.

    Returns 409 for non-FAILED states (COMPLETED and CANCELLED are terminal).
    """
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != "FAILED":
        raise HTTPException(
            status_code=409,
            detail=f"Only FAILED jobs can be retried. Current status: {job.status}",
        )

    # Reset to PENDING, clear error fields
    updated = await job_repo.update_status(
        job_id,
        "PENDING",
        error_message=None,
        prefect_flow_run_id=None,
        commit_sha=None,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Re-determine mode (same logic as create_job)
    if updated.force:
        mode = "full"
    else:
        structure = await wiki_repo.get_latest_structure(
            repository_id=updated.repository_id,
            branch=updated.branch,
        )
        mode = "full" if structure is None else "incremental"

    # Re-submit flow
    try:
        await _submit_flow(
            mode=mode,
            repository_id=updated.repository_id,
            job_id=updated.id,
            branch=updated.branch,
            dry_run=updated.dry_run,
        )
    except Exception as exc:
        logger.error("Failed to submit retry flow for job %s: %s", job_id, exc)
        updated = await job_repo.update_status(
            job_id,
            "FAILED",
            error_message=f"Flow submission failed: {exc}",
        )
        return JobResponse.model_validate(updated)

    logger.info("Retrying job %s (mode=%s)", job_id, mode)
    return JobResponse.model_validate(updated)


# ---------------------------------------------------------------------------
# T073: GET /jobs/{job_id}/tasks
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}/tasks",
    response_model=list[TaskState],
    summary="Get job task states",
    description=(
        "Get Prefect task states for a job's flow run. Returns an empty "
        "list if the job has no associated Prefect flow run or if the "
        "Prefect API is unavailable."
    ),
    responses={
        404: {
            "description": "Job not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Job not found"},
                },
            },
        },
    },
)
async def get_job_tasks(
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the job.",
        openapi_examples={
            "example": {
                "summary": "Job UUID",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
    job_repo: JobRepo = Depends(get_job_repo),
) -> list[TaskState]:
    """Get Prefect task states for a job's flow run."""
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.prefect_flow_run_id:
        return []

    try:
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import (
            TaskRunFilter,
            TaskRunFilterFlowRunId,
        )

        async with get_client() as client:
            task_runs = await client.read_task_runs(
                task_run_filter=TaskRunFilter(
                    flow_run_id=TaskRunFilterFlowRunId(
                        any_=[job.prefect_flow_run_id],
                    ),
                ),
            )
    except Exception:
        logger.warning("Failed to query Prefect task runs for job %s", job_id)
        return []

    return [
        TaskState(
            task_name=tr.name,
            state=tr.state.name if tr.state else "Unknown",
            started_at=tr.start_time,
            completed_at=tr.end_time if tr.state and tr.state.is_final() else None,
            message=tr.state.message if tr.state else None,
        )
        for tr in task_runs
    ]


# ---------------------------------------------------------------------------
# T073: GET /jobs/{job_id}/logs
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}/logs",
    response_model=list[LogEntry],
    summary="Get job logs",
    description=(
        "Get Prefect flow run logs for a job. Returns an empty list if "
        "the job has no associated Prefect flow run or if the Prefect API "
        "is unavailable."
    ),
    responses={
        404: {
            "description": "Job not found.",
            "content": {
                "application/json": {
                    "example": {"detail": "Job not found"},
                },
            },
        },
    },
)
async def get_job_logs(
    job_id: UUID = Path(
        ...,
        description="Unique identifier of the job.",
        openapi_examples={
            "example": {
                "summary": "Job UUID",
                "value": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
            },
        },
    ),
    job_repo: JobRepo = Depends(get_job_repo),
) -> list[LogEntry]:
    """Get Prefect flow run logs for a job."""
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.prefect_flow_run_id:
        return []

    try:
        from prefect.client.orchestration import get_client
        from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId

        async with get_client() as client:
            logs = await client.read_logs(
                log_filter=LogFilter(
                    flow_run_id=LogFilterFlowRunId(
                        any_=[job.prefect_flow_run_id],
                    ),
                ),
            )
    except Exception:
        logger.warning("Failed to query Prefect logs for job %s", job_id)
        return []

    return [
        LogEntry(
            timestamp=log.timestamp,
            level=log.level_name if hasattr(log, "level_name") else str(log.level),
            message=log.message,
            task_name=None,  # Prefect logs don't always have task association
        )
        for log in logs
    ]
