# Flow Task Serialization Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace non-serializable objects (ORM models, WikiRepo, AgentResult) passed between Prefect tasks with typed Pydantic DTOs, fixing the crash in scope_processing_flow.

**Architecture:** Create `src/flows/schemas.py` with Pydantic BaseModel DTOs for all task inputs/outputs. Update each task to accept/return these DTOs. Update all flow callers to use them. Update integration tests to match new signatures.

**Tech Stack:** Pydantic BaseModel, Prefect 3 tasks, Python dataclasses (AutodocConfig stays as-is)

---

### Task 1: Create `src/flows/schemas.py` — Pydantic DTOs

**Files:**
- Create: `src/flows/schemas.py`
- Test: `tests/unit/test_flow_schemas.py`

**Step 1: Write the tests for schema serialization**

```python
"""Tests for flow inter-task Pydantic DTOs."""
from __future__ import annotations

import uuid

from src.flows.schemas import (
    CloneInput,
    PageTaskResult,
    PrRepositoryInfo,
    ReadmeTaskResult,
    ScopeProcessingResult,
    StructureTaskResult,
    TokenUsageResult,
)


class TestTokenUsageResult:
    def test_defaults(self):
        t = TokenUsageResult()
        assert t.input_tokens == 0
        assert t.calls == 0

    def test_from_values(self):
        t = TokenUsageResult(input_tokens=100, output_tokens=50, total_tokens=150, calls=2)
        assert t.total_tokens == 150


class TestStructureTaskResult:
    def test_roundtrip_json(self):
        r = StructureTaskResult(
            final_score=8.5,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=100, output_tokens=50, total_tokens=150, calls=1),
            output_title="Test",
            output_description="Desc",
            sections_json=[{"title": "Core", "pages": [], "subsections": []}],
        )
        data = r.model_dump(mode="json")
        restored = StructureTaskResult.model_validate(data)
        assert restored.final_score == 8.5
        assert restored.sections_json[0]["title"] == "Core"

    def test_nullable_output(self):
        r = StructureTaskResult(
            final_score=0.0,
            passed_quality_gate=False,
            below_minimum_floor=True,
            attempts=3,
            token_usage=TokenUsageResult(),
        )
        assert r.output_title is None
        assert r.sections_json is None


class TestPageTaskResult:
    def test_roundtrip_json(self):
        r = PageTaskResult(
            page_key="core-overview",
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=80, output_tokens=40, total_tokens=120, calls=1),
        )
        data = r.model_dump(mode="json")
        restored = PageTaskResult.model_validate(data)
        assert restored.page_key == "core-overview"


class TestReadmeTaskResult:
    def test_roundtrip_json(self):
        r = ReadmeTaskResult(
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            content="# README",
            token_usage=TokenUsageResult(),
        )
        assert r.content == "# README"


class TestCloneInput:
    def test_from_values(self):
        c = CloneInput(url="https://github.com/org/repo", provider="github", access_token="tok")
        assert c.provider == "github"

    def test_optional_token(self):
        c = CloneInput(url="https://github.com/org/repo", provider="github")
        assert c.access_token is None


class TestPrRepositoryInfo:
    def test_from_values(self):
        p = PrRepositoryInfo(
            url="https://github.com/org/repo",
            provider="github",
            name="repo",
            public_branch="main",
        )
        assert p.name == "repo"


class TestScopeProcessingResult:
    def test_defaults(self):
        r = ScopeProcessingResult()
        assert r.structure_result is None
        assert r.page_results == []
        assert r.readme_result is None
        assert r.embedding_count == 0

    def test_full(self):
        r = ScopeProcessingResult(
            structure_result=StructureTaskResult(
                final_score=8.5,
                passed_quality_gate=True,
                below_minimum_floor=False,
                attempts=1,
                token_usage=TokenUsageResult(),
            ),
            page_results=[
                PageTaskResult(
                    page_key="p1",
                    final_score=7.0,
                    passed_quality_gate=True,
                    below_minimum_floor=False,
                    attempts=1,
                    token_usage=TokenUsageResult(),
                ),
            ],
            wiki_structure_id=uuid.uuid4(),
            embedding_count=10,
        )
        assert len(r.page_results) == 1

    def test_roundtrip_json(self):
        sid = uuid.uuid4()
        r = ScopeProcessingResult(wiki_structure_id=sid, embedding_count=5)
        data = r.model_dump(mode="json")
        restored = ScopeProcessingResult.model_validate(data)
        assert restored.wiki_structure_id == sid
```

**Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_flow_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.flows.schemas'`

**Step 3: Create `src/flows/schemas.py`**

```python
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
```

**Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_flow_schemas.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/flows/schemas.py tests/unit/test_flow_schemas.py
git commit -m "feat: add Pydantic DTOs for inter-task data passing"
```

---

### Task 2: Update `clone_repository` task — accept `CloneInput` instead of Repository ORM

**Files:**
- Modify: `src/flows/tasks/clone.py` (lines 1-43)
- Test: `tests/unit/test_flow_schemas.py` (already tested schema)

**Step 1: Update `clone.py` to use `CloneInput`**

Replace the full file content. Key changes:
- Import `CloneInput` from `src.flows.schemas` instead of `Repository` from ORM
- Change signature: `clone_input: CloneInput` replaces `repository: Repository`
- Access fields via `clone_input.url`, `clone_input.provider`, `clone_input.access_token`

```python
from __future__ import annotations

