# Flow Task Serialization Fix

**Date**: 2026-02-18
**Status**: Approved
**Scope**: `src/flows/`, `src/flows/tasks/`

## Problem

Prefect `@task` functions in `src/flows/tasks/` have correctly designed JSON-serializable signatures, but the callers in `scope_processing.py`, `full_generation.py`, and `incremental_update.py` pass non-serializable objects (SQLAlchemy ORM models, `WikiRepo` instances, `AgentResult` dataclasses) with mismatched parameter names. This causes crashes in `scope_processing_flow` and prevents future distributed execution (K8s workers).

### Specific violations

| Task | Task Signature | What Callers Pass |
|------|---------------|-------------------|
| `clone_repository` | `repository: Repository` (ORM) | Repository ORM object (non-serializable across processes) |
| `extract_structure` | `config_dict: dict`, no `wiki_repo` | `config=AutodocConfig` object, `wiki_repo=WikiRepo` |
| `generate_pages` | `structure_sections_json`, `structure_title`, `structure_description`, `config_dict` | `structure_spec=WikiStructureSpec`, `config=AutodocConfig`, `wiki_repo=WikiRepo` |
| `distill_readme` | `structure_title`, `structure_description`, `page_summaries`, `config_dict` | `structure_spec=WikiStructureSpec`, `wiki_pages=list[WikiPage]`, `config=AutodocConfig` |
| `aggregate_job_metrics` | `AgentResult` objects + `job_repo: JobRepo` | Non-serializable objects |

Additionally, tasks return `dict` but callers treat returns as `AgentResult` objects (accessing `.below_minimum_floor`, `.output`, `.token_usage` attributes on dicts).

## Solution

Introduce Pydantic DTOs in `src/flows/schemas.py` as the typed, serializable contract between task callers and task functions. Fix all callers to use these types. Fix all tasks to accept and return these types.

### New file: `src/flows/schemas.py`

```python
from __future__ import annotations
from uuid import UUID
from pydantic import BaseModel

class TokenUsageResult(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

class StructureTaskResult(BaseModel):
    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    attempts: int
    token_usage: TokenUsageResult
    output_title: str | None = None
    output_description: str | None = None
    sections_json: list[dict] | None = None

class PageTaskResult(BaseModel):
    page_key: str
    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    attempts: int
    token_usage: TokenUsageResult

class ReadmeTaskResult(BaseModel):
    final_score: float
    passed_quality_gate: bool
    below_minimum_floor: bool
    attempts: int
    content: str
    token_usage: TokenUsageResult

class CloneInput(BaseModel):
    url: str
    provider: str
    access_token: str | None = None

class PrRepositoryInfo(BaseModel):
    url: str
    provider: str
    name: str
    access_token: str | None = None
    public_branch: str

class ScopeProcessingResult(BaseModel):
    structure_result: StructureTaskResult | None = None
    page_results: list[PageTaskResult] = []
    readme_result: ReadmeTaskResult | None = None
    wiki_structure_id: UUID | None = None
    embedding_count: int = 0
    regenerated_page_keys: list[str] = []
```

### Task signature changes

| Task | Current Input | New Input | Current Return | New Return |
|------|--------------|-----------|---------------|------------|
| `clone_repository` | `repository: Repository` | `clone_input: CloneInput` | `tuple[str, str]` | `tuple[str, str]` (no change) |
| `extract_structure` | `config_dict: dict` | `config: AutodocConfig` | `dict` | `StructureTaskResult` |
| `generate_pages` | `structure_sections_json`, `structure_title`, `structure_description`, `config_dict` | `structure_result: StructureTaskResult`, `config: AutodocConfig` | `list[dict]` | `list[PageTaskResult]` |
| `distill_readme` | `structure_title`, `structure_description`, `page_summaries`, `config_dict` | `structure_title`, `structure_description`, `page_summaries: list[dict]`, `config: AutodocConfig` | `dict` | `ReadmeTaskResult` |
| `generate_embeddings_task` | `wiki_structure_id: UUID` | No change | `int` | No change |
| `aggregate_job_metrics` | `AgentResult` + `JobRepo` | `StructureTaskResult` + `list[PageTaskResult]` + `ReadmeTaskResult` + `job_id: UUID` | `dict` | `dict` (quality_report JSONB) |

### Caller changes

**`scope_processing_flow`**:
- Receives `StructureTaskResult` from `extract_structure` (typed Pydantic, not dict or AgentResult)
- Access quality via `structure_result.below_minimum_floor` (same attribute names)
- Passes `StructureTaskResult` to `generate_pages`
- Builds `page_summaries` list[dict] from DB wiki_pages for `distill_readme`
- Returns `ScopeProcessingResult` instead of raw dict

**`full_generation_flow`**:
- Creates `CloneInput.from_repository(repo)` before calling `clone_repository`
- Creates `PrRepositoryInfo.from_repository(repo)` for PR tasks
- Processes `ScopeProcessingResult` from scope_processing
- Passes typed results to `aggregate_job_metrics`

**`incremental_update_flow`**:
- Same treatment as full_generation
- `_process_incremental_scope` returns `ScopeProcessingResult`

### What stays the same

- `AutodocConfig` passed directly to tasks (stdlib dataclass, pickle-serializable)
- `generate_embeddings_task` (already self-contained, UUID input, creates own session)
- Task internals (agent calls, DB session creation inside tasks)
- Agent schemas (`StructureExtractorInput`, `PageGeneratorInput`, `ReadmeDistillerInput`)
- `scan_file_tree` and `discover_autodoc_configs` (already correct)

### Key principle

Each `@task` is self-contained: accepts only serializable inputs, creates its own DB session if needed, returns a serializable Pydantic model. Flows orchestrate by passing these typed results between tasks.
