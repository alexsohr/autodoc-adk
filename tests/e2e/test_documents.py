from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.database.models.wiki_page import WikiPage
from src.flows.schemas import PageTaskResult, ReadmeTaskResult, TokenUsageResult
from tests.e2e.stubs import (
    make_callback_stub,
    make_clone_stub,
    make_pr_stub,
    make_structure_stub,
)

FIXTURE_PATH = str(Path(__file__).parent / "fixtures" / "sample-repo")

_REPO_COUNTER = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_repo(client) -> dict:
    """Register a sample repository with a unique URL and return JSON response."""
    global _REPO_COUNTER
    _REPO_COUNTER += 1
    resp = await client.post(
        "/repositories",
        json={
            "url": f"https://github.com/test-docs/doc-repo-{_REPO_COUNTER}",
            "provider": "github",
            "branch_mappings": {"main": "Main Branch"},
            "public_branch": "main",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _poll_job(client, job_id: str, *, timeout: float = 30.0) -> dict:
    """Poll GET /jobs/{id} until terminal status or timeout."""
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


def _make_generate_pages_side_effect():
    """Create a side_effect for generate_pages that saves pages to the test DB."""
    from src.flows.tasks.pages import _reconstruct_page_specs

    async def _side_effect(
        *,
        job_id: uuid.UUID,
        wiki_structure_id: uuid.UUID,
        structure_result,
        repo_path: str,
        config,
    ) -> list[PageTaskResult]:
        page_specs = _reconstruct_page_specs(structure_result.sections_json or [])
        if not page_specs:
            return []

        from src.database.engine import get_session_factory
        from src.database.repos.wiki_repo import WikiRepo

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
    """Create a side_effect for distill_readme that returns ReadmeTaskResult."""

    async def _side_effect(**kwargs) -> ReadmeTaskResult:
        content = (
            "# Sample Project Documentation\n\n"
            "Welcome to the Sample Project.\n\n"
            "## Contents\n\n"
            "- [Core Module](docs/core-module.md) - Core functionality\n"
            "- [Utility Functions](docs/utils-module.md) - Helper utilities\n"
            "- [Project Overview](docs/project-overview.md) - High-level overview\n\n"
            "## Getting Started\n\n"
            "See the individual module pages for detailed documentation.\n"
        )
        return ReadmeTaskResult(
            final_score=7.5,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            content=content,
            token_usage=TokenUsageResult(
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                calls=2,
            ),
        )

    return _side_effect


def _full_generation_patches(
    *,
    clone_side_effect=None,
    structure_mock=None,
    generate_pages_side_effect=None,
    distill_readme_side_effect=None,
    close_stale_mock=None,
    create_pr_mock=None,
    callback_mock=None,
):
    """Return a list of patch context managers for the full generation flow."""
    if structure_mock is None:
        structure_mock = make_structure_stub()
    if close_stale_mock is None and create_pr_mock is None:
        close_stale_mock, create_pr_mock = make_pr_stub()
    elif close_stale_mock is None:
        close_stale_mock = AsyncMock(return_value=0)
    elif create_pr_mock is None:
        create_pr_mock = AsyncMock(return_value="https://github.com/test/sample-project/pull/999")
    if callback_mock is None:
        callback_mock = make_callback_stub()
    if generate_pages_side_effect is None:
        generate_pages_side_effect = _make_generate_pages_side_effect()
    if distill_readme_side_effect is None:
        distill_readme_side_effect = _make_distill_readme_side_effect()

    return [
        patch(
            "src.flows.full_generation.clone_repository",
            side_effect=clone_side_effect or make_clone_stub(FIXTURE_PATH),
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
            side_effect=generate_pages_side_effect,
        ),
        patch(
            "src.flows.scope_processing.distill_readme",
            side_effect=distill_readme_side_effect,
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


async def _run_full_generation(client) -> tuple[str, str]:
    """Register a repo, run full generation, and return (repo_id, job_id).

    The caller MUST have activated the ``prefect_harness`` fixture before
    calling this helper.
    """
    repo = await _register_repo(client)
    repo_id = repo["id"]

    patches = _full_generation_patches()

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        resp = await client.post("/jobs", json={"repository_id": repo_id})
        assert resp.status_code == 201, resp.text
        job_id = resp.json()["id"]

        result = await _poll_job(client, job_id, timeout=30.0)
        assert result["status"] == "COMPLETED", (
            f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
        )

    return repo_id, job_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestDocuments:
    """E2E tests for document retrieval and search endpoints (6.19-6.28)."""

    # -------------------------------------------------------------------
    # 6.20  List scopes after generation
    # -------------------------------------------------------------------

    async def test_list_scopes_after_generation(self, client, db_session, prefect_harness):
        """After full gen, GET /documents/{repo_id}/scopes returns non-empty list with page_count > 0."""
        repo_id, _ = await _run_full_generation(client)

        resp = await client.get(f"/documents/{repo_id}/scopes")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["scopes"]) > 0, "Expected at least one scope after generation"

        for scope in data["scopes"]:
            assert scope["page_count"] > 0, f"Scope '{scope['scope_path']}' should have pages"

    # -------------------------------------------------------------------
    # 6.21  List scopes with no structures
    # -------------------------------------------------------------------

    async def test_list_scopes_no_structures(self, client, db_session):
        """Register repo without generation -> GET scopes returns empty list."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        resp = await client.get(f"/documents/{repo_id}/scopes")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["scopes"] == [], "Expected empty scopes list for repo with no generation"

    # -------------------------------------------------------------------
    # 6.22  Get page by key
    # -------------------------------------------------------------------

    async def test_get_page_by_key(self, client, db_session, prefect_harness):
        """After full gen, GET /documents/{repo_id}/pages/core-module returns full page data."""
        repo_id, _ = await _run_full_generation(client)

        resp = await client.get(f"/documents/{repo_id}/pages/core-module")
        assert resp.status_code == 200, resp.text
        page = resp.json()

        assert page["page_key"] == "core-module"
        assert page["content"], "Page content should not be empty"
        assert len(page["source_files"]) > 0, "Page should have source_files"
        assert page["quality_score"] is not None, "Page should have a quality_score"
        assert page["quality_score"] > 0

    # -------------------------------------------------------------------
    # 6.23  Get page not found
    # -------------------------------------------------------------------

    async def test_get_page_not_found(self, client, db_session, prefect_harness):
        """GET /documents/{repo_id}/pages/nonexistent returns 404."""
        repo_id, _ = await _run_full_generation(client)

        resp = await client.get(f"/documents/{repo_id}/pages/nonexistent-page-key")
        assert resp.status_code == 404

    # -------------------------------------------------------------------
    # 6.24  Get full wiki
    # -------------------------------------------------------------------

    async def test_get_full_wiki(self, client, db_session, prefect_harness):
        """After full gen, GET /documents/{repo_id}/wiki returns sections with pages."""
        repo_id, _ = await _run_full_generation(client)

        resp = await client.get(f"/documents/{repo_id}/wiki")
        assert resp.status_code == 200, resp.text
        wiki = resp.json()

        assert wiki["title"] is not None
        assert wiki["scope_path"] == "."
        assert wiki["branch"] == "main"
        assert wiki["commit_sha"] is not None
        assert len(wiki["sections"]) > 0, "Wiki should have at least one section"

        # Verify sections contain pages with content
        all_pages = []
        for section in wiki["sections"]:
            for page in section.get("pages", []):
                all_pages.append(page)
        assert len(all_pages) > 0, "Wiki sections should contain pages"
        for page in all_pages:
            assert page["content"], f"Page '{page['page_key']}' should have content"

    # -------------------------------------------------------------------
    # 6.25  Get wiki with no structure
    # -------------------------------------------------------------------

    async def test_get_wiki_no_structure(self, client, db_session):
        """Register repo without generation -> GET wiki returns 404."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        resp = await client.get(f"/documents/{repo_id}/wiki")
        assert resp.status_code == 404

    # -------------------------------------------------------------------
    # 6.26  Paginate wiki sections
    # -------------------------------------------------------------------

    async def test_paginate_wiki_sections(self, client, db_session, prefect_harness):
        """After full gen, GET /documents/{repo_id}?limit=1 returns 1 section + next_cursor."""
        repo_id, _ = await _run_full_generation(client)

        resp = await client.get(f"/documents/{repo_id}", params={"limit": 1})
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert len(data["items"]) == 1, "Expected exactly 1 section with limit=1"
        assert data["next_cursor"] is not None, "Expected next_cursor when more sections exist"
        assert data["limit"] == 1

        # Follow the cursor to get the next page
        resp2 = await client.get(
            f"/documents/{repo_id}",
            params={"limit": 1, "cursor": data["next_cursor"]},
        )
        assert resp2.status_code == 200, resp2.text
        data2 = resp2.json()
        assert len(data2["items"]) == 1, "Expected 1 section on second page"

        # Section titles should differ between pages
        assert data["items"][0]["title"] != data2["items"][0]["title"]

    # -------------------------------------------------------------------
    # 6.28  Search with no results
    # -------------------------------------------------------------------

    async def test_search_no_results(self, client, db_session, prefect_harness):
        """After full gen, searching for nonsense returns empty results."""
        repo_id, _ = await _run_full_generation(client)

        # Use text search to avoid needing embedding service
        resp = await client.get(
            f"/documents/{repo_id}/search",
            params={"query": "zzzznonexistent_xyzzy_nothinghere", "search_type": "text"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["results"] == [], "Expected no results for nonsense query"
        assert data["total"] == 0
        assert data["search_type"] == "text"
