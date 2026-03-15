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
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "summary": "Full generation",
                    "value": {
                        "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "branch": "main",
                        "force": True,
                        "dry_run": False,
                        "callback_url": "https://example.com/webhooks/autodoc",
                    },
                },
                {
                    "summary": "Incremental dry run",
                    "value": {
                        "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "branch": None,
                        "force": False,
                        "dry_run": True,
                        "callback_url": None,
                    },
                },
            ]
        }
    )

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
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "status": "COMPLETED",
                "mode": "full",
                "branch": "main",
                "commit_sha": "a3f5b8c1d2e4f6a7b9c0d1e2f3a4b5c6d7e8f9a0",
                "force": False,
                "dry_run": False,
                "quality_report": {
                    "overall_score": 8.2,
                    "quality_threshold": 7.0,
                    "passed": True,
                    "total_pages": 12,
                    "pages_below_floor": 0,
                    "page_scores": [
                        {
                            "page_key": "getting-started/installation",
                            "score": 8.5,
                            "passed": True,
                            "attempts": 1,
                            "below_minimum_floor": False,
                            "criteria_scores": {
                                "accuracy": 9.0,
                                "completeness": 8.0,
                                "clarity": 8.5,
                            },
                        }
                    ],
                    "structure_score": {
                        "score": 8.8,
                        "passed": True,
                        "attempts": 1,
                        "criteria_scores": {
                            "coverage": 9.0,
                            "organization": 8.5,
                        },
                    },
                    "readme_score": {
                        "score": 7.9,
                        "passed": True,
                        "attempts": 2,
                        "criteria_scores": {
                            "accuracy": 8.0,
                            "completeness": 7.5,
                            "clarity": 8.2,
                        },
                    },
                    "regenerated_pages": None,
                    "no_changes": None,
                },
                "token_usage": {
                    "total_input_tokens": 125000,
                    "total_output_tokens": 45000,
                    "total_tokens": 170000,
                    "by_agent": {
                        "page_generator": {
                            "input_tokens": 80000,
                            "output_tokens": 30000,
                            "total_tokens": 110000,
                            "calls": 24,
                        }
                    },
                },
                "config_warnings": None,
                "pull_request_url": "https://github.com/acme/backend-api/pull/42",
                "error_message": None,
                "created_at": "2026-02-18T10:25:00Z",
                "updated_at": "2026-02-18T10:35:22Z",
            }
        },
    )

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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                        "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "status": "COMPLETED",
                        "mode": "full",
                        "branch": "main",
                        "commit_sha": "a3f5b8c1d2e4f6a7b9c0d1e2f3a4b5c6d7e8f9a0",
                        "force": False,
                        "dry_run": False,
                        "quality_report": None,
                        "token_usage": None,
                        "config_warnings": None,
                        "pull_request_url": None,
                        "error_message": None,
                        "created_at": "2026-02-18T10:25:00Z",
                        "updated_at": "2026-02-18T10:35:22Z",
                    }
                ],
                "next_cursor": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                "limit": 20,
            }
        }
    )

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
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "repository_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "branch": "main",
                "scope_path": ".",
                "version": 1,
                "title": "Backend API Documentation",
                "description": "Auto-generated documentation for the backend API service.",
                "sections": [
                    {
                        "title": "Getting Started",
                        "description": "Setup and installation guides.",
                        "pages": [
                            {
                                "page_key": "getting-started/installation",
                                "title": "Installation Guide",
                                "description": "Step-by-step installation instructions for local development.",
                                "importance": "high",
                                "page_type": "guide",
                            }
                        ],
                        "subsections": [],
                    }
                ],
                "commit_sha": "a3f5b8c1d2e4f6a7b9c0d1e2f3a4b5c6d7e8f9a0",
                "created_at": "2026-02-18T10:30:00Z",
            }
        },
    )

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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task_name": "generate_pages",
                "state": "Completed",
                "started_at": "2026-02-18T10:30:00Z",
                "completed_at": "2026-02-18T10:34:15Z",
                "message": None,
            }
        }
    )

    task_name: str
    state: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    message: str | None = None


# For GET /jobs/{id}/logs
class LogEntry(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-02-18T10:35:22Z",
                "level": "INFO",
                "message": "Generated 12 pages for scope '.'",
                "task_name": None,
            }
        }
    )

    timestamp: datetime
    level: str
    message: str
    task_name: str | None = None
