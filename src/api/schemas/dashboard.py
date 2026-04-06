"""Pydantic schemas for dashboard API endpoints (Tasks 9.1-9.11)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# 9.1: GET /auth/me
# ---------------------------------------------------------------------------


class AuthUserResponse(BaseModel):
    """Current authenticated user extracted from SSO proxy headers."""

    username: str
    email: str
    role: str


# ---------------------------------------------------------------------------
# 9.2: GET /repositories/{id}/overview
# ---------------------------------------------------------------------------


class ScopeSummary(BaseModel):
    """Summary of a documentation scope within a repository."""

    scope_path: str
    title: str | None = None
    page_count: int = 0
    latest_version: int = 1


class LastJobSummary(BaseModel):
    """Compact summary of the most recent job for a repository."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    mode: str
    branch: str
    created_at: datetime
    updated_at: datetime


class RecentActivityEvent(BaseModel):
    """A single activity event derived from job history."""

    job_id: UUID
    event: str  # e.g. "job_created", "job_completed", "job_failed"
    timestamp: datetime
    branch: str
    mode: str


class RepositoryOverviewResponse(BaseModel):
    """Aggregated overview for a repository."""

    repository_id: UUID
    page_count: int
    avg_quality_score: float | None = None
    scope_summaries: list[ScopeSummary] = []
    last_job: LastJobSummary | None = None
    recent_activity: list[RecentActivityEvent] = []


# ---------------------------------------------------------------------------
# 9.3: GET /repositories/{id}/quality
# ---------------------------------------------------------------------------


class AgentScoreTrend(BaseModel):
    """Current, previous, and trend values for an agent's score history."""

    agent: str
    current: float | None = None
    previous: float | None = None
    trend: list[float] = Field(default_factory=list, description="Scores for last 5 runs, newest first")


class PageQualityRow(BaseModel):
    """Quality data for a single wiki page."""

    page_key: str
    title: str
    scope: str
    score: float
    attempts: int
    tokens: int


class AgentTokenBreakdown(BaseModel):
    """Token usage for a single agent."""

    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class RepositoryQualityResponse(BaseModel):
    """Quality metrics for a repository."""

    repository_id: UUID
    agent_scores: list[AgentScoreTrend] = []
    page_scores: list[PageQualityRow] = []
    page_scores_total: int = 0
    token_breakdown: list[AgentTokenBreakdown] = []


# ---------------------------------------------------------------------------
# 9.4: GET /repositories/{id}/quality/pages/{page_key}
# ---------------------------------------------------------------------------


class AttemptHistory(BaseModel):
    """A single attempt in the quality loop."""

    attempt: int
    score: float
    passed: bool
    feedback: str | None = None


class PageQualityDetailResponse(BaseModel):
    """Detailed quality data for a single wiki page."""

    page_key: str
    title: str
    scope: str
    score: float
    criteria_scores: dict[str, float] = {}
    critic_feedback: str | None = None
    attempt_history: list[AttemptHistory] = []


# ---------------------------------------------------------------------------
# 9.5: GET /jobs/{id}/progress
# ---------------------------------------------------------------------------


class PipelineStage(BaseModel):
    """A pipeline stage with status and timing."""

    name: str
    status: str  # "pending", "running", "completed", "failed", "skipped"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None


class ScopeProgress(BaseModel):
    """Progress for a single scope within a job."""

    scope_path: str
    pages_completed: int = 0
    pages_total: int = 0


class JobProgressResponse(BaseModel):
    """Pipeline progress for a job."""

    job_id: UUID
    status: str
    stages: list[PipelineStage] = []
    scope_progress: list[ScopeProgress] = []


# ---------------------------------------------------------------------------
# 9.6: GET /admin/health
# ---------------------------------------------------------------------------


class WorkerPoolInfo(BaseModel):
    """Details about a Prefect worker pool."""

    name: str
    type: str | None = None
    status: str = "unknown"
    concurrency_limit: int | None = None


class DatabaseHealthInfo(BaseModel):
    """Database version and extension info."""

    version: str | None = None
    pgvector_installed: bool = False
    storage_mb: float | None = None


class AdminHealthResponse(BaseModel):
    """Extended health check for admin dashboard."""

    api_uptime_seconds: float
    api_latency_ms: float | None = None
    prefect_status: str = "unknown"
    prefect_pool_count: int = 0
    database: DatabaseHealthInfo = Field(default_factory=DatabaseHealthInfo)
    worker_pools: list[WorkerPoolInfo] = []


# ---------------------------------------------------------------------------
# 9.7: GET /admin/usage
# ---------------------------------------------------------------------------


class TopRepoByTokens(BaseModel):
    """A repository ranked by token usage."""

    repository_id: UUID
    name: str
    total_tokens: int = 0


class UsageByModel(BaseModel):
    """Token usage grouped by model."""

    model: str
    total_tokens: int = 0
    calls: int = 0


class AdminUsageResponse(BaseModel):
    """Aggregate usage metrics for the admin dashboard."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    job_count: int = 0
    top_repos_by_tokens: list[TopRepoByTokens] = []
    usage_by_model: list[UsageByModel] = []
    period_start: datetime | None = None
    period_end: datetime | None = None


# ---------------------------------------------------------------------------
# 9.8: GET /admin/mcp
# ---------------------------------------------------------------------------


class McpToolInfo(BaseModel):
    """Metadata for a single MCP tool."""

    name: str
    description: str | None = None


class AdminMcpResponse(BaseModel):
    """MCP server status and tool listing."""

    endpoint_url: str
    status: str = "unknown"  # "running" | "stopped" | "unknown"
    tools: list[McpToolInfo] = []
    total_calls: int = 0


# ---------------------------------------------------------------------------
# 9.9 / 9.10: PATCH / GET /repositories/{id}/schedule
# ---------------------------------------------------------------------------


class ScheduleConfig(BaseModel):
    """Auto-generation schedule configuration."""

    enabled: bool = False
    mode: str = "full"  # "full" | "incremental"
    frequency: str = "weekly"  # "daily" | "weekly" | "monthly"
    day_of_week: int | None = Field(
        default=None,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday). Relevant for weekly frequency.",
    )


class ScheduleResponse(BaseModel):
    """Response for schedule endpoints."""

    repository_id: UUID
    schedule: ScheduleConfig


# ---------------------------------------------------------------------------
# 9.11: POST /repositories/{id}/config
# ---------------------------------------------------------------------------


class ConfigPushRequest(BaseModel):
    """Request to push a .autodoc.yaml config update via PR."""

    scope_path: str = Field(default=".", description="Scope path where the config file lives")
    yaml_content: str = Field(description="Full YAML content for the .autodoc.yaml file")


class ConfigPushResponse(BaseModel):
    """Response after creating a config-update PR."""

    pull_request_url: str
    branch: str
    scope_path: str
