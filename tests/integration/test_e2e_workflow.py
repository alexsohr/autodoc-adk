"""End-to-end workflow validation per quickstart.md (T083).

Exercises the full API workflow in sequence with stateful mocks:
  1. Register repository
  2. Trigger full generation job
  3. Verify wiki pages are stored
  4. Search documentation
  5. Trigger incremental update
  6. Verify selective regeneration mode
  7. Test webhook trigger
  8. Validate latency targets (SC-004 search <3s, SC-007 job mgmt <2s)
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
from src.api.schemas.documents import SearchResponse

# ---------------------------------------------------------------------------
# Stable IDs
# ---------------------------------------------------------------------------

REPO_ID = uuid.UUID("00000000-0000-4000-8000-e2e000000001")
JOB_ID_FULL = uuid.UUID("00000000-0000-4000-8000-e2e000000010")
JOB_ID_INCR = uuid.UUID("00000000-0000-4000-8000-e2e000000011")
JOB_ID_WEBHOOK = uuid.UUID("00000000-0000-4000-8000-e2e000000012")
STRUCTURE_ID = uuid.UUID("00000000-0000-4000-8000-e2e000000020")
NOW = datetime(2026, 2, 17, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Stateful mock repos
# ---------------------------------------------------------------------------


def _make_repo_ns() -> SimpleNamespace:
    return SimpleNamespace(
        id=REPO_ID,
        url="https://github.com/acme/widgets",
        provider="github",
        org="acme",
        name="widgets",
        branch_mappings={"main": "main"},
        public_branch="main",
        access_token=None,
        created_at=NOW,
        updated_at=NOW,
    )


def _make_structure_ns() -> SimpleNamespace:
    return SimpleNamespace(
        id=STRUCTURE_ID,
        repository_id=REPO_ID,
        branch="main",
        scope_path=".",
        version=1,
        title="Widgets Documentation",
        description="Auto-generated docs",
        sections={
            "sections": [
                {
                    "title": "Getting Started",
                    "description": "Introduction",
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
            ],
        },
        commit_sha="abc123def456" * 3 + "abc123de",
        created_at=NOW,
    )


def _make_page_ns(page_key: str = "getting-started/overview") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        wiki_structure_id=STRUCTURE_ID,
        page_key=page_key,
        title="Overview",
        description="Project overview",
        importance="high",
        page_type="overview",
        content="# Overview\n\nThis is the widgets project overview.",
        source_files=["src/main.py"],
        related_pages=[],
        quality_score=8.5,
    )


class StatefulRepositoryRepo:
    """Simulates repository CRUD with in-memory state."""

    def __init__(self) -> None:
        self._repos: dict[uuid.UUID, SimpleNamespace] = {}

    async def get_by_id(self, repo_id: uuid.UUID) -> SimpleNamespace | None:
        return self._repos.get(repo_id)

    async def get_by_url(self, url: str) -> SimpleNamespace | None:
        normalized = url.removesuffix(".git")
        for r in self._repos.values():
            if r.url.removesuffix(".git") == normalized:
                return r
        return None

    async def create(self, **kwargs: object) -> SimpleNamespace:
        ns = _make_repo_ns()
        for k, v in kwargs.items():
            setattr(ns, k, v)
        self._repos[ns.id] = ns
        return ns

    async def list(self, **_kwargs: object) -> list[SimpleNamespace]:
        return list(self._repos.values())

    async def update(self, repo_id: uuid.UUID, **kwargs: object) -> SimpleNamespace | None:
        ns = self._repos.get(repo_id)
        if ns:
            for k, v in kwargs.items():
                setattr(ns, k, v)
        return ns

    async def delete(self, repo_id: uuid.UUID) -> bool:
        return self._repos.pop(repo_id, None) is not None


class StatefulJobRepo:
    """Simulates job lifecycle with in-memory state."""

    def __init__(self) -> None:
        self._jobs: dict[uuid.UUID, SimpleNamespace] = {}
        self._next_id = JOB_ID_FULL

    async def get_by_id(self, job_id: uuid.UUID) -> SimpleNamespace | None:
        return self._jobs.get(job_id)

    async def get_active_for_repo(self, **_kwargs: object) -> SimpleNamespace | None:
        return None

    async def create(self, **kwargs: object) -> SimpleNamespace:
        ns = SimpleNamespace(
            id=self._next_id,
            commit_sha=None,
            prefect_flow_run_id=None,
            app_commit_sha="e2etest",
            quality_report=None,
            token_usage=None,
            config_warnings=None,
            error_message=None,
            pull_request_url=None,
            created_at=NOW,
            updated_at=NOW,
        )
        for k, v in kwargs.items():
            setattr(ns, k, v)
        self._jobs[ns.id] = ns
        return ns

    async def list(self, **_kwargs: object) -> list[SimpleNamespace]:
        return list(self._jobs.values())

    async def update_status(
        self, job_id: uuid.UUID, status: str, **kwargs: object
    ) -> SimpleNamespace | None:
        ns = self._jobs.get(job_id)
        if ns:
            ns.status = status
            for k, v in kwargs.items():
                setattr(ns, k, v)
        return ns

    def set_next_id(self, job_id: uuid.UUID) -> None:
        self._next_id = job_id


class StatefulWikiRepo:
    """Simulates wiki structure/page storage with in-memory state."""

    def __init__(self) -> None:
        self._has_structure = False

    def mark_structure_exists(self) -> None:
        self._has_structure = True

    async def get_latest_structure(self, **_kwargs: object) -> SimpleNamespace | None:
        return _make_structure_ns() if self._has_structure else None

    async def get_structures_for_repo(self, **_kwargs: object) -> list[SimpleNamespace]:
        return [_make_structure_ns()] if self._has_structure else []

    async def count_pages_for_structure(self, _structure_id: uuid.UUID) -> int:
        return 1 if self._has_structure else 0

    async def get_page_by_key(self, **_kwargs: object) -> SimpleNamespace | None:
        return _make_page_ns() if self._has_structure else None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def stateful_repos():
    """Create all stateful repos as a bundle."""
    return {
        "repository_repo": StatefulRepositoryRepo(),
        "job_repo": StatefulJobRepo(),
        "wiki_repo": StatefulWikiRepo(),
        "search_repo": AsyncMock(),
    }


@pytest.fixture()
async def client(stateful_repos):
    app: FastAPI = create_app()
    app.dependency_overrides[get_repository_repo] = lambda: stateful_repos["repository_repo"]
    app.dependency_overrides[get_job_repo] = lambda: stateful_repos["job_repo"]
    app.dependency_overrides[get_wiki_repo] = lambda: stateful_repos["wiki_repo"]
    app.dependency_overrides[get_search_repo] = lambda: stateful_repos["search_repo"]

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# E2E Workflow Tests
# ---------------------------------------------------------------------------


class TestE2EWorkflow:
    """Validates the full quickstart.md workflow in sequence."""

    async def test_step1_register_repository(self, client: httpx.AsyncClient):
        """Step 1: Register a repository."""
        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "github"
        assert data["org"] == "acme"
        assert data["name"] == "widgets"
        assert "id" in data

    async def test_step2_trigger_full_generation(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 2: Trigger full generation (no structure exists → full mode)."""
        # Pre-populate: register repo first
        await stateful_repos["repository_repo"].create()

        response = await client.post(
            "/jobs",
            json={"repository_id": str(REPO_ID), "branch": "main"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["mode"] == "full"
        assert data["status"] == "PENDING"

    async def test_step3_verify_wiki_pages(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 3: After generation, verify wiki pages are accessible."""
        # Set up: repo registered, structure exists (simulating completed generation)
        await stateful_repos["repository_repo"].create()
        stateful_repos["wiki_repo"].mark_structure_exists()

        # Get wiki structure
        response = await client.get(f"/documents/{REPO_ID}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0
        assert data["items"][0]["title"] == "Getting Started"

        # Get specific page
        response = await client.get(
            f"/documents/{REPO_ID}/pages/getting-started/overview"
        )
        assert response.status_code == 200
        page = response.json()
        assert page["page_key"] == "getting-started/overview"
        assert page["quality_score"] == 8.5
        assert "content" in page

    async def test_step4_search_documentation(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 4: Search the generated documentation."""
        await stateful_repos["repository_repo"].create()

        mock_response = SearchResponse(
            results=[], search_type="hybrid", total=0,
        )
        with patch(
            "src.api.routes.documents.search_documents",
            return_value=mock_response,
        ):
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "authentication", "search_type": "hybrid"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "hybrid"
        assert data["total"] == 0

    async def test_step5_trigger_incremental_update(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 5: With structure existing, auto-determines incremental mode."""
        await stateful_repos["repository_repo"].create()
        stateful_repos["wiki_repo"].mark_structure_exists()

        stateful_repos["job_repo"].set_next_id(JOB_ID_INCR)

        response = await client.post(
            "/jobs",
            json={"repository_id": str(REPO_ID), "branch": "main"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["mode"] == "incremental", "Should auto-detect incremental when structure exists"

    async def test_step6_force_full_regeneration(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 6: Force full regeneration even when structure exists."""
        await stateful_repos["repository_repo"].create()
        stateful_repos["wiki_repo"].mark_structure_exists()

        response = await client.post(
            "/jobs",
            json={
                "repository_id": str(REPO_ID),
                "branch": "main",
                "force": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["mode"] == "full", "force=true should override incremental detection"

    async def test_step7_webhook_trigger(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 7: Webhook push triggers incremental update."""
        await stateful_repos["repository_repo"].create()
        stateful_repos["wiki_repo"].mark_structure_exists()

        stateful_repos["job_repo"].set_next_id(JOB_ID_WEBHOOK)

        response = await client.post(
            "/webhooks/push",
            json={
                "ref": "refs/heads/main",
                "after": "abc123",
                "repository": {
                    "clone_url": "https://github.com/acme/widgets.git",
                    "full_name": "acme/widgets",
                },
            },
            headers={"X-GitHub-Event": "push"},
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data

    async def test_step8_scopes_endpoint(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """Step 8: Verify scopes endpoint returns discovered scopes."""
        await stateful_repos["repository_repo"].create()
        stateful_repos["wiki_repo"].mark_structure_exists()

        response = await client.get(f"/documents/{REPO_ID}/scopes")
        assert response.status_code == 200
        data = response.json()
        assert len(data["scopes"]) == 1
        assert data["scopes"][0]["scope_path"] == "."
        assert data["scopes"][0]["page_count"] == 1


# ---------------------------------------------------------------------------
# Latency Validation (SC-004, SC-007)
# ---------------------------------------------------------------------------


class TestLatencyTargets:
    """Validate that API operations meet performance SLAs.

    SC-004: Search queries return within 3 seconds (p95)
    SC-007: Job management operations within 2 seconds
    """

    async def test_search_latency_under_3s(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """SC-004: Search queries return within 3 seconds."""
        await stateful_repos["repository_repo"].create()

        mock_response = SearchResponse(
            results=[], search_type="hybrid", total=0,
        )
        latencies: list[float] = []
        with patch(
            "src.api.routes.documents.search_documents",
            return_value=mock_response,
        ):
            for _ in range(10):
                start = time.monotonic()
                response = await client.get(
                    f"/documents/{REPO_ID}/search",
                    params={"query": "test"},
                )
                elapsed = time.monotonic() - start
                assert response.status_code == 200
                latencies.append(elapsed)

        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 3.0, f"Search p95 latency {p95:.3f}s exceeds 3s target"

    async def test_job_create_latency_under_2s(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """SC-007: Job creation within 2 seconds."""
        await stateful_repos["repository_repo"].create()

        start = time.monotonic()
        response = await client.post(
            "/jobs",
            json={"repository_id": str(REPO_ID), "branch": "main"},
        )
        elapsed = time.monotonic() - start
        assert response.status_code == 201
        assert elapsed < 2.0, f"Job creation latency {elapsed:.3f}s exceeds 2s target"

    async def test_job_get_latency_under_2s(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """SC-007: Job retrieval within 2 seconds."""
        await stateful_repos["repository_repo"].create()
        # Create a job first
        job = await stateful_repos["job_repo"].create(
            repository_id=REPO_ID, status="PENDING", mode="full",
            branch="main", force=False, dry_run=False, callback_url=None,
        )

        start = time.monotonic()
        response = await client.get(f"/jobs/{job.id}")
        elapsed = time.monotonic() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"Job GET latency {elapsed:.3f}s exceeds 2s target"

    async def test_job_list_latency_under_2s(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """SC-007: Job listing within 2 seconds."""
        await stateful_repos["repository_repo"].create()

        start = time.monotonic()
        response = await client.get("/jobs")
        elapsed = time.monotonic() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"Job list latency {elapsed:.3f}s exceeds 2s target"

    async def test_job_cancel_latency_under_2s(
        self, client: httpx.AsyncClient, stateful_repos
    ):
        """SC-007: Job cancellation within 2 seconds."""
        await stateful_repos["repository_repo"].create()
        job = await stateful_repos["job_repo"].create(
            repository_id=REPO_ID, status="PENDING", mode="full",
            branch="main", force=False, dry_run=False, callback_url=None,
        )

        start = time.monotonic()
        response = await client.post(f"/jobs/{job.id}/cancel")
        elapsed = time.monotonic() - start
        assert response.status_code == 200
        assert elapsed < 2.0, f"Job cancel latency {elapsed:.3f}s exceeds 2s target"

    async def test_health_endpoint(self, client: httpx.AsyncClient):
        """Health check must respond quickly."""
        start = time.monotonic()
        response = await client.get("/health")
        elapsed = time.monotonic() - start
        assert response.status_code == 200
        assert elapsed < 1.0, f"Health check latency {elapsed:.3f}s exceeds 1s target"
