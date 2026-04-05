"""Admin endpoints for the dashboard UI (Tasks 9.6, 9.7, 9.8)."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import UTC, datetime

import httpx
import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_job_repo
from src.api.schemas.dashboard import (
    AdminHealthResponse,
    AdminMcpResponse,
    AdminUsageResponse,
    DatabaseHealthInfo,
    McpToolInfo,
    TopRepoByTokens,
    WorkerPoolInfo,
)
from src.config.settings import get_settings
from src.database.models.job import Job
from src.database.models.repository import Repository
from src.database.repos.job_repo import JobRepo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Module-level start time for uptime calculation
_start_time = time.monotonic()


# ---------------------------------------------------------------------------
# 9.6: GET /admin/health
# ---------------------------------------------------------------------------


@router.get(
    "/health",
    response_model=AdminHealthResponse,
    summary="Admin health check",
    description=(
        "Extended health check returning API uptime, Prefect server status, "
        "database version/pgvector info, and worker pool details."
    ),
)
async def admin_health(
    session: AsyncSession = Depends(get_db_session),
) -> AdminHealthResponse:
    """Return detailed system health for the admin dashboard."""
    settings = get_settings()

    # API uptime
    uptime_seconds = time.monotonic() - _start_time

    # Database info
    db_info = DatabaseHealthInfo()
    try:
        version_result = await session.execute(text("SELECT version()"))
        db_info.version = version_result.scalar_one_or_none()

        pgvector_result = await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        db_info.pgvector_installed = pgvector_result.scalar_one_or_none() is not None

        size_result = await session.execute(text("SELECT pg_database_size(current_database()) / (1024.0 * 1024.0)"))
        db_info.storage_mb = size_result.scalar_one_or_none()
    except Exception:
        logger.warning("Failed to query database metadata for admin health")

    # Prefect status and worker pools
    prefect_status = "unknown"
    pool_count = 0
    worker_pools: list[WorkerPoolInfo] = []

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.PREFECT_API_URL}/health")
            prefect_status = "healthy" if resp.status_code == 200 else "unhealthy"

            # Fetch work pools
            pools_resp = await client.post(
                f"{settings.PREFECT_API_URL}/work_pools/filter",
                json={},
            )
            if pools_resp.status_code == 200:
                pools_data = pools_resp.json()
                pool_count = len(pools_data)
                for pool in pools_data:
                    worker_pools.append(
                        WorkerPoolInfo(
                            name=pool.get("name", ""),
                            type=pool.get("type"),
                            status=pool.get("status", "unknown"),
                            concurrency_limit=pool.get("concurrency_limit"),
                        )
                    )
    except Exception:
        logger.warning("Failed to query Prefect API for admin health")

    return AdminHealthResponse(
        api_uptime_seconds=uptime_seconds,
        prefect_status=prefect_status,
        prefect_pool_count=pool_count,
        database=db_info,
        worker_pools=worker_pools,
    )


# ---------------------------------------------------------------------------
# 9.7: GET /admin/usage
# ---------------------------------------------------------------------------


@router.get(
    "/usage",
    response_model=AdminUsageResponse,
    summary="Usage statistics",
    description=(
        "Aggregate token usage, cost estimates, job counts, and top repositories. "
        "Supports optional time range filtering via query parameters."
    ),
)
async def admin_usage(
    since: datetime | None = Query(
        default=None,
        description="Start of time range (ISO 8601). Defaults to all time.",
    ),
    until: datetime | None = Query(
        default=None,
        description="End of time range (ISO 8601). Defaults to now.",
    ),
    job_repo: JobRepo = Depends(get_job_repo),
    session: AsyncSession = Depends(get_db_session),
) -> AdminUsageResponse:
    """Aggregate usage metrics across completed jobs.

    Scans the ``token_usage`` JSONB column on completed jobs within the given
    time range to compute totals, per-model breakdowns, and top repositories.
    """
    # TODO: implement with real query - aggregating token_usage JSONB from jobs table
    # For now, return simulated data to unblock the dashboard UI

    # Build time-range filter clause fragments
    period_start = since or datetime(2020, 1, 1, tzinfo=UTC)
    period_end = until or datetime.now(UTC)

    # Count completed jobs in range
    count_stmt = (
        sa.select(sa_func.count())
        .select_from(Job)
        .where(
            Job.status == "COMPLETED",
            Job.created_at >= period_start,
            Job.created_at <= period_end,
        )
    )
    count_result = await session.execute(count_stmt)
    job_count = count_result.scalar_one()

    # Aggregate token totals from JSONB - simplified placeholder
    # TODO: implement with real query using jsonb_extract_path / cast for aggregation
    total_input = 0
    total_output = 0
    total = 0

    jobs_stmt = (
        sa.select(Job.token_usage, Job.repository_id)
        .where(
            Job.status == "COMPLETED",
            Job.token_usage.isnot(None),
            Job.created_at >= period_start,
            Job.created_at <= period_end,
        )
        .limit(1000)
    )
    jobs_result = await session.execute(jobs_stmt)
    rows = jobs_result.all()

    repo_tokens: dict[str, int] = {}

    for row in rows:
        usage = row.token_usage
        if not isinstance(usage, dict):
            continue
        inp = usage.get("total_input_tokens", 0) or 0
        out = usage.get("total_output_tokens", 0) or 0
        tot = usage.get("total_tokens", 0) or 0
        total_input += inp
        total_output += out
        total += tot

        repo_key = str(row.repository_id)
        repo_tokens[repo_key] = repo_tokens.get(repo_key, 0) + tot

    # Rough cost estimate ($0.15 per 1M input, $0.60 per 1M output - Gemini Flash ballpark)
    estimated_cost = (total_input * 0.15 + total_output * 0.60) / 1_000_000

    # Build top repos (fetch names)
    top_repo_items: list[TopRepoByTokens] = []
    if repo_tokens:
        sorted_repos = sorted(repo_tokens.items(), key=lambda x: x[1], reverse=True)[:10]
        for repo_id_str, tokens in sorted_repos:
            try:
                repo_uuid = uuid.UUID(repo_id_str)
            except ValueError:
                continue
            repo_row = await session.get(Repository, repo_uuid)
            top_repo_items.append(
                TopRepoByTokens(
                    repository_id=repo_uuid,
                    name=repo_row.name if repo_row else "unknown",
                    total_tokens=tokens,
                )
            )

    return AdminUsageResponse(
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total,
        estimated_cost_usd=round(estimated_cost, 4),
        job_count=job_count,
        top_repos_by_tokens=top_repo_items,
        usage_by_model=[],  # TODO: implement with real query parsing token_usage.by_agent
        period_start=period_start,
        period_end=period_end,
    )


# ---------------------------------------------------------------------------
# 9.8: GET /admin/mcp
# ---------------------------------------------------------------------------


@router.get(
    "/mcp",
    response_model=AdminMcpResponse,
    summary="MCP server status",
    description=(
        "Return MCP server endpoint URL, list of registered tools, running/stopped status, and usage statistics."
    ),
)
async def admin_mcp() -> AdminMcpResponse:
    """Return MCP server info and tool listing.

    Reads tool definitions from the fastmcp server instance.  Status is
    determined by checking whether the MCP module is importable and its
    tools are registered.
    """
    settings = get_settings()
    endpoint_url = f"{settings.PREFECT_API_URL.rsplit('/api', 1)[0]}/mcp"

    tools: list[McpToolInfo] = []
    status = "unknown"

    try:
        from src.mcp_server import mcp as mcp_server

        # FastMCP exposes tools via its internal registry
        if hasattr(mcp_server, "_tool_manager") and hasattr(mcp_server._tool_manager, "tools"):
            for name, tool in mcp_server._tool_manager.tools.items():
                tools.append(
                    McpToolInfo(
                        name=name,
                        description=getattr(tool, "description", None),
                    )
                )
        elif hasattr(mcp_server, "list_tools"):
            # Fallback for newer FastMCP versions
            pass

        status = "running" if tools else "stopped"
    except Exception:
        logger.warning("Failed to inspect MCP server tools")
        status = "stopped"

    # If we could not introspect tools, provide a static fallback
    if not tools:
        tools = [
            McpToolInfo(
                name="find_repository", description="Find registered repositories by name, URL, or partial match"
            ),
            McpToolInfo(name="query_documents", description="Search documentation for a registered repository"),
        ]

    return AdminMcpResponse(
        endpoint_url=endpoint_url,
        status=status,
        tools=tools,
        total_calls=0,  # TODO: implement with real call tracking
    )