import logging
import tempfile

from prefect import task

from src.flows.schemas import CloneInput
from src.providers.base import get_provider

logger = logging.getLogger(__name__)


@task(name="clone_repository", retries=2, retry_delay_seconds=10)
async def clone_repository(clone_input: CloneInput, branch: str) -> tuple[str, str]:
    """Clone a repository to a temporary directory.

    Args:
        clone_input: Serializable repository info for cloning.
        branch: Branch to clone.

    Returns:
        Tuple of (repo_path, commit_sha).
    """
    provider = get_provider(clone_input.provider)
    dest_dir = tempfile.mkdtemp(prefix="autodoc_")

    repo_path, commit_sha = await provider.clone_repository(
        url=clone_input.url,
        branch=branch,
        access_token=clone_input.access_token,
        dest_dir=dest_dir,
    )

    logger.info(
        "Cloned %s branch=%s to %s (sha=%s)",
        clone_input.url,
        branch,
        repo_path,
        commit_sha[:8],
    )
    return repo_path, commit_sha
```

**Step 2: Run existing tests to check nothing else breaks yet**

Run: `uv run pytest tests/unit/ -v -x`
Expected: PASS (clone task is mocked in integration tests, unit tests don't test it directly)

**Step 3: Commit**

```bash
git add src/flows/tasks/clone.py
git commit -m "refactor: clone_repository accepts CloneInput instead of Repository ORM"
```

---

### Task 3: Update `extract_structure` task — accept `AutodocConfig` directly, return `StructureTaskResult`

**Files:**
- Modify: `src/flows/tasks/structure.py` (lines 25-123)

**Step 1: Update `structure.py`**

Key changes:
- Import `StructureTaskResult`, `TokenUsageResult` from `src.flows.schemas`
- Change `config_dict: dict` to `config: AutodocConfig` (remove `autodoc_config_from_dict` call)
- Return `StructureTaskResult` instead of raw dict
- Keep internal DB session creation (task is self-contained)

```python
from __future__ import annotations

import logging
import uuid
from dataclasses import asdict

from prefect import task

from src.agents.structure_extractor import (
    StructureExtractor,
    StructureExtractorInput,
    WikiStructureSpec,
)
from src.config.settings import get_settings
from src.flows.schemas import StructureTaskResult, TokenUsageResult
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


def _structure_spec_to_sections_json(spec: WikiStructureSpec) -> list[dict]:
    """Convert WikiStructureSpec.sections to JSON-serializable structure for DB storage."""
    return [asdict(s) for s in spec.sections]


@task(name="extract_structure", timeout_seconds=600)
async def extract_structure(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    scope_path: str,
    commit_sha: str,
    file_list: list[str],
    repo_path: str,
    config: AutodocConfig,
    readme_content: str = "",
) -> StructureTaskResult:
    """Run StructureExtractor agent and save result to database.

    Creates a DatabaseSessionService session (user_id=job_id), runs
    StructureExtractor with file list and config, saves WikiStructure
    to DB via WikiRepo (enforce version retention).

    Returns:
        StructureTaskResult with quality metadata and sections JSON.
    """
    settings = get_settings()

    # Create ADK DatabaseSessionService
    db_url = settings.DATABASE_URL.replace("+asyncpg", "")

    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    session_id = f"structure-{job_id}-{scope_path}-{uuid.uuid4().hex[:8]}"

    agent = StructureExtractor()
    input_data = StructureExtractorInput(
        file_list=file_list,
        repo_path=repo_path,
        readme_content=readme_content,
        custom_instructions=config.custom_instructions,
        style_audience=config.style.audience,
        style_tone=config.style.tone,
        style_detail_level=config.style.detail_level,
    )

    result = await agent.run(
        input_data=input_data,
        session_service=session_service,
        session_id=session_id,
    )

    sections_json = None
    if result.output is not None:
        sections_json = _structure_spec_to_sections_json(result.output)

        # Save to database with own session
        from src.database.engine import get_session_factory
        from src.database.repos.wiki_repo import WikiRepo

        session_factory = get_session_factory()
        async with session_factory() as session:
            wiki_repo = WikiRepo(session)
            await wiki_repo.create_structure(
                repository_id=repository_id,
                job_id=job_id,
                branch=branch,
                scope_path=scope_path,
                title=result.output.title,
                description=result.output.description,
                sections=sections_json,
                commit_sha=commit_sha,
            )
            await session.commit()

        logger.info(
            "Saved wiki structure for %s/%s (score=%.2f, attempts=%d)",
            branch,
            scope_path,
            result.final_score,
            result.attempts,
        )

    return StructureTaskResult(
        final_score=result.final_score,
        passed_quality_gate=result.passed_quality_gate,
        below_minimum_floor=result.below_minimum_floor,
        attempts=result.attempts,
        token_usage=TokenUsageResult(
            input_tokens=result.token_usage.input_tokens,
            output_tokens=result.token_usage.output_tokens,
            total_tokens=result.token_usage.total_tokens,
            calls=result.token_usage.calls,
        ),
        output_title=result.output.title if result.output else None,
        output_description=result.output.description if result.output else None,
        sections_json=sections_json,
    )
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/tasks/structure.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/tasks/structure.py
git commit -m "refactor: extract_structure accepts AutodocConfig, returns StructureTaskResult"
```

---

### Task 4: Update `generate_pages` task — accept `StructureTaskResult` + `AutodocConfig`, return `list[PageTaskResult]`

**Files:**
- Modify: `src/flows/tasks/pages.py` (lines 50-157)

**Step 1: Update `pages.py`**

Key changes:
- Import `StructureTaskResult`, `PageTaskResult`, `TokenUsageResult` from schemas
- Change signature: `structure_result: StructureTaskResult` + `config: AutodocConfig` replace the scattered params
- Use `_reconstruct_page_specs(structure_result.sections_json)` internally
- Return `list[PageTaskResult]` instead of `list[dict]`
- Keep `_collect_page_specs` and `_reconstruct_page_specs` helpers (used by incremental flow too)

```python
from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.page_generator import (
    PageGenerator,
    PageGeneratorInput,
)
from src.agents.structure_extractor.schemas import PageSpec, SectionSpec
from src.config.settings import get_settings
from src.database.models.wiki_page import WikiPage
from src.flows.schemas import PageTaskResult, StructureTaskResult, TokenUsageResult
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


