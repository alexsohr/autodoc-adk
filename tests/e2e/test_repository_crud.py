from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select

from src.database.models.job import Job
from src.database.models.page_chunk import PageChunk
from src.database.models.wiki_page import WikiPage
from src.database.models.wiki_structure import WikiStructure
from src.flows.schemas import PageTaskResult, ReadmeTaskResult, TokenUsageResult
from tests.e2e.stubs import (
    make_callback_stub,
    make_clone_stub,
    make_pr_stub,
    make_structure_stub,
)

# ---------------------------------------------------------------------------
# All tests in this module are E2E (real database via testcontainers)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.e2e

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "sample-repo")


# ---------------------------------------------------------------------------
# Helper: generate_pages side_effect that saves pages to the test DB
# ---------------------------------------------------------------------------


def _make_generate_pages_side_effect():
    """Side_effect for generate_pages that writes WikiPage records to DB."""
    from src.flows.tasks.pages import _reconstruct_page_specs

    async def _side_effect(
        *,
        job_id: uuid.UUID,
        wiki_structure_id: uuid.UUID,
        structure_result,
        repo_path: str,
        config,
    ) -> list[PageTaskResult]:
        from src.database.engine import get_session_factory
        from src.database.repos.wiki_repo import WikiRepo

        page_specs = _reconstruct_page_specs(structure_result.sections_json or [])
        if not page_specs:
            return []

        session_factory = get_session_factory()
        results: list[PageTaskResult] = []

        async with session_factory() as session:
            wiki_repo = WikiRepo(session)

            for page_spec in page_specs:
                source_files_list = (
                    "\n".join(f"- `{f}`" for f in page_spec.source_files) if page_spec.source_files else "- None"
                )
                content = (
                    f"# {page_spec.title}\n\n"
                    f"Documentation for {page_spec.page_key}.\n\n"
                    f"## Source Files\n\n"
                    f"{source_files_list}\n\n"
                    f"## Details\n\n"
                    f"This page covers the core functionality.\n\n"
                    f"```python\n"
                    f"# Example code\n"
                    f"pass\n"
                    f"```\n"
                )

                wiki_page = WikiPage(
                    wiki_structure_id=wiki_structure_id,
                    page_key=page_spec.page_key,
                    title=page_spec.title,
                    description=page_spec.description,
                    importance=page_spec.importance,
                    page_type=page_spec.page_type,
                    source_files=page_spec.source_files,
                    related_pages=page_spec.related_pages or [],
                    content=content,
                    quality_score=8.0,
                )
                await wiki_repo.create_pages([wiki_page])

                results.append(
                    PageTaskResult(
                        page_key=page_spec.page_key,
                        final_score=8.0,
                        passed_quality_gate=True,
                        below_minimum_floor=False,
                        attempts=1,
                        token_usage=TokenUsageResult(
                            input_tokens=1200,
                            output_tokens=600,
                            total_tokens=1800,
                            calls=2,
                        ),
                    )
                )

            await session.commit()

        return results

    return _side_effect


def _make_distill_readme_side_effect():
    """Side_effect for distill_readme that returns ReadmeTaskResult."""

    async def _side_effect(**kwargs) -> ReadmeTaskResult:
        return ReadmeTaskResult(
            final_score=7.5,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            content="# Sample Project Documentation\n\nWelcome.\n",
            token_usage=TokenUsageResult(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                calls=2,
            ),
        )

    return _side_effect


def _full_generation_patches():
    """Return patches for full generation using the proven pattern."""
    structure_mock = make_structure_stub()
    close_stale_mock, create_pr_mock = make_pr_stub()
    callback_mock = make_callback_stub()

    return [
        patch(
            "src.flows.full_generation.clone_repository",
            side_effect=make_clone_stub(FIXTURE_DIR),
        ),
        patch(
            "src.flows.tasks.structure.StructureExtractor.run",
            structure_mock,
        ),
        patch(
            "src.services.session.SanitizedDatabaseSessionService",
        ),
        patch(
            "src.flows.scope_processing.generate_pages",
            side_effect=_make_generate_pages_side_effect(),
        ),
        patch(
            "src.flows.scope_processing.distill_readme",
            side_effect=_make_distill_readme_side_effect(),
        ),
        patch(
            "src.flows.scope_processing.generate_embeddings_task",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "src.flows.full_generation.close_stale_autodoc_prs",
            close_stale_mock,
        ),
        patch(
            "src.flows.full_generation.create_autodoc_pr",
            create_pr_mock,
        ),
        patch(
            "src.flows.full_generation.deliver_callback",
            callback_mock,
        ),
        patch(
            "src.flows.full_generation.cleanup_workspace",
            new_callable=AsyncMock,
        ),
        patch(
            "src.flows.tasks.cleanup.cleanup_workspace",
            new_callable=AsyncMock,
        ),
    ]


