from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class JobStatus(enum.StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobMode(enum.StrEnum):
    full = "full"
    incremental = "incremental"


class CreateJobRequest(BaseModel):
    repository_id: UUID
    branch: str | None = None  # defaults to repo's public_branch
    force: bool = False  # forces full mode
    dry_run: bool = False  # structure extraction only
    callback_url: str | None = None  # webhook notification URL


class AgentTokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class TokenUsage(BaseModel):
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    by_agent: dict[str, AgentTokenUsage] | None = None


class PageScore(BaseModel):
    page_key: str
    score: float
    passed: bool
    attempts: int
    below_minimum_floor: bool | None = None
    criteria_scores: dict[str, float] | None = None


class AgentScore(BaseModel):
    score: float
    passed: bool
    attempts: int
    criteria_scores: dict[str, float] | None = None


class QualityReport(BaseModel):
    overall_score: float
    quality_threshold: float
    passed: bool
    total_pages: int
    pages_below_floor: int | None = None
    page_scores: list[PageScore] | None = None
    readme_score: AgentScore | None = None
    structure_score: AgentScore | None = None
    regenerated_pages: list[str] | None = None
    no_changes: bool | None = None


class ConfigWarning(BaseModel):
    scope_path: str
    message: str
    key: str | None = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    status: JobStatus
    mode: JobMode
    branch: str
    commit_sha: str | None = None
    force: bool
    dry_run: bool
    quality_report: QualityReport | None = None
    token_usage: TokenUsage | None = None
    config_warnings: list[ConfigWarning] | None = None
    pull_request_url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedJobResponse(BaseModel):
    items: list[JobResponse]
    next_cursor: str | None = None
    limit: int = 20


# For GET /jobs/{id}/structure
class WikiPageSummary(BaseModel):
    page_key: str
    title: str
    description: str | None = None
    importance: str
    page_type: str


class WikiSection(BaseModel):
    title: str
    description: str | None = None
    pages: list[WikiPageSummary] = []
    subsections: list[WikiSection] = []


WikiSection.model_rebuild()


class WikiStructureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    repository_id: UUID
    branch: str
    scope_path: str
    version: int
    title: str
    description: str
    sections: list[WikiSection]
    commit_sha: str
    created_at: datetime


# For GET /jobs/{id}/tasks
class TaskState(BaseModel):
    task_name: str
    state: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None


# For GET /jobs/{id}/logs
class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str
    task_name: str | None = None