def _collect_page_specs(sections: list[SectionSpec]) -> list[PageSpec]:
    """Recursively collect all PageSpecs from nested sections."""
    pages: list[PageSpec] = []
    for section in sections:
        pages.extend(section.pages)
        pages.extend(_collect_page_specs(section.subsections))
    return pages


def _reconstruct_page_specs(sections_json: list[dict]) -> list[PageSpec]:
    """Reconstruct PageSpec list from sections JSONB."""
    specs: list[PageSpec] = []
    for section in sections_json:
        for page in section.get("pages", []):
            specs.append(
                PageSpec(
                    page_key=page["page_key"],
                    title=page["title"],
                    description=page.get("description", ""),
                    importance=page.get("importance", "medium"),
                    page_type=page.get("page_type", "overview"),
                    source_files=page.get("source_files", []),
                    related_pages=page.get("related_pages", []),
                )
            )
        for sub in section.get("subsections", []):
            specs.extend(_reconstruct_page_specs([sub]))
    return specs


@task(name="generate_pages", timeout_seconds=1800)
async def generate_pages(
    *,
    job_id: uuid.UUID,
    wiki_structure_id: uuid.UUID,
    structure_result: StructureTaskResult,
    repo_path: str,
    config: AutodocConfig,
) -> list[PageTaskResult]:
    """Generate wiki pages for all page specs in the structure.

    Iterates page specs from the structure result's sections JSON, runs
    PageGenerator agent for each page. Each WikiPage is saved atomically
    (partial results persist on failure).

    Returns:
        List of PageTaskResult with quality metadata per page.
    """
    settings = get_settings()

    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    page_specs = _reconstruct_page_specs(structure_result.sections_json or [])
    results: list[PageTaskResult] = []

    for page_spec in page_specs:
        session_id = f"page-{job_id}-{page_spec.page_key}-{uuid.uuid4().hex[:8]}"

        agent = PageGenerator()
        input_data = PageGeneratorInput(
            page_key=page_spec.page_key,
            title=page_spec.title,
            description=page_spec.description,
            importance=page_spec.importance,
            page_type=page_spec.page_type,
            source_files=page_spec.source_files,
            repo_path=repo_path,
            related_pages=page_spec.related_pages,
            custom_instructions=config.custom_instructions,
            style_audience=config.style.audience,
            style_tone=config.style.tone,
            style_detail_level=config.style.detail_level,
        )

        try:
            result = await agent.run(
                input_data=input_data,
                session_service=session_service,
                session_id=session_id,
            )

            # Save page to DB atomically with own session
            if result.output is not None:
                from src.database.engine import get_session_factory
                from src.database.repos.wiki_repo import WikiRepo

                session_factory = get_session_factory()
                async with session_factory() as session:
                    wiki_repo = WikiRepo(session)
                    wiki_page = WikiPage(
                        wiki_structure_id=wiki_structure_id,
                        page_key=result.output.page_key,
                        title=result.output.title,
                        description=page_spec.description,
                        importance=page_spec.importance,
                        page_type=page_spec.page_type,
                        source_files=page_spec.source_files,
                        related_pages=page_spec.related_pages,
                        content=result.output.content,
                        quality_score=result.final_score,
                    )
                    await wiki_repo.create_pages([wiki_page])
                    await session.commit()

                logger.info(
                    "Generated page '%s' (score=%.2f, attempts=%d)",
                    page_spec.page_key,
                    result.final_score,
                    result.attempts,
                )

            results.append(PageTaskResult(
                page_key=result.output.page_key if result.output else page_spec.page_key,
                final_score=result.final_score,
                passed_quality_gate=result.passed_quality_gate,
                below_minimum_floor=result.below_minimum_floor,
                attempts=result.attempts,
                token_usage=TokenUsageResult(
                    input_tokens=result.token_usage.input_tokens,
                    output_tokens=result.token_usage.output_tokens,
                    total_tokens=result.token_usage.total_tokens,
                    calls=result.token_usage.calls,
                ),
            ))
        except Exception:
            logger.exception("Failed to generate page '%s'", page_spec.page_key)
            # Continue with remaining pages — partial results persist
            continue

    return results
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/tasks/pages.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/tasks/pages.py
git commit -m "refactor: generate_pages accepts StructureTaskResult, returns list[PageTaskResult]"
```

---

### Task 5: Update `distill_readme` task — accept `AutodocConfig` directly, return `ReadmeTaskResult`

**Files:**
- Modify: `src/flows/tasks/readme.py` (lines 18-91)

**Step 1: Update `readme.py`**

Key changes:
- Import `ReadmeTaskResult`, `TokenUsageResult` from schemas
- Change `config_dict: dict` to `config: AutodocConfig`
- Remove `autodoc_config_from_dict` call
- Return `ReadmeTaskResult` instead of raw dict

```python
from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.readme_distiller import (
    ReadmeDistiller,
    ReadmeDistillerInput,
)
from src.config.settings import get_settings
from src.flows.schemas import ReadmeTaskResult, TokenUsageResult
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


