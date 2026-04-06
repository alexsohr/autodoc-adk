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

# Per-token cost estimates (USD per token) — Gemini Flash ballpark.
# Update these when provider pricing changes.
_INPUT_TOKEN_COST = 0.15 / 1_000_000   # $0.15 per 1M input tokens
_OUTPUT_TOKEN_COST = 0.60 / 1_000_000  # $0.60 per 1M output tokens

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

    # Aggregate token totals in SQL to avoid loading all rows into Python
    _token_filters = [
        Job.status == "COMPLETED",
        Job.token_usage.isnot(None),
        Job.created_at >= period_start,
        Job.created_at <= period_end,
    ]

    totals_stmt = sa.select(
        sa.func.coalesce(
            sa.func.sum(sa.cast(Job.token_usage["total_input_tokens"].astext, sa.BigInteger)), 0
        ).label("total_input"),
        sa.func.coalesce(
            sa.func.sum(sa.cast(Job.token_usage["total_output_tokens"].astext, sa.BigInteger)), 0
        ).label("total_output"),
        sa.func.coalesce(
            sa.func.sum(sa.cast(Job.token_usage["total_tokens"].astext, sa.BigInteger)), 0
        ).label("total"),
    ).where(*_token_filters)

    totals_result = await session.execute(totals_stmt)
    totals_row = totals_result.one()
    total_input = totals_row.total_input
    total_output = totals_row.total_output
    total = totals_row.total

    estimated_cost = total_input * _INPUT_TOKEN_COST + total_output * _OUTPUT_TOKEN_COST

    # Top repositories by token usage (aggregated in SQL, limited to top 10)
    repo_totals_stmt = (
        sa.select(
            Job.repository_id,
            sa.func.sum(sa.cast(Job.token_usage["total_tokens"].astext, sa.BigInteger)).label("repo_tokens"),
        )
        .where(*_token_filters)
        .group_by(Job.repository_id)
        .order_by(sa.desc("repo_tokens"))
        .limit(10)
    )
    repo_totals_result = await session.execute(repo_totals_stmt)
    repo_rows = repo_totals_result.all()

    # Batch-fetch repository names to avoid N+1 queries
    top_repo_items: list[TopRepoByTokens] = []
    if repo_rows:
        repo_ids = [r.repository_id for r in repo_rows]
        names_stmt = sa.select(Repository.id, Repository.name).where(Repository.id.in_(repo_ids))
        names_result = await session.execute(names_stmt)
        name_map: dict[uuid.UUID, str] = {r.id: r.name for r in names_result.all()}

        for r in repo_rows:
            top_repo_items.append(
                TopRepoByTokens(
                    repository_id=r.repository_id,
                    name=name_map.get(r.repository_id, "unknown"),
                    total_tokens=r.repo_tokens or 0,
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