async def _poll_job(client, job_id: str, *, timeout: float = 30.0) -> dict:
    """Poll GET /jobs/{id} until a terminal status or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.1)
        resp = await client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return data
    resp = await client.get(f"/jobs/{job_id}")
    return resp.json()


# ---------------------------------------------------------------------------
# TestRepositoryRegistration (tasks 4.15-4.19)
# ---------------------------------------------------------------------------


class TestRepositoryRegistration:
    """Repository CRUD validation against a real PostgreSQL database."""

    async def test_register_valid_github_repo(self, client):
        """Task 4.16: Register a valid GitHub repository and verify the response."""
        resp = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/test/sample-project",
                "provider": "github",
                "branch_mappings": {"main": "Main Branch"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://github.com/test/sample-project"
        assert data["provider"] == "github"
        assert data["org"] == "test"
        assert data["name"] == "sample-project"
        assert data["branch_mappings"] == {"main": "Main Branch"}
        assert data["public_branch"] == "main"
        assert "id" in data
        assert "created_at" in data

    async def test_register_duplicate_url(self, client):
        """Task 4.17: Registering the same URL twice returns 409."""
        payload = {
            "url": "https://github.com/test/duplicate-repo",
            "provider": "github",
            "branch_mappings": {"main": "Main"},
            "public_branch": "main",
        }
        resp1 = await client.post("/repositories", json=payload)
        assert resp1.status_code == 201

        resp2 = await client.post("/repositories", json=payload)
        assert resp2.status_code == 409

    async def test_register_url_provider_mismatch(self, client):
        """Task 4.18: URL host must match the declared provider."""
        resp = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/test/repo",
                "provider": "bitbucket",
                "branch_mappings": {"main": "Main"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 422

    async def test_register_public_branch_not_in_mappings(self, client):
        """Task 4.19: public_branch must be a key in branch_mappings."""
        resp = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/test/branch-repo",
                "provider": "github",
                "branch_mappings": {"main": "Main"},
                "public_branch": "staging",
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# TestCascadeDelete (task 4.20)
# ---------------------------------------------------------------------------


class TestCascadeDelete:
    """Verify that DELETE /repositories/{id} cascades to all child tables.

    Registers a repository, runs a full generation flow (with all external
    dependencies stubbed), then deletes the repository and asserts that
    every related row has been removed.
    """

    async def test_cascade_delete_removes_all_related_records(self, client, db_session, prefect_harness):
        """Task 4.20: Cascade delete across jobs, structures, pages, and chunks."""
        # --- Step 1: Register repository via API ---
        resp = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/test/cascade-project",
                "provider": "github",
                "branch_mappings": {"main": "Main Branch"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201
        repo_data = resp.json()
        repo_id = repo_data["id"]
        repo_uuid = uuid.UUID(repo_id)

        # --- Step 2: Run full generation with proven patching approach ---
        patches = _full_generation_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            job_resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                    "force": True,
                },
            )
            assert job_resp.status_code == 201
            job_data = job_resp.json()
            job_id = job_data["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Flow did not complete successfully. Status: {result['status']}, error: {result.get('error_message')}"
            )

        # --- Verify records were created ---
        # Use a fresh session for verification queries to avoid stale cache
        from src.database.engine import get_session_factory

        session_factory = get_session_factory()
        async with session_factory() as verify_session:
            structure_count = await verify_session.scalar(
                select(func.count()).select_from(WikiStructure).where(WikiStructure.repository_id == repo_uuid)
            )
            assert structure_count > 0, "Expected at least one WikiStructure record"

            page_count = await verify_session.scalar(
                select(func.count())
                .select_from(WikiPage)
                .join(WikiStructure, WikiPage.wiki_structure_id == WikiStructure.id)
                .where(WikiStructure.repository_id == repo_uuid)
            )
            assert page_count > 0, "Expected at least one WikiPage record"

            job_count = await verify_session.scalar(
                select(func.count()).select_from(Job).where(Job.repository_id == repo_uuid)
            )
            assert job_count > 0, "Expected at least one Job record"

        # --- Step 3: DELETE the repository ---
        delete_resp = await client.delete(f"/repositories/{repo_id}")
        assert delete_resp.status_code == 204

        # --- Step 4: Verify all related records are gone ---
        async with session_factory() as verify_session:
            # Jobs should be cascade-deleted
            remaining_jobs = await verify_session.scalar(
                select(func.count()).select_from(Job).where(Job.repository_id == repo_uuid)
            )
            assert remaining_jobs == 0, f"Expected 0 jobs, found {remaining_jobs}"

            # Wiki structures should be cascade-deleted
            remaining_structures = await verify_session.scalar(
                select(func.count()).select_from(WikiStructure).where(WikiStructure.repository_id == repo_uuid)
            )
            assert remaining_structures == 0, f"Expected 0 structures, found {remaining_structures}"

            # Wiki pages should be cascade-deleted (via structure cascade)
            remaining_pages = await verify_session.scalar(
                select(func.count())
                .select_from(WikiPage)
                .where(
                    WikiPage.wiki_structure_id.in_(
                        select(WikiStructure.id).where(WikiStructure.repository_id == repo_uuid)
                    )
                )
            )
            assert remaining_pages == 0, f"Expected 0 pages, found {remaining_pages}"

            # Page chunks should be cascade-deleted (via page cascade)
            remaining_chunks = await verify_session.scalar(
                select(func.count())
                .select_from(PageChunk)
                .where(
                    PageChunk.wiki_page_id.in_(
                        select(WikiPage.id)
                        .join(WikiStructure, WikiPage.wiki_structure_id == WikiStructure.id)
                        .where(WikiStructure.repository_id == repo_uuid)
                    )
                )
            )
            assert remaining_chunks == 0, f"Expected 0 chunks, found {remaining_chunks}"

        # API confirms repo is gone
        get_resp = await client.get(f"/repositories/{repo_id}")
        assert get_resp.status_code == 404

        # Jobs endpoint returns empty for this repository
        jobs_resp = await client.get(f"/jobs?repository_id={repo_id}")
        assert jobs_resp.status_code == 200
        assert jobs_resp.json()["items"] == []

        # Documents endpoint returns 404 since repo is deleted
        docs_resp = await client.get(f"/documents/{repo_id}/wiki")
        assert docs_resp.status_code == 404


# ---------------------------------------------------------------------------
# TestRepositoryUpdate (tasks 5.18-5.23)
# ---------------------------------------------------------------------------

_UPDATE_REPO_COUNTER = 0


class TestRepositoryUpdate:
    """Repository PATCH endpoint validation against a real PostgreSQL database."""

    async def _register(self, client) -> dict:
        """Register a unique repository and return the JSON response body."""
        global _UPDATE_REPO_COUNTER
        _UPDATE_REPO_COUNTER += 1
        resp = await client.post(
            "/repositories",
            json={
                "url": f"https://github.com/test-org/update-repo-{_UPDATE_REPO_COUNTER}",
                "provider": "github",
                "branch_mappings": {"main": "Main Branch", "develop": "Develop"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_update_branch_mappings(self, client):
        """Task 5.19: PATCH with new branch_mappings updates the repository."""
        repo = await self._register(client)
        repo_id = repo["id"]

        new_mappings = {"main": "Main Branch", "develop": "Develop", "release": "Release"}
        resp = await client.patch(
            f"/repositories/{repo_id}",
            json={
                "branch_mappings": new_mappings,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["branch_mappings"] == new_mappings

        # Verify via GET that the update persisted
        get_resp = await client.get(f"/repositories/{repo_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["branch_mappings"] == new_mappings

    async def test_update_access_token_only(self, client):
        """Task 5.20: PATCH with only access_token returns 200."""
        repo = await self._register(client)
        repo_id = repo["id"]

        resp = await client.patch(
            f"/repositories/{repo_id}",
            json={
                "access_token": "ghp_rotated_token_12345",
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Verify the response still contains existing fields unchanged
        assert data["id"] == repo_id
        assert data["branch_mappings"] == repo["branch_mappings"]
        assert data["public_branch"] == repo["public_branch"]

    async def test_update_public_branch_to_invalid(self, client):
        """Task 5.21: PATCH with public_branch not in mappings returns 422."""
        repo = await self._register(client)
        repo_id = repo["id"]

        resp = await client.patch(
            f"/repositories/{repo_id}",
            json={
                "public_branch": "staging",
            },
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert "staging" in detail
        assert "branch_mappings" in detail

    async def test_update_with_no_fields(self, client):
        """Task 5.22: PATCH with empty body returns 422."""
        repo = await self._register(client)
        repo_id = repo["id"]

        resp = await client.patch(
            f"/repositories/{repo_id}",
            json={},
        )
        assert resp.status_code == 422, resp.text

    async def test_update_nonexistent(self, client):
        """Task 5.23: PATCH on a non-existent repository returns 404."""
        random_id = str(uuid.uuid4())
        resp = await client.patch(
            f"/repositories/{random_id}",
            json={
                "branch_mappings": {"main": "Main"},
            },
        )
        assert resp.status_code == 404, resp.text
        assert "not found" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# TestRepositoryPagination (tasks 6.1-6.4)
# ---------------------------------------------------------------------------

_PAGINATION_REPO_COUNTER = 0


class TestRepositoryPagination:
    """Cursor-based pagination for GET /repositories."""

    async def _register(self, client, *, suffix: str = "") -> dict:
        """Register a unique repository and return the JSON response body."""
        global _PAGINATION_REPO_COUNTER
        _PAGINATION_REPO_COUNTER += 1
        resp = await client.post(
            "/repositories",
            json={
                "url": f"https://github.com/test-org/paginate-repo-{_PAGINATION_REPO_COUNTER}{suffix}",
                "provider": "github",
                "branch_mappings": {"main": "Main Branch"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_first_page_with_next_cursor(self, client):
        """Task 6.2: Create 5 repos, GET with limit=2 returns 2 items + next_cursor."""
        for _ in range(5):
            await self._register(client)

        resp = await client.get("/repositories?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["next_cursor"] is not None
        assert data["limit"] == 2

    async def test_last_page(self, client):
        """Task 6.3: Walk pages until next_cursor is null."""
        created_ids = set()
        for _ in range(5):
            repo = await self._register(client, suffix="-lastpage")
            created_ids.add(repo["id"])

        collected_ids: set[str] = set()
        cursor = None
        pages = 0

        while True:
            url = "/repositories?limit=2"
            if cursor:
                url += f"&cursor={cursor}"
            resp = await client.get(url)
            assert resp.status_code == 200
            data = resp.json()
            for item in data["items"]:
                collected_ids.add(item["id"])
            cursor = data["next_cursor"]
            pages += 1
            if cursor is None:
                break
            # Safety valve: prevent infinite loops
            assert pages < 50, "Too many pages"

        # Last page must have next_cursor=null
        assert cursor is None
        # All created repos should appear somewhere in the paginated results
        assert created_ids.issubset(collected_ids), f"Missing repos: {created_ids - collected_ids}"

    async def test_empty_results(self, client, db_session):
        """Task 6.4: GET /repositories with no repos returns empty list."""
        # Use a cursor that points past all existing repos to get an empty page.
        # Alternatively, we filter for a high cursor that returns nothing.
        # The safest approach: use a UUID that is lexicographically after all
        # existing repos (cursor-based pagination uses id ordering).
        resp = await client.get("/repositories?cursor=ffffffff-ffff-ffff-ffff-ffffffffffff&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["next_cursor"] is None


# ---------------------------------------------------------------------------
# TestRepositoryGetDelete (tasks 6.5-6.7)
# ---------------------------------------------------------------------------

_GET_DELETE_REPO_COUNTER = 0


class TestRepositoryGetDelete:
    """GET and DELETE single repository validation."""

    async def _register(self, client) -> dict:
        """Register a unique repository and return the JSON response body."""
        global _GET_DELETE_REPO_COUNTER
        _GET_DELETE_REPO_COUNTER += 1
        resp = await client.post(
            "/repositories",
            json={
                "url": f"https://github.com/test-org/getdel-repo-{_GET_DELETE_REPO_COUNTER}",
                "provider": "github",
                "branch_mappings": {"main": "Main Branch", "develop": "Develop"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    async def test_get_existing_repo(self, client):
        """Task 6.5: GET /repositories/{id} returns 200 with all fields."""
        repo = await self._register(client)
        repo_id = repo["id"]

        resp = await client.get(f"/repositories/{repo_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == repo_id
        assert data["url"] == repo["url"]
        assert data["provider"] == "github"
        assert data["org"] == "test-org"
        assert "name" in data
        assert data["branch_mappings"] == {"main": "Main Branch", "develop": "Develop"}
        assert data["public_branch"] == "main"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_get_nonexistent_repo(self, client):
        """Task 6.6: GET /repositories/{random_uuid} returns 404."""
        random_id = str(uuid.uuid4())
        resp = await client.get(f"/repositories/{random_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_delete_nonexistent(self, client):
        """Task 6.7: DELETE /repositories/{random_uuid} returns 404."""
        random_id = str(uuid.uuid4())
        resp = await client.delete(f"/repositories/{random_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