@task(name="distill_readme", timeout_seconds=600)
async def distill_readme(
    *,
    job_id: uuid.UUID,
    structure_title: str,
    structure_description: str,
    page_summaries: list[dict],
    config: AutodocConfig,
) -> ReadmeTaskResult:
    """Distill wiki pages into a README.

    Accepts page summaries as dicts and config as AutodocConfig
    for cross-process execution.

    Args:
        job_id: Job UUID (used as session user_id).
        structure_title: The wiki structure title.
        structure_description: The wiki structure description.
        page_summaries: List of dicts with keys: page_key, title, description, content.
        config: AutodocConfig instance.

    Returns:
        ReadmeTaskResult with README content and quality metadata.
    """
    settings = get_settings()

    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    session_id = f"readme-{job_id}-{uuid.uuid4().hex[:8]}"

    agent = ReadmeDistiller()
    input_data = ReadmeDistillerInput(
        wiki_pages=page_summaries,
        project_title=structure_title,
        project_description=structure_description,
        custom_instructions=config.custom_instructions,
        max_length=config.readme.max_length,
        include_toc=config.readme.include_toc,
        include_badges=config.readme.include_badges,
        style_audience=config.style.audience,
        style_tone=config.style.tone,
        style_detail_level=config.style.detail_level,
    )

    result = await agent.run(
        input_data=input_data,
        session_service=session_service,
        session_id=session_id,
    )

    logger.info(
        "Distilled README (score=%.2f, attempts=%d, length=%d chars)",
        result.final_score,
        result.attempts,
        len(result.output.content) if result.output else 0,
    )

    return ReadmeTaskResult(
        final_score=result.final_score,
        passed_quality_gate=result.passed_quality_gate,
        below_minimum_floor=result.below_minimum_floor,
        attempts=result.attempts,
        content=result.output.content if result.output else "",
        token_usage=TokenUsageResult(
            input_tokens=result.token_usage.input_tokens,
            output_tokens=result.token_usage.output_tokens,
            total_tokens=result.token_usage.total_tokens,
            calls=result.token_usage.calls,
        ),
    )
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/tasks/readme.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/tasks/readme.py
git commit -m "refactor: distill_readme accepts AutodocConfig, returns ReadmeTaskResult"
```

---

### Task 6: Update `generate_embeddings_task` — remove `wiki_repo` parameter

**Files:**
- Modify: `src/flows/tasks/embeddings.py` (already correct internally, but callers pass extra `wiki_repo`)

The task signature at `embeddings.py:16-19` already only accepts `wiki_structure_id: UUID` and creates its own DB session. No changes needed to this file. The callers will be fixed in Task 8.

**Step 1: Verify embeddings task is already correct**

Run: `uv run ruff check src/flows/tasks/embeddings.py`
Expected: No errors

**Step 2: Commit (skip — no changes needed)**

---

### Task 7: Update PR tasks — accept `PrRepositoryInfo` instead of Repository ORM

**Files:**
- Modify: `src/flows/tasks/pr.py` (lines 26-155)

**Step 1: Update `pr.py`**

Key changes:
- Import `PrRepositoryInfo` from schemas
- `close_stale_autodoc_prs` and `create_autodoc_pr`: change `repository: Repository` to `repo_info: PrRepositoryInfo`
- Access fields via `repo_info.url`, `repo_info.provider`, `repo_info.name`, `repo_info.access_token`, `repo_info.public_branch`
- `ScopeReadme` stays as-is (it uses `AutodocConfig` which is a serializable dataclass)

```python
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from prefect import task

from src.errors import TransientError
from src.flows.schemas import PrRepositoryInfo
from src.providers.base import get_provider
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


@dataclass
class ScopeReadme:
    """A README produced for a single documentation scope."""

    content: str
    config: AutodocConfig


@task(name="close_stale_autodoc_prs")
async def close_stale_autodoc_prs(
    *,
    repo_info: PrRepositoryInfo,
    branch: str,
) -> int:
    """Close open autodoc PRs matching branch pattern ``autodoc/{repo_name}-{branch}-*``.

    Returns count of closed PRs.
    """
    provider = get_provider(repo_info.provider)
    branch_pattern = f"autodoc/{repo_info.name}-{branch}-"

    count = await provider.close_stale_prs(
        url=repo_info.url,
        branch_pattern=branch_pattern,
        access_token=repo_info.access_token,
    )
    logger.info("Closed %d stale autodoc PRs for %s/%s", count, repo_info.name, branch)
    return count


