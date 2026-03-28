"""E2E search tests (tasks 4.21-4.24).

After running a full generation flow with stubs, verifies that text,
semantic, and hybrid search endpoints return correct results from the
real test database (PostgreSQL + pgvector via testcontainers).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.database.models.wiki_page import WikiPage
from src.flows.schemas import PageTaskResult, ReadmeTaskResult, TokenUsageResult
from tests.e2e.stubs import (
    make_callback_stub,
    make_clone_stub,
    make_embedding_stub,
    make_pr_stub,
    make_structure_stub,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_REPO = os.path.join(os.path.dirname(__file__), "fixtures", "sample-repo")


# ---------------------------------------------------------------------------
# Helper: generate_pages side_effect that saves pages to DB
# ---------------------------------------------------------------------------


def _make_generate_pages_side_effect():
    """Side_effect for generate_pages that writes WikiPage records to the test DB."""
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


def _full_generation_patches_with_embeddings():
    """Return patches for full generation that include real embedding generation.

    Uses the same proven patching pattern as test_full_generation.py but
    allows generate_embeddings_task to run (with stubbed embed_texts) so
    that page_chunks with vectors are created in the DB for search tests.
    """
    structure_mock = make_structure_stub()
    close_stale_mock, create_pr_mock = make_pr_stub()
    callback_mock = make_callback_stub()
    embedding_side_effect = make_embedding_stub()

    return [
        patch(
            "src.flows.full_generation.clone_repository",
            side_effect=make_clone_stub(_FIXTURE_REPO),
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
        # Let generate_embeddings_task run (real) but stub the external calls
        patch(
            "src.flows.tasks.embeddings.embed_texts",
            side_effect=embedding_side_effect,
        ),
        # Disable context enrichment by patching get_settings in the
        # embeddings task to return settings with CONTEXT_ENABLED=False.
        # This avoids LLM calls and the strict zip issue with empty contexts.
        patch(
            "src.flows.tasks.embeddings.get_settings",
            return_value=MagicMock(CONTEXT_ENABLED=False),
        ),
        # PR tasks
        patch(
            "src.flows.full_generation.close_stale_autodoc_prs",
            close_stale_mock,
        ),
        patch(
            "src.flows.full_generation.create_autodoc_pr",
            create_pr_mock,
        ),
        # Callback
        patch(
            "src.flows.full_generation.deliver_callback",
            callback_mock,
        ),
        # Cleanup
        patch(
            "src.flows.full_generation.cleanup_workspace",
            new_callable=AsyncMock,
        ),
        patch(
            "src.flows.tasks.cleanup.cleanup_workspace",
            new_callable=AsyncMock,
        ),
    ]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


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


async def _run_full_generation(client):
    """Register a repo, create a job, and wait for the flow to complete.

    Returns (repo_id, job_id) once the job reaches a terminal state.
    """
    # 1. Register repository
    resp = await client.post(
        "/repositories",
        json={
            "url": "https://github.com/test/sample-project",
            "provider": "github",
            "branch_mappings": {"main": "main"},
            "public_branch": "main",
        },
    )
    assert resp.status_code == 201, f"Repo registration failed: {resp.text}"
    repo_id = resp.json()["id"]

    # 2. Create a full-generation job
    resp = await client.post(
        "/jobs",
        json={
            "repository_id": repo_id,
            "branch": "main",
            "force": True,
            "dry_run": False,
        },
    )
    assert resp.status_code == 201, f"Job creation failed: {resp.text}"
    job_id = resp.json()["id"]

    # 3. Poll until the flow reaches a terminal state
    result = await _poll_job(client, job_id, timeout=30.0)
    assert result["status"] == "COMPLETED", (
        f"Expected COMPLETED but got {result['status']}: {result.get('error_message')}"
    )

    return repo_id, job_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestSearch:
    """Search E2E tests that rely on a completed full-generation run.

    Each test registers a repository, triggers full generation with all
    agents/services stubbed, waits for completion, then exercises the
    search endpoint against the real test database.
    """

    async def test_text_search(
        self,
        client,
        db_session,
        prefect_harness,
    ):
        """Task 4.22: GET /documents/{repo_id}/search?search_type=text

        Verifies that full-text search on page content matches pages whose
        content contains the query term.
        """
        patches = _full_generation_patches_with_embeddings()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            repo_id, _job_id = await _run_full_generation(client)

        resp = await client.get(
            f"/documents/{repo_id}/search",
            params={"query": "core", "search_type": "text"},
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["search_type"] == "text"
        assert len(data["results"]) > 0, "Text search should return results"

        page_keys = [r["page_key"] for r in data["results"]]
        assert "core-module" in page_keys, f"Expected 'core-module' in text search results, got {page_keys}"

    async def test_semantic_search(
        self,
        client,
        db_session,
        prefect_harness,
    ):
        """Task 4.23: GET /documents/{repo_id}/search?search_type=semantic

        Verifies that semantic (vector) search returns results with
        non-zero similarity scores.
        """
        embedding_side_effect = make_embedding_stub()

        async def _embed_query_stub(query, *, model=None, dimensions=None):
            vectors = await embedding_side_effect([query])
            return vectors[0]

        patches = _full_generation_patches_with_embeddings()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            repo_id, _job_id = await _run_full_generation(client)

        with patch("src.services.search.embed_query", side_effect=_embed_query_stub):
            resp = await client.get(
                f"/documents/{repo_id}/search",
                params={
                    "query": "module documentation",
                    "search_type": "semantic",
                },
            )
        assert resp.status_code == 200

        data = resp.json()
        assert data["search_type"] == "semantic"
        assert len(data["results"]) > 0, "Semantic search should return results"

        for result in data["results"]:
            assert result["score"] != 0.0, f"Semantic result for '{result['page_key']}' should have a non-zero score"

    async def test_hybrid_search(
        self,
        client,
        db_session,
        prefect_harness,
    ):
        """Task 4.24: GET /documents/{repo_id}/search?search_type=hybrid

        Verifies that hybrid (RRF) search returns results and that they
        are ordered by score in descending order.
        """
        embedding_side_effect = make_embedding_stub()

        async def _embed_query_stub(query, *, model=None, dimensions=None):
            vectors = await embedding_side_effect([query])
            return vectors[0]

        patches = _full_generation_patches_with_embeddings()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            repo_id, _job_id = await _run_full_generation(client)

        with patch("src.services.search.embed_query", side_effect=_embed_query_stub):
            resp = await client.get(
                f"/documents/{repo_id}/search",
                params={"query": "core", "search_type": "hybrid"},
            )
        assert resp.status_code == 200

        data = resp.json()
        assert data["search_type"] == "hybrid"
        assert len(data["results"]) > 0, "Hybrid search should return results"

        scores = [r["score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True), f"Results should be ordered by score descending, got {scores}"
