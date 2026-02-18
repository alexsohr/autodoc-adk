"""Shared fixtures for API integration tests.

Provides a FastAPI test application with mocked database dependencies,
an async HTTPX test client, and reusable mock repo fixtures.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from src.api.app import create_app
from src.api.dependencies import (
    get_job_repo,
    get_repository_repo,
    get_search_repo,
    get_wiki_repo,
)

# ---------------------------------------------------------------------------
# Stable IDs used across tests
# ---------------------------------------------------------------------------

REPO_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
REPO_ID_2 = uuid.UUID("00000000-0000-4000-8000-000000000002")
UNKNOWN_ID = uuid.UUID("00000000-0000-4000-8000-ffffffffffff")
JOB_ID = uuid.UUID("00000000-0000-4000-8000-000000000010")
JOB_ID_2 = uuid.UUID("00000000-0000-4000-8000-000000000011")
STRUCTURE_ID = uuid.UUID("00000000-0000-4000-8000-000000000020")

NOW = datetime(2026, 2, 17, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def make_repository(
    repo_id: uuid.UUID = REPO_ID,
    url: str = "https://github.com/acme/widgets",
    provider: str = "github",
    org: str = "acme",
    name: str = "widgets",
    branch_mappings: dict[str, str] | None = None,
    public_branch: str = "main",
) -> SimpleNamespace:
    """Return a lightweight repository-like object."""
    return SimpleNamespace(
        id=repo_id,
        url=url,
        provider=provider,
        org=org,
        name=name,
        branch_mappings=branch_mappings or {"main": "main", "develop": "develop"},
        public_branch=public_branch,
        access_token=None,
        created_at=NOW,
        updated_at=NOW,
    )


def make_job(
    job_id: uuid.UUID = JOB_ID,
    repository_id: uuid.UUID = REPO_ID,
    status: str = "PENDING",
    mode: str = "full",
    branch: str = "main",
    force: bool = False,
    dry_run: bool = False,
    prefect_flow_run_id: str | None = None,
    callback_url: str | None = None,
    error_message: str | None = None,
    pull_request_url: str | None = None,
    **overrides: object,
) -> SimpleNamespace:
    """Return a lightweight job-like object."""
    fields = dict(
        id=job_id,
        repository_id=repository_id,
        status=status,
        mode=mode,
        branch=branch,
        commit_sha=None,
        force=force,
        dry_run=dry_run,
        prefect_flow_run_id=prefect_flow_run_id,
        app_commit_sha="abc123",
        quality_report=None,
        token_usage=None,
        config_warnings=None,
        callback_url=callback_url,
        error_message=error_message,
        pull_request_url=pull_request_url,
        created_at=NOW,
        updated_at=NOW,
    )
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _default_sections_dict() -> dict:
    """Return raw sections dict as stored in the database (used by document routes)."""
    return {
        "sections": [
            {
                "title": "Getting Started",
                "description": "Introduction and setup",
                "pages": [
                    {
                        "page_key": "getting-started/overview",
                        "title": "Overview",
                        "description": "Project overview",
                        "importance": "high",
                        "page_type": "overview",
                    },
                ],
                "subsections": [],
            },
            {
                "title": "API Reference",
                "description": "REST API documentation",
                "pages": [
                    {
                        "page_key": "api/endpoints",
                        "title": "Endpoints",
                        "description": "REST endpoints",
                        "importance": "medium",
                        "page_type": "api",
                    },
                ],
                "subsections": [],
            },
        ],
    }


def make_structure(
    structure_id: uuid.UUID = STRUCTURE_ID,
    repository_id: uuid.UUID = REPO_ID,
    scope_path: str = ".",
    version: int = 1,
) -> SimpleNamespace:
    """Return a lightweight wiki-structure-like object.

    The ``sections`` field uses the raw dict format as stored in the DB.
    This is appropriate for document routes which parse sections manually.
    For the ``/jobs/{id}/structure`` endpoint (which calls ``model_validate``
    on ``WikiStructureResponse``), use :func:`make_structure_for_response`.
    """
    return SimpleNamespace(
        id=structure_id,
        repository_id=repository_id,
        branch="main",
        scope_path=scope_path,
        version=version,
        title="Root Documentation",
        description="Auto-generated documentation for the repository.",
        sections=_default_sections_dict(),
        commit_sha="a1b2c3d4e5f6" * 3 + "a1b2c3d4",
        created_at=NOW,
    )


def make_structure_for_response(
    structure_id: uuid.UUID = STRUCTURE_ID,
    repository_id: uuid.UUID = REPO_ID,
    scope_path: str = ".",
    version: int = 1,
) -> SimpleNamespace:
    """Return a structure object compatible with WikiStructureResponse.model_validate.

    The ``sections`` field is a list (not a dict) matching the Pydantic schema.
    """
    return SimpleNamespace(
        id=structure_id,
        repository_id=repository_id,
        branch="main",
        scope_path=scope_path,
        version=version,
        title="Root Documentation",
        description="Auto-generated documentation for the repository.",
        sections=_default_sections_dict()["sections"],
        commit_sha="a1b2c3d4e5f6" * 3 + "a1b2c3d4",
        created_at=NOW,
    )


def make_page(
    page_key: str = "getting-started/overview",
    wiki_structure_id: uuid.UUID = STRUCTURE_ID,
) -> SimpleNamespace:
    """Return a lightweight wiki-page-like object."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        wiki_structure_id=wiki_structure_id,
        page_key=page_key,
        title="Overview",
        description="Project overview",
        importance="high",
        page_type="overview",
        content="# Overview\n\nThis is the project overview.",
        source_files=["src/main.py", "src/utils.py"],
        related_pages=["api/endpoints"],
        quality_score=8.5,
    )


# ---------------------------------------------------------------------------
# Application fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> FastAPI:
    """Create a fresh FastAPI application (no real lifespan side-effects)."""
    return create_app()


# ---------------------------------------------------------------------------
# Mock repository fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_repository_repo() -> AsyncMock:
    """Mock RepositoryRepo with common defaults."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_url = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=make_repository())
    repo.list = AsyncMock(return_value=[])
    repo.update = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=False)
    return repo


@pytest.fixture()
def mock_job_repo() -> AsyncMock:
    """Mock JobRepo with common defaults."""
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_active_for_repo = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=make_job())
    repo.list = AsyncMock(return_value=[])
    repo.update_status = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
def mock_wiki_repo() -> AsyncMock:
    """Mock WikiRepo with common defaults."""
    repo = AsyncMock()
    repo.get_latest_structure = AsyncMock(return_value=None)
    repo.get_structures_for_repo = AsyncMock(return_value=[])
    repo.count_pages_for_structure = AsyncMock(return_value=0)
    repo.get_page_by_key = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
def mock_search_repo() -> AsyncMock:
    """Mock SearchRepo with common defaults."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# Async HTTPX test client
# ---------------------------------------------------------------------------


@pytest.fixture()
async def client(
    app: FastAPI,
    mock_repository_repo: AsyncMock,
    mock_job_repo: AsyncMock,
    mock_wiki_repo: AsyncMock,
    mock_search_repo: AsyncMock,
) -> httpx.AsyncClient:
    """Yield an async HTTPX client wired to the test app with all deps mocked."""
    app.dependency_overrides[get_repository_repo] = lambda: mock_repository_repo
    app.dependency_overrides[get_job_repo] = lambda: mock_job_repo
    app.dependency_overrides[get_wiki_repo] = lambda: mock_wiki_repo
    app.dependency_overrides[get_search_repo] = lambda: mock_search_repo

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