@task(name="create_autodoc_pr", retries=1, retry_delay_seconds=5)
async def create_autodoc_pr(
    *,
    repo_info: PrRepositoryInfo,
    branch: str,
    job_id: uuid.UUID,
    scope_readmes: list[ScopeReadme],
    repo_path: str,
) -> str:
    """Create autodoc PR with README content from one or more scopes.

    1. Create branch: ``autodoc/{repo_name}-{branch}-{job_id_short}-{YYYY-MM-DD}``
    2. Write all README files to disk (each at its scope-relative output_path)
    3. Commit and push
    4. Create PR targeting default branch (``public_branch``)

    PR settings (auto_merge, reviewers) are taken from the first scope's config.

    Returns:
        PR URL.
    """
    import asyncio
    from datetime import UTC, datetime
    from urllib.parse import urlparse

    provider = get_provider(repo_info.provider)
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    job_short = str(job_id)[:8]
    pr_branch = f"autodoc/{repo_info.name}-{branch}-{job_short}-{today}"

    # Write all README files relative to their scope_path.
    added_paths: list[str] = []
    for scope_readme in scope_readmes:
        relative_readme = str(
            Path(scope_readme.config.scope_path) / scope_readme.config.readme.output_path
        )
        readme_path = Path(repo_path) / relative_readme
        readme_path.parent.mkdir(parents=True, exist_ok=True)
        readme_path.write_text(scope_readme.content, encoding="utf-8")
        added_paths.append(relative_readme)

    # Git operations
    async def _git(*args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise TransientError(f"git {args[0]} failed: {stderr.decode()}")
        return stdout.decode().strip()

    await _git("checkout", "-b", pr_branch)
    for path in added_paths:
        await _git("add", path)
    await _git("commit", "-m", f"docs: update documentation for {branch}")

    # Push — inject token for auth
    push_url = repo_info.url
    if repo_info.access_token:
        parsed = urlparse(repo_info.url)
        if repo_info.provider == "github":
            push_url = (
                f"https://{repo_info.access_token}@{parsed.hostname}{parsed.path}"
            )
        else:  # bitbucket
            push_url = (
                f"https://x-token-auth:{repo_info.access_token}"
                f"@{parsed.hostname}{parsed.path}"
            )

    await _git("push", push_url, pr_branch)

    # For PR config, use the first scope's settings
    pr_config = scope_readmes[0].config
    scope_count = len(scope_readmes)
    scope_list = ", ".join(sr.config.scope_path for sr in scope_readmes)

    pr_url = await provider.create_pull_request(
        url=repo_info.url,
        branch=pr_branch,
        target_branch=repo_info.public_branch,
        title=f"docs: update documentation for {branch}",
        body=(
            f"Automated documentation update generated by AutoDoc.\n\n"
            f"Job ID: {job_id}\n"
            f"Branch: {branch}\n"
            f"Scopes: {scope_count} ({scope_list})"
        ),
        access_token=repo_info.access_token,
        reviewers=pr_config.pull_request.reviewers or None,
        auto_merge=pr_config.pull_request.auto_merge,
    )

    logger.info("Created PR: %s (scopes: %s)", pr_url, scope_list)
    return pr_url
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/tasks/pr.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/tasks/pr.py
git commit -m "refactor: PR tasks accept PrRepositoryInfo instead of Repository ORM"
```

---

### Task 8: Update `aggregate_job_metrics` task — accept Pydantic DTOs, create own DB session

**Files:**
- Modify: `src/flows/tasks/metrics.py` (lines 1-136)

**Step 1: Update `metrics.py`**

Key changes:
- Accept `StructureTaskResult | None`, `list[PageTaskResult]`, `ReadmeTaskResult | None` instead of `AgentResult` objects
- Accept `job_id: UUID` instead of `job_repo: JobRepo` — create own session internally
- Keep logic the same, just read from Pydantic model attributes instead of AgentResult attributes

```python
from __future__ import annotations

import logging
import uuid

from prefect import task

from src.config.settings import get_settings
from src.flows.schemas import (
    PageTaskResult,
    ReadmeTaskResult,
    StructureTaskResult,
    TokenUsageResult,
)

logger = logging.getLogger(__name__)


@task(name="aggregate_job_metrics")
async def aggregate_job_metrics(
    *,
    job_id: uuid.UUID,
    structure_result: StructureTaskResult | None,
    page_results: list[PageTaskResult],
    readme_result: ReadmeTaskResult | None,
) -> dict:
    """Collect token usage and quality scores from all task results.

    Builds ``quality_report`` and ``token_usage`` JSONB objects, updates
    the job record via its own DB session.

    Returns the quality_report dict.
    """
    settings = get_settings()

    # Build token usage
    total_input = 0
    total_output = 0
    total_tokens = 0
    total_calls = 0
    by_agent: dict[str, dict] = {}

    if structure_result:
        tu = structure_result.token_usage
        total_input += tu.input_tokens
        total_output += tu.output_tokens
        total_tokens += tu.total_tokens
        total_calls += tu.calls
        by_agent["structure_extractor"] = tu.model_dump()

    page_input = 0
    page_output = 0
    page_tokens = 0
    page_calls = 0
    page_scores: list[dict] = []
    pages_below_floor = 0

    for pr in page_results:
        tu = pr.token_usage
        page_input += tu.input_tokens
        page_output += tu.output_tokens
        page_tokens += tu.total_tokens
        page_calls += tu.calls
        total_input += tu.input_tokens
        total_output += tu.output_tokens
        total_tokens += tu.total_tokens
        total_calls += tu.calls
        page_scores.append(
            {
                "page_key": pr.page_key,
                "score": pr.final_score,
                "passed": pr.passed_quality_gate,
                "attempts": pr.attempts,
                "below_minimum_floor": pr.below_minimum_floor,
            }
        )
        if pr.below_minimum_floor:
            pages_below_floor += 1

    by_agent["page_generator"] = {
        "input_tokens": page_input,
        "output_tokens": page_output,
        "total_tokens": page_tokens,
        "calls": page_calls,
    }

    if readme_result:
        tu = readme_result.token_usage
        total_input += tu.input_tokens
        total_output += tu.output_tokens
        total_tokens += tu.total_tokens
        total_calls += tu.calls
        by_agent["readme_distiller"] = tu.model_dump()

    # Compute overall score (average across all results)
    all_scores: list[float] = []
    if structure_result:
        all_scores.append(structure_result.final_score)
    all_scores.extend(pr.final_score for pr in page_results)
    if readme_result:
        all_scores.append(readme_result.final_score)

    overall_score = sum(all_scores) / len(all_scores) if all_scores else 0.0

    quality_report: dict = {
        "overall_score": round(overall_score, 2),
        "quality_threshold": settings.QUALITY_THRESHOLD,
        "passed": overall_score >= settings.QUALITY_THRESHOLD
        and pages_below_floor == 0,
        "total_pages": len(page_results),
        "pages_below_floor": pages_below_floor,
        "page_scores": page_scores,
        "structure_score": {
            "score": structure_result.final_score,
            "passed": structure_result.passed_quality_gate,
            "attempts": structure_result.attempts,
        }
        if structure_result
        else None,
        "readme_score": {
            "score": readme_result.final_score,
            "passed": readme_result.passed_quality_gate,
            "attempts": readme_result.attempts,
        }
        if readme_result
        else None,
    }

    token_usage_report: dict = {
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "by_agent": by_agent,
    }

    # Update job record via own DB session
    from src.database.engine import get_session_factory
    from src.database.repos.job_repo import JobRepo

    session_factory = get_session_factory()
    async with session_factory() as session:
        job_repo = JobRepo(session)
        job = await job_repo.get_by_id(job_id)
        if job is not None:
            job.quality_report = quality_report
            job.token_usage = token_usage_report
            await session.flush()
        await session.commit()

    logger.info(
        "Aggregated metrics: overall=%.2f, pages=%d, tokens=%d",
        overall_score,
        len(page_results),
        total_tokens,
    )

    return quality_report
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/tasks/metrics.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/tasks/metrics.py
git commit -m "refactor: aggregate_job_metrics accepts Pydantic DTOs, creates own DB session"
```

---

### Task 9: Update `scope_processing_flow` — use typed DTOs throughout

**Files:**
- Modify: `src/flows/scope_processing.py` (lines 58-169)

**Step 1: Update `scope_processing.py`**

Key changes:
- Remove `wiki_repo: WikiRepo` parameter — flow creates its own DB session for the queries it needs (get_latest_structure, get_pages_for_structure)
- Pass `config: AutodocConfig` directly to tasks (not `config_dict`)
- Pass `StructureTaskResult` to `generate_pages`
- Build `page_summaries: list[dict]` from DB wiki_pages for `distill_readme`
- Return `ScopeProcessingResult` instead of raw dict
- Remove `AgentResult` imports — no longer used at flow level

```python
from __future__ import annotations

import asyncio
import logging
import os
import uuid

from prefect import flow

from src.database.engine import get_session_factory
from src.database.repos.wiki_repo import WikiRepo
from src.flows.schemas import (
    ReadmeTaskResult,
    ScopeProcessingResult,
    StructureTaskResult,
)
from src.flows.tasks.embeddings import generate_embeddings_task
from src.flows.tasks.pages import generate_pages
from src.flows.tasks.readme import distill_readme
from src.flows.tasks.structure import extract_structure
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)

