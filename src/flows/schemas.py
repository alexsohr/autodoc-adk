"""Pydantic DTOs for inter-task data passing in Prefect flows.

All objects in this module are JSON-serializable and safe for cross-process
execution. They replace the raw dicts and non-serializable objects (ORM models,
WikiRepo, AgentResult) that were previously passed between tasks.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TokenUsageResult(BaseModel):
    """Token usage from an agent run."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0


class StructureTaskResult(BaseModel):
    """Return type for the extract_structure task."""

    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    attempts: int
    token_usage: TokenUsageResult
    output_title: str | None = None
    output_description: str | None = None
    sections_json: list[dict] | None = None


class PageTaskResult(BaseModel):
    """Return type for a single page result from generate_pages."""

    page_key: str
    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    attempts: int
    token_usage: TokenUsageResult


class ReadmeTaskResult(BaseModel):
    """Return type for the distill_readme task."""

    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    attempts: int
    content: str
    token_usage: TokenUsageResult


class CloneInput(BaseModel):
    """Serializable subset of Repository ORM for clone_repository task."""

    url: str
    provider: str
    access_token: str | None = None


class PrRepositoryInfo(BaseModel):
    """Serializable subset of Repository ORM for PR tasks."""

    url: str
    provider: str
    name: str
    access_token: str | None = None
    public_branch: str


class ScopeProcessingResult(BaseModel):
    """Return type for scope_processing_flow and _process_incremental_scope."""

    structure_result: StructureTaskResult | None = None
    page_results: list[PageTaskResult] = []
    readme_result: ReadmeTaskResult | None = None
    wiki_structure_id: UUID | None = None
    embedding_count: int = 0
    regenerated_page_keys: list[str] = []
