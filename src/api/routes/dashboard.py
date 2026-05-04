"""Dashboard-specific repository and job endpoints (Tasks 9.2-9.5, 9.9-9.11)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query

from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo
from src.api.schemas.dashboard import (
    AgentScoreTrend,
    AgentTokenBreakdown,
    AttemptHistory,
    ConfigPushRequest,
    ConfigPushResponse,
    JobProgressResponse,
    LastJobSummary,
    PageQualityDetailResponse,
    PageQualityRow,
    PipelineStage,
    RecentActivityEvent,
    RepositoryOverviewResponse,
    RepositoryQualityResponse,
    ScheduleConfig,
    ScheduleResponse,
    ScopeProgress,
    ScopeSummary,
)
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_repository_or_404(
    repository_id: UUID,
    repo: RepositoryRepo,
) -> object:
    """Fetch a repository by id or raise 404."""
    row = await repo.get_by_id(repository_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return row


def _job_event_name(status: str) -> str:
    """Map job status to an activity event name."""
    return {
        "PENDING": "job_created",
        "RUNNING": "job_started",
        "COMPLETED": "job_completed",
        "FAILED": "job_failed",
        "CANCELLED": "job_cancelled",
    }.get(status, "job_updated")


# ---------------------------------------------------------------------------
# 9.2: GET /repositories/{repository_id}/overview
# ---------------------------------------------------------------------------


@router.get(
    "/repositories/{repository_id}/overview",
    response_model=RepositoryOverviewResponse,
    summary="Repository overview",
    description=(
        "Aggregated overview including page count, average quality score, "
        "scope summaries, last job, and recent activity."
    ),
    responses={
        404: {"description": "Repository not found"},
    },
)
async def get_repository_overview(
    repository_id: UUID = Path(description="Unique identifier of the repository."),
    repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
    job_repo: JobRepo = Depends(get_job_repo),
) -> RepositoryOverviewResponse:
    """Aggregate overview data for a repository."""
    repository = await _get_repository_or_404(repository_id, repo)

    # Scope summaries - from latest structures per scope
    structures = await wiki_repo.get_structures_for_repo(
        repository_id=repository_id,
        branch=repository.public_branch,
    )
    latest_by_scope: dict[str, object] = {}
    for s in structures:
        latest_by_scope[s.scope_path] = s

    scope_summaries: list[ScopeSummary] = []
    total_pages = 0
    quality_sum = 0.0
    quality_count = 0

    for structure in latest_by_scope.values():
        page_count = await wiki_repo.count_pages_for_structure(structure.id)
        total_pages += page_count
        scope_summaries.append(
            ScopeSummary(
                scope_path=structure.scope_path,
                title=structure.title,
                page_count=page_count,
                latest_version=structure.version,
            )
        )

        # Compute average quality score from pages
        pages = await wiki_repo.get_pages_for_structure(structure.id)
        for page in pages:
            if page.quality_score is not None:
                quality_sum += page.quality_score
                quality_count += 1

    avg_quality = round(quality_sum / quality_count, 2) if quality_count > 0 else None

    # Last job
    jobs = await job_repo.list(repository_id=repository_id, limit=1)
    last_job = LastJobSummary.model_validate(jobs[0]) if jobs else None

    # Recent activity (last 20 jobs as events)
    recent_jobs = await job_repo.list(repository_id=repository_id, limit=20)
    recent_activity = [
        RecentActivityEvent(
            job_id=j.id,
            event=_job_event_name(j.status),
            timestamp=j.updated_at,
            branch=j.branch,
            mode=j.mode,
        )
        for j in recent_jobs
    ]

    return RepositoryOverviewResponse(
        repository_id=repository_id,
        page_count=total_pages,
        avg_quality_score=avg_quality,
        scope_summaries=scope_summaries,
        last_job=last_job,
        recent_activity=recent_activity,
    )


# ---------------------------------------------------------------------------
# 9.3: GET /repositories/{repository_id}/quality
# ---------------------------------------------------------------------------


@router.get(
    "/repositories/{repository_id}/quality",
    response_model=RepositoryQualityResponse,
    summary="Repository quality metrics",
    description=("Agent score trends, paginated page quality scores, and token breakdowns per agent."),
    responses={
        404: {"description": "Repository not found"},
    },
)
async def get_repository_quality(
    repository_id: UUID = Path(description="Unique identifier of the repository."),
    page: int = Query(default=1, ge=1, description="Page number for page scores pagination"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size for page scores"),
    repo: RepositoryRepo = Depends(get_repository_repo),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> RepositoryQualityResponse:
    """Return quality metrics for a repository.

    Aggregates data from completed jobs' quality_report and token_usage
    JSONB columns, plus per-page scores from the current wiki structure.
    """
    repository = await _get_repository_or_404(repository_id, repo)

    # --- Agent score trends (last 5 completed jobs) ---
    completed_jobs = await job_repo.list(
        repository_id=repository_id,
        status="COMPLETED",
        limit=5,
    )

    agent_names = ["structure_extractor", "page_generator", "readme_distiller"]
    agent_trends: dict[str, list[float]] = {name: [] for name in agent_names}

    for j in completed_jobs:
        qr = j.quality_report
        if not isinstance(qr, dict):
            continue
        # Structure score
        ss = qr.get("structure_score")
        if isinstance(ss, dict) and "score" in ss:
            agent_trends["structure_extractor"].append(ss["score"])
        # Page scores -> overall
        if "overall_score" in qr:
            agent_trends["page_generator"].append(qr["overall_score"])
        # Readme score
        rs = qr.get("readme_score")
        if isinstance(rs, dict) and "score" in rs:
            agent_trends["readme_distiller"].append(rs["score"])

    agent_scores: list[AgentScoreTrend] = []
    for agent_name in agent_names:
        trend = agent_trends[agent_name]
        agent_scores.append(
            AgentScoreTrend(
                agent=agent_name,
                current=trend[0] if trend else None,
                previous=trend[1] if len(trend) > 1 else None,
                trend=trend,
            )
        )

    # --- Page quality scores (from latest structure) ---
    structures = await wiki_repo.get_structures_for_repo(
        repository_id=repository_id,
        branch=repository.public_branch,
    )
    latest_by_scope: dict[str, object] = {}
    for s in structures:
        latest_by_scope[s.scope_path] = s

    all_page_rows: list[PageQualityRow] = []
    for structure in latest_by_scope.values():
        pages = await wiki_repo.get_pages_for_structure(structure.id)
        for p in pages:
            all_page_rows.append(
                PageQualityRow(
                    page_key=p.page_key,
                    title=p.title,
                    scope=structure.scope_path,
                    score=p.quality_score or 0.0,
                    attempts=1,  # TODO: extract from quality_report.page_scores
                    tokens=0,  # TODO: extract from token_usage.by_agent per page
                )
            )

    total_page_scores = len(all_page_rows)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_pages = all_page_rows[start_idx:end_idx]

    # --- Token breakdown per agent (from latest completed job) ---
    token_breakdown: list[AgentTokenBreakdown] = []
    if completed_jobs:
        tu = completed_jobs[0].token_usage
        if isinstance(tu, dict) and "by_agent" in tu:
            by_agent = tu["by_agent"]
            if isinstance(by_agent, dict):
                for agent_key, agent_data in by_agent.items():
                    if isinstance(agent_data, dict):
                        token_breakdown.append(
                            AgentTokenBreakdown(
                                agent=agent_key,
                                input_tokens=agent_data.get("input_tokens", 0),
                                output_tokens=agent_data.get("output_tokens", 0),
                                total_tokens=agent_data.get("total_tokens", 0),
                                calls=agent_data.get("calls", 0),
                            )
                        )

    return RepositoryQualityResponse(
        repository_id=repository_id,
        agent_scores=agent_scores,
        page_scores=paginated_pages,
        page_scores_total=total_page_scores,
        token_breakdown=token_breakdown,
    )


# ---------------------------------------------------------------------------
# 9.4: GET /repositories/{repository_id}/quality/pages/{page_key}
# ---------------------------------------------------------------------------


@router.get(
    "/repositories/{repository_id}/quality/pages/{page_key:path}",
    response_model=PageQualityDetailResponse,
    summary="Page quality detail",
    description=("Per-criterion scores, critic feedback text, and attempt history for a single wiki page."),
    responses={
        404: {"description": "Repository or page not found"},
    },
)
async def get_page_quality_detail(
    repository_id: UUID = Path(description="Unique identifier of the repository."),
    page_key: str = Path(description="Page key within the wiki structure."),
    scope: str = Query(default=".", description="Scope path"),
    repo: RepositoryRepo = Depends(get_repository_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
    job_repo: JobRepo = Depends(get_job_repo),
) -> PageQualityDetailResponse:
    """Return detailed quality data for a single wiki page."""
    repository = await _get_repository_or_404(repository_id, repo)

    structure = await wiki_repo.get_latest_structure(
        repository_id=repository_id,
        branch=repository.public_branch,
        scope_path=scope,
    )
    if structure is None:
        raise HTTPException(status_code=404, detail="No wiki structure found for this scope")

    page = await wiki_repo.get_page_by_key(
        wiki_structure_id=structure.id,
        page_key=page_key,
    )
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")

    # Extract per-criterion scores and attempt history from the latest
    # completed job's quality_report
    criteria_scores: dict[str, float] = {}
    critic_feedback: str | None = None
    attempt_history: list[AttemptHistory] = []

    completed_jobs = await job_repo.list(
        repository_id=repository_id,
        status="COMPLETED",
        limit=1,
    )

    if completed_jobs:
        qr = completed_jobs[0].quality_report
        if isinstance(qr, dict):
            page_scores_list = qr.get("page_scores", [])
            if isinstance(page_scores_list, list):
                for ps in page_scores_list:
                    if isinstance(ps, dict) and ps.get("page_key") == page_key:
                        criteria_scores = ps.get("criteria_scores", {}) or {}
                        # TODO: extract critic feedback from evaluation_history
                        break

    # TODO: implement with real attempt history from agent evaluation_history
    # For now, provide a single attempt from the current score
    attempt_history.append(
        AttemptHistory(
            attempt=1,
            score=page.quality_score or 0.0,
            passed=(page.quality_score or 0.0) >= 7.0,
            feedback=critic_feedback,
        )
    )

    return PageQualityDetailResponse(
        page_key=page.page_key,
        title=page.title,
        scope=scope,
        score=page.quality_score or 0.0,
        criteria_scores=criteria_scores,
        critic_feedback=critic_feedback,
        attempt_history=attempt_history,
    )


# ---------------------------------------------------------------------------
# 9.5: GET /jobs/{job_id}/progress
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}/progress",
    response_model=JobProgressResponse,
    summary="Job pipeline progress",
    description=("Pipeline stages with status/timing and per-scope progress (pages completed vs total)."),
    responses={
        404: {"description": "Job not found"},
    },
)
async def get_job_progress(
    job_id: UUID = Path(description="Unique identifier of the job."),
    job_repo: JobRepo = Depends(get_job_repo),
    wiki_repo: WikiRepo = Depends(get_wiki_repo),
) -> JobProgressResponse:
    """Return pipeline progress for a job.

    Derives stage info from Prefect task states and scope progress from
    wiki structures created by the job.
    """
    job = await job_repo.get_by_id(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Define the standard pipeline stages
    pipeline_stage_names = [
        "clone",
        "discover_scopes",
        "scan_files",
        "extract_structure",
        "generate_pages",
        "generate_readme",
        "create_embeddings",
        "create_pr",
    ]

    stages: list[PipelineStage] = []

    # Try to get actual stage info from Prefect task runs
    task_states: dict[str, dict] = {}
    if job.prefect_flow_run_id:
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
                for tr in task_runs:
                    state_name = tr.state.name if tr.state else "Unknown"
                    task_states[tr.name] = {
                        "status": state_name.lower(),
                        "started_at": tr.start_time,
                        "completed_at": tr.end_time if tr.state and tr.state.is_final() else None,
                    }
        except Exception:
            logger.warning("Failed to query Prefect task runs for job progress %s", job_id)

    # Build stages list
    for stage_name in pipeline_stage_names:
        task_info = task_states.get(stage_name, {})
        status = task_info.get("status", "pending")
        started_at = task_info.get("started_at")
        completed_at = task_info.get("completed_at")

        # Infer status from job state if no Prefect data
        if not task_states:
            if job.status == "COMPLETED":
                status = "completed"
            elif job.status == "FAILED":
                status = "failed"
            elif job.status == "CANCELLED":
                status = "skipped"
            elif job.status in ("PENDING", "RUNNING"):
                status = "pending"

        duration = None
        if started_at and completed_at:
            duration = (completed_at - started_at).total_seconds()

        stages.append(
            PipelineStage(
                name=stage_name,
                status=status,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration,
            )
        )

    # Scope progress - from wiki structures created by this job
    scope_progress: list[ScopeProgress] = []
    # TODO: implement with real query filtering wiki_structures by job_id
    # For now, derive from latest structures if job is completed
    if job.status == "COMPLETED":
        structures = await wiki_repo.get_structures_for_repo(
            repository_id=job.repository_id,
            branch=job.branch,
        )
        latest_by_scope: dict[str, object] = {}
        for s in structures:
            latest_by_scope[s.scope_path] = s

        for structure in latest_by_scope.values():
            page_count = await wiki_repo.count_pages_for_structure(structure.id)
            scope_progress.append(
                ScopeProgress(
                    scope_path=structure.scope_path,
                    pages_completed=page_count,
                    pages_total=page_count,
                )
            )

    return JobProgressResponse(
        job_id=job_id,
        status=job.status,
        stages=stages,
        scope_progress=scope_progress,
    )


# ---------------------------------------------------------------------------
# 9.9: PATCH /repositories/{repository_id}/schedule
# ---------------------------------------------------------------------------

# In-memory schedule store - in production this would be a database column
# on the Repository model or a separate table.
_schedules: dict[str, ScheduleConfig] = {}


@router.patch(
    "/repositories/{repository_id}/schedule",
    response_model=ScheduleResponse,
    summary="Update repository schedule",
    description="Create or update the auto-generation schedule for a repository.",
    responses={
        404: {"description": "Repository not found"},
    },
)
async def update_schedule(
    repository_id: UUID = Path(description="Unique identifier of the repository."),
    body: ScheduleConfig = Body(
        openapi_examples={
            "weekly_full": {
                "summary": "Weekly full generation on Monday",
                "value": {
                    "enabled": True,
                    "mode": "full",
                    "frequency": "weekly",
                    "day_of_week": 0,
                },
            },
            "disable": {
                "summary": "Disable schedule",
                "value": {
                    "enabled": False,
                },
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> ScheduleResponse:
    """Create or update the auto-generation schedule.

    Note: This is stored in-memory for now. A production implementation
    would persist to the database and register/update a Prefect schedule.
    """
    # TODO: persist schedule to database column or separate table
    # TODO: register/update Prefect scheduled deployment
    await _get_repository_or_404(repository_id, repo)

    _schedules[str(repository_id)] = body

    return ScheduleResponse(
        repository_id=repository_id,
        schedule=body,
    )


# ---------------------------------------------------------------------------
# 9.10: GET /repositories/{repository_id}/schedule
# ---------------------------------------------------------------------------


@router.get(
    "/repositories/{repository_id}/schedule",
    response_model=ScheduleResponse,
    summary="Get repository schedule",
    description="Return the current auto-generation schedule configuration.",
    responses={
        404: {"description": "Repository not found"},
    },
)
async def get_schedule(
    repository_id: UUID = Path(description="Unique identifier of the repository."),
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> ScheduleResponse:
    """Return the current schedule configuration for a repository."""
    # TODO: read from database instead of in-memory store
    await _get_repository_or_404(repository_id, repo)

    schedule = _schedules.get(str(repository_id), ScheduleConfig())

    return ScheduleResponse(
        repository_id=repository_id,
        schedule=schedule,
    )


# ---------------------------------------------------------------------------
# 9.11: POST /repositories/{repository_id}/config
# ---------------------------------------------------------------------------


@router.post(
    "/repositories/{repository_id}/config",
    response_model=ConfigPushResponse,
    status_code=201,
    summary="Push config update via PR",
    description=(
        "Create a pull request in the source repository containing an "
        "updated .autodoc.yaml file at the specified scope path."
    ),
    responses={
        404: {"description": "Repository not found"},
        502: {"description": "Failed to create PR via Git provider"},
    },
)
async def push_config(
    repository_id: UUID = Path(description="Unique identifier of the repository."),
    body: ConfigPushRequest = Body(
        openapi_examples={
            "root_config": {
                "summary": "Update root config",
                "value": {
                    "scope_path": ".",
                    "yaml_content": "title: My Project\nscopes:\n  - path: .\n    include:\n      - 'src/**/*.py'\n",
                },
            },
        },
    ),
    repo: RepositoryRepo = Depends(get_repository_repo),
) -> ConfigPushResponse:
    """Push an .autodoc.yaml update to the source repository via a PR.

    Uses the Git provider abstraction to create a branch and PR containing
    the updated config file.
    """
    repository = await _get_repository_or_404(repository_id, repo)

    # Build the file path within the repo
    file_path = ".autodoc.yaml" if body.scope_path == "." else f"{body.scope_path.rstrip('/')}/.autodoc.yaml"

    branch_name = f"autodoc/config-update-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    try:
        from src.providers import get_provider

        provider = get_provider(
            provider_type=repository.provider,
            access_token=repository.access_token,
        )
        pr_url = await provider.create_config_pr(
            org=repository.org,
            name=repository.name,
            branch=branch_name,
            base_branch=repository.public_branch,
            file_path=file_path,
            content=body.yaml_content,
            title=f"chore(autodoc): update {file_path}",
            body="Auto-generated config update from AutoDoc dashboard.",
        )
    except AttributeError as exc:
        # Provider does not implement create_config_pr yet
        # TODO: implement create_config_pr on GitHubProvider and BitbucketProvider
        raise HTTPException(
            status_code=501,
            detail="Config push via PR is not yet implemented for this Git provider",
        ) from exc
    except Exception as exc:
        logger.error("Failed to create config PR for repo %s: %s", repository_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create PR via Git provider: {exc}",
        ) from exc

    return ConfigPushResponse(
        pull_request_url=pr_url,
        branch=branch_name,
        scope_path=body.scope_path,
    )