# Common README filenames in priority order
_README_CANDIDATES = [
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "readme.md",
    "Readme.md",
]


def read_readme(repo_path: str) -> str:
    """Read the repository README file if it exists.

    Tries common README filenames in priority order and returns the content
    of the first one found. Returns empty string if no README is found.

    Args:
        repo_path: Absolute path to the cloned repository.

    Returns:
        README content as a string, or empty string if not found.
    """
    for candidate in _README_CANDIDATES:
        readme_path = os.path.join(repo_path, candidate)
        try:
            with open(readme_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            logger.info("Found README at %s", readme_path)
            return content
        except OSError:
            continue
    logger.info("No README found in %s", repo_path)
    return ""


@flow(name="scope_processing", timeout_seconds=3600)
async def scope_processing_flow(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    scope_path: str,
    commit_sha: str,
    repo_path: str,
    config: AutodocConfig,
    dry_run: bool = False,
) -> ScopeProcessingResult:
    """Process a single documentation scope.

    Pipeline: extract_structure -> (if not dry_run: generate_pages -> (distill_readme || generate_embeddings))

    If structure quality gate fails (below_minimum_floor), raises QualityError
    to skip page generation.

    Args:
        repository_id: Repository UUID.
        job_id: Job UUID.
        branch: Target branch.
        scope_path: Documentation scope path (e.g. ".").
        commit_sha: Current commit SHA.
        repo_path: Path to cloned repository.
        config: AutodocConfig for this scope.
        dry_run: If True, only extract structure (skip pages + readme).

    Returns:
        ScopeProcessingResult with all task results.
    """
    from src.errors import QualityError
    from src.flows.tasks.scan import scan_file_tree

    # Scan file tree for this scope
    file_list = await scan_file_tree(repo_path=repo_path, config=config)

    # Read README for structure extraction context
    readme_content = read_readme(repo_path)

    # Extract structure
    structure_result: StructureTaskResult = await extract_structure(
        repository_id=repository_id,
        job_id=job_id,
        branch=branch,
        scope_path=scope_path,
        commit_sha=commit_sha,
        file_list=file_list,
        repo_path=repo_path,
        config=config,
        readme_content=readme_content,
    )

    # Check structure quality gate
    if structure_result.below_minimum_floor:
        raise QualityError(
            f"Structure extraction below minimum floor for scope '{scope_path}' "
            f"(score={structure_result.final_score})"
        )

    # Get the wiki_structure_id from the database
    session_factory = get_session_factory()
    async with session_factory() as session:
        wiki_repo = WikiRepo(session)
        wiki_structure = await wiki_repo.get_latest_structure(
            repository_id=repository_id,
            branch=branch,
            scope_path=scope_path,
        )
    wiki_structure_id = wiki_structure.id if wiki_structure else None

    page_results = []
    readme_result: ReadmeTaskResult | None = None
    embedding_count: int = 0

    if not dry_run and structure_result.sections_json is not None and wiki_structure_id is not None:
        # Generate pages
        page_results = await generate_pages(
            job_id=job_id,
            wiki_structure_id=wiki_structure_id,
            structure_result=structure_result,
            repo_path=repo_path,
            config=config,
        )

        # Get generated wiki pages from DB for readme distillation
        async with session_factory() as session:
            wiki_repo = WikiRepo(session)
            wiki_pages = await wiki_repo.get_pages_for_structure(wiki_structure_id)

        # Build page summaries for readme distillation
        page_summaries = [
            {
                "page_key": p.page_key,
                "title": p.title,
                "description": p.description,
                "content": p.content,
            }
            for p in wiki_pages
        ]

        # Run README distillation and embedding generation in parallel
        readme_result, embedding_count = await asyncio.gather(
            distill_readme(
                job_id=job_id,
                structure_title=structure_result.output_title or "",
                structure_description=structure_result.output_description or "",
                page_summaries=page_summaries,
                config=config,
            ),
            generate_embeddings_task(
                wiki_structure_id=wiki_structure_id,
            ),
        )

    return ScopeProcessingResult(
        structure_result=structure_result,
        page_results=page_results,
        readme_result=readme_result,
        wiki_structure_id=wiki_structure_id,
        embedding_count=embedding_count,
    )
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/scope_processing.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/scope_processing.py
git commit -m "refactor: scope_processing_flow uses Pydantic DTOs, creates own DB sessions"
```

---

### Task 10: Update `full_generation_flow` — use typed DTOs and serializable inputs

**Files:**
- Modify: `src/flows/full_generation.py` (lines 1-291)

**Step 1: Update `full_generation.py`**

Key changes:
- Create `CloneInput` and `PrRepositoryInfo` from Repository ORM before passing to tasks
- Process `ScopeProcessingResult` instead of raw dicts
- Access `result.structure_result`, `result.page_results`, `result.readme_result` as typed Pydantic models
- Pass `StructureTaskResult`, `list[PageTaskResult]`, `ReadmeTaskResult` to `aggregate_job_metrics`
- Build `ScopeReadme` using `readme_result.content` from `ReadmeTaskResult`
- Remove `wiki_repo` from scope_processing_flow call

The full file is large (~290 lines). The key changes are:

1. **Line 75-78**: Create `CloneInput` from repository ORM:
```python
clone_input = CloneInput(
    url=repository.url,
    provider=repository.provider,
    access_token=repository.access_token,
)
repo_path, commit_sha = await clone_repository(
    clone_input=clone_input,
    branch=branch,
)
```

2. **Line 88-99**: Remove `wiki_repo` from scope_processing call:
```python
async def _process_scope(cfg):
    return await scope_processing_flow(
        repository_id=repository_id,
        job_id=job_id,
        branch=branch,
        scope_path=cfg.scope_path,
        commit_sha=commit_sha,
        repo_path=repo_path,
        config=cfg,
        dry_run=dry_run,
    )
```

3. **Lines 121-133**: Process typed `ScopeProcessingResult`:
```python
for i, result in enumerate(scope_results):
    if isinstance(result, Exception):
        logger.error("Scope '%s' failed: %s", configs[i].scope_path, result)
        continue

    sr = result.structure_result
    pr_list = result.page_results
    rr = result.readme_result

    if sr:
        all_structure_results.append(sr)
    all_page_results.extend(pr_list)
    if rr:
        all_readme_results.append(rr)
        scope_readmes.append(
            ScopeReadme(content=rr.content, config=configs[i])
        )
```

4. **Lines 138-149**: Create `PrRepositoryInfo` for PR tasks:
```python
repo_info = PrRepositoryInfo(
    url=repository.url,
    provider=repository.provider,
    name=repository.name,
    access_token=repository.access_token,
    public_branch=repository.public_branch,
)
await close_stale_autodoc_prs(repo_info=repo_info, branch=branch)
pr_url = await create_autodoc_pr(
    repo_info=repo_info,
    branch=branch,
    job_id=job_id,
    scope_readmes=scope_readmes,
    repo_path=repo_path,
)
```

5. **Lines 157-163**: Pass DTOs to `aggregate_job_metrics`:
```python
await aggregate_job_metrics(
    job_id=job_id,
    structure_result=structure_result,
    page_results=all_page_results,
    readme_result=readme_result,
)
```

6. **Lines 167-180**: Quality gate uses Pydantic attribute access (same names, just typed now):
```python
for sr in all_structure_results:
    if sr.below_minimum_floor:  # StructureTaskResult attribute
        any_below_floor = True
        break
```

**Step 2: Run linter**

Run: `uv run ruff check src/flows/full_generation.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/full_generation.py
git commit -m "refactor: full_generation_flow uses CloneInput, PrRepositoryInfo, ScopeProcessingResult"
```

---

### Task 11: Update `incremental_update_flow` — use typed DTOs

**Files:**
- Modify: `src/flows/incremental_update.py` (lines 1-713)

**Step 1: Update `incremental_update.py`**

Key changes:
- Same pattern as full_generation: `CloneInput`, `PrRepositoryInfo`
- `_process_incremental_scope` returns `ScopeProcessingResult` instead of raw dict
- `_process_incremental_scope` creates its own DB sessions for wiki_repo operations
- Remove `wiki_repo` parameter from `_process_incremental_scope`
- Pass `StructureTaskResult` to `generate_pages`
- Build `page_summaries` for `distill_readme` from DB wiki_pages
- Process `ScopeProcessingResult` in the main flow

The changes follow the exact same pattern as Tasks 9 and 10. Key function signatures become:

```python
async def _process_incremental_scope(
    *,
    config: AutodocConfig,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    commit_sha: str,
    repo_path: str,
    changed_files_set: set[str],
    needs_structure_reextraction: bool,
    dry_run: bool,
) -> ScopeProcessingResult:
```

Note: `wiki_repo` removed — function creates its own session for DB operations (get_latest_structure, get_pages_for_structure, create_structure, duplicate_pages).

**Step 2: Run linter**

Run: `uv run ruff check src/flows/incremental_update.py`
Expected: No errors

**Step 3: Commit**

```bash
git add src/flows/incremental_update.py
git commit -m "refactor: incremental_update_flow uses Pydantic DTOs, no WikiRepo passing"
```

---

### Task 12: Update integration tests

**Files:**
- Modify: `tests/integration/test_flows.py` (lines 1-1800+)

**Step 1: Update mock factories and test assertions**

Key changes:
1. Replace `AgentResult`-based mock returns with `StructureTaskResult`, `PageTaskResult`, `ReadmeTaskResult`:

```python
from src.flows.schemas import (
    CloneInput,
    PageTaskResult,
    PrRepositoryInfo,
    ReadmeTaskResult,
    ScopeProcessingResult,
    StructureTaskResult,
    TokenUsageResult,
)

def _make_structure_task_result(below_floor: bool = False) -> StructureTaskResult:
    return StructureTaskResult(
        final_score=8.5,
        passed_quality_gate=True,
        below_minimum_floor=below_floor,
        attempts=1,
        token_usage=TokenUsageResult(input_tokens=1000, output_tokens=500, total_tokens=1500, calls=2),
        output_title="Test Project",
        output_description="Test project documentation",
        sections_json=[{
            "title": "Core",
            "description": "Core module docs",
            "pages": [{
                "page_key": "core-overview",
                "title": "Core Overview",
                "description": "Overview of core module",
                "importance": "high",
                "page_type": "overview",
                "source_files": ["src/core.py"],
                "related_pages": [],
            }],
            "subsections": [],
        }],
    )

def _make_page_task_result(page_key: str = "core-overview", below_floor: bool = False) -> PageTaskResult:
    return PageTaskResult(
        page_key=page_key,
        final_score=8.0,
        passed_quality_gate=True,
        below_minimum_floor=below_floor,
        attempts=1,
        token_usage=TokenUsageResult(input_tokens=800, output_tokens=400, total_tokens=1200, calls=2),
    )

def _make_readme_task_result(below_floor: bool = False) -> ReadmeTaskResult:
    return ReadmeTaskResult(
        final_score=8.0,
        passed_quality_gate=True,
        below_minimum_floor=below_floor,
        attempts=1,
        content="# Test Project\n\nA great project.",
        token_usage=TokenUsageResult(input_tokens=600, output_tokens=300, total_tokens=900, calls=2),
    )
```

2. Replace `scope_result` dicts with `ScopeProcessingResult`:

```python
scope_result = ScopeProcessingResult(
    structure_result=_make_structure_task_result(),
    page_results=[_make_page_task_result()],
    readme_result=_make_readme_task_result(),
    wiki_structure_id=wiki_structure.id,
    embedding_count=5,
)
```

3. Update `aggregate_job_metrics` mock patches to match new signature (no `job_repo` param).

4. Update PR task mock patches: `close_stale_autodoc_prs` and `create_autodoc_pr` now receive `repo_info` keyword.

5. Keep old `_make_*_result()` helpers if they are used elsewhere (e.g. for verifying internal agent logic), but add the new `_make_*_task_result()` helpers for flow-level tests.

**Step 2: Run all tests**

Run: `uv run pytest tests/ -v -x`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/integration/test_flows.py
git commit -m "test: update flow integration tests for Pydantic DTO signatures"
```

---

### Task 13: Run full test suite and lint

**Step 1: Run linter on all changed files**

Run: `uv run ruff check src/flows/ tests/`
Expected: No errors

**Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 3: Final commit (if any lint fixes needed)**

```bash
git add -A
git commit -m "chore: lint fixes for flow task serialization refactor"
```
