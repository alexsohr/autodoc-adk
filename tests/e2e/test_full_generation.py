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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_repo(client) -> dict:
    """Register a sample repository and return the JSON response body."""
    resp = await client.post(
        "/repositories",
        json={
            "url": "https://github.com/test/sample-project",
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
    # Return last known state on timeout
    resp = await client.get(f"/jobs/{job_id}")
    return resp.json()


def _make_generate_pages_side_effect():
    """Create a side_effect for generate_pages that saves pages to the test DB.

    This replaces the entire ``generate_pages`` flow (which normally uses
    ThreadPoolTaskRunner + an independent DB engine) with a function that:
    1. Extracts page specs from the structure_result argument
    2. Creates WikiPage records via the patched ``get_session_factory()``
    3. Returns ``list[PageTaskResult]``

    By using ``get_session_factory()`` (patched to the test SAVEPOINT-backed
    session by ``prefect_harness``), all data is visible to the test client's
    ``db_session`` and rolled back automatically after the test.
    """
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

        # Save pages to DB using the patched session factory
        from src.database.engine import get_session_factory
        from src.database.repos.wiki_repo import WikiRepo

        session_factory = get_session_factory()
        results: list[PageTaskResult] = []

        async with session_factory() as session:
            wiki_repo = WikiRepo(session)

            for page_spec in page_specs:
                # Generate deterministic page content (mirrors make_page_stub logic)
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
    """Create a side_effect for distill_readme that returns ReadmeTaskResult.

    Bypasses the real ReadmeDistiller agent while returning the expected
    ReadmeTaskResult (not AgentResult), which is what the scope_processing
    flow expects from the distill_readme task.
    """

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
    """Return a list of patch context managers for the full generation flow.

    Patches are applied where functions are imported in the flow modules.
    The key differences from test_job_lifecycle._all_flow_patches:
    - ``generate_pages`` is patched at the scope_processing import site
      (not PageGenerator.run) so page data is saved to the test DB
      via the patched session factory.
    - ``distill_readme`` is patched at the scope_processing import site
      (not ReadmeDistiller.run) so the task returns ReadmeTaskResult directly.
    """
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
        # Clone — patched where imported in full_generation
        patch(
            "src.flows.full_generation.clone_repository",
            side_effect=clone_side_effect or make_clone_stub(FIXTURE_PATH),
        ),
        # Structure extractor agent — patched inside the extract_structure task
        # module. The task uses get_session_factory() (patched by prefect_harness)
        # to save the structure to the test DB.
        patch(
            "src.flows.tasks.structure.StructureExtractor.run",
            structure_mock,
        ),
        # SanitizedDatabaseSessionService — prevent ADK DB session connection
        # (the session is passed to the mocked agent.run which ignores it)
        patch(
            "src.services.session.SanitizedDatabaseSessionService",
        ),
        # generate_pages flow — patched at the scope_processing import site.
        # Uses a custom side_effect that saves pages through the patched
        # session factory (SAVEPOINT-compatible) and returns PageTaskResult.
        patch(
            "src.flows.scope_processing.generate_pages",
            side_effect=generate_pages_side_effect,
        ),
        # distill_readme task — patched at the scope_processing import site.
        # Returns ReadmeTaskResult directly.
        patch(
            "src.flows.scope_processing.distill_readme",
            side_effect=distill_readme_side_effect,
        ),
        # Embeddings — patched at the scope_processing import site (no-op)
        patch(
            "src.flows.scope_processing.generate_embeddings_task",
            new_callable=AsyncMock,
            return_value=0,
        ),
        # PR tasks — patched where imported in full_generation
        patch(
            "src.flows.full_generation.close_stale_autodoc_prs",
            close_stale_mock,
        ),
        patch(
            "src.flows.full_generation.create_autodoc_pr",
            create_pr_mock,
        ),
        # Callback — patched where imported in full_generation
        patch(
            "src.flows.full_generation.deliver_callback",
            callback_mock,
        ),
        # Cleanup — patched to avoid real filesystem operations
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
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestFullGeneration:
    """E2E tests for the full documentation generation pipeline."""

    # -------------------------------------------------------------------
    # 4.1-4.2  Happy path: register repo -> create job -> verify output
    # -------------------------------------------------------------------

    async def test_happy_path(self, client, db_session, prefect_harness):
        """Full generation: register repo, create job, wait for flow, verify everything."""
        # 1. Register repository
        repo = await _register_repo(client)
        repo_id = repo["id"]

        close_pr_mock, create_pr_mock = make_pr_stub()
        callback_mock = make_callback_stub()
        structure_mock = make_structure_stub()

        patches = _full_generation_patches(
            structure_mock=structure_mock,
            close_stale_mock=close_pr_mock,
            create_pr_mock=create_pr_mock,
            callback_mock=callback_mock,
        )

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # 2. Create job (triggers full generation flow)
            resp = await client.post("/jobs", json={"repository_id": repo_id})
            assert resp.status_code == 201, resp.text
            job_data = resp.json()
            job_id = job_data["id"]
            assert job_data["mode"] == "full"

            # 3. Wait for flow to complete
            result = await _poll_job(client, job_id, timeout=30.0)

            # 4. Assert COMPLETED
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )
            assert result["quality_report"] is not None
            assert result["token_usage"] is not None
            assert result["commit_sha"] is not None
            assert result["pull_request_url"] is not None
            assert result["pull_request_url"] == "https://github.com/test/sample-project/pull/999"

            # 5. Verify structure via the job structure endpoint
            resp = await client.get(f"/jobs/{job_id}/structure")
            assert resp.status_code == 200, resp.text
            structure = resp.json()
            assert len(structure["sections"]) == 2
            section_titles = {s["title"] for s in structure["sections"]}
            assert "Core Modules" in section_titles
            assert "Project Overview" in section_titles

            # 6. Verify full wiki (sections + pages)
            resp = await client.get(f"/documents/{repo_id}/wiki")
            assert resp.status_code == 200, resp.text
            wiki = resp.json()
            assert wiki["title"] == "Sample Project Documentation"
            assert len(wiki["sections"]) == 2

            # Collect all page keys from sections
            all_page_keys = set()
            for section in wiki["sections"]:
                for page in section.get("pages", []):
                    all_page_keys.add(page["page_key"])
            assert "core-module" in all_page_keys
            assert "utils-module" in all_page_keys
            assert "project-overview" in all_page_keys

            # 7. Verify individual page retrieval
            for page_key in ["core-module", "utils-module", "project-overview"]:
                resp = await client.get(f"/documents/{repo_id}/pages/{page_key}")
                assert resp.status_code == 200, (
                    f"GET /documents/{repo_id}/pages/{page_key} returned {resp.status_code}: {resp.text}"
                )
                page_data = resp.json()
                assert page_key in page_data["content"]

            # 8. Verify quality report structure
            qr = result["quality_report"]
            assert qr["total_pages"] == 3
            assert qr["overall_score"] > 0
            assert "structure_score" in qr
            assert "page_scores" in qr

            # 9. Verify token usage structure
            tu = result["token_usage"]
            assert tu["total_tokens"] > 0
            assert "by_agent" in tu

            # 10. Verify PR mock was called
            assert create_pr_mock.called
            assert close_pr_mock.called

            # 11. Verify structure extractor was called
            assert structure_mock.called

    # -------------------------------------------------------------------
    # 4.3  Dry run: structure only, no pages, no PR
    # -------------------------------------------------------------------

    async def test_dry_run(self, client, db_session, prefect_harness):
        """Dry run: only structure extraction, no pages, no README, no PR."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        structure_mock = make_structure_stub()
        page_side_effect = _make_generate_pages_side_effect()
        readme_side_effect = _make_distill_readme_side_effect()
        close_pr_mock, create_pr_mock = make_pr_stub()
        callback_mock = make_callback_stub()

        # Track whether generate_pages / distill_readme were called
        generate_pages_mock = AsyncMock(side_effect=page_side_effect)
        distill_readme_mock = AsyncMock(side_effect=readme_side_effect)

        # Build patches manually to track call counts
        dry_patches = [
            patch(
                "src.flows.full_generation.clone_repository",
                side_effect=make_clone_stub(FIXTURE_PATH),
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
                generate_pages_mock,
            ),
            patch(
                "src.flows.scope_processing.distill_readme",
                distill_readme_mock,
            ),
            patch(
                "src.flows.scope_processing.generate_embeddings_task",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                close_pr_mock,
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

        with contextlib.ExitStack() as stack:
            for p in dry_patches:
                stack.enter_context(p)

            # Create job with dry_run=True
            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "dry_run": True,
                },
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]
            assert resp.json()["dry_run"] is True

            # Wait for flow completion
            result = await _poll_job(client, job_id, timeout=30.0)

            # Job should complete (structure extraction passes quality gate)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

            # Structure extractor SHOULD have been called
            assert structure_mock.called, "StructureExtractor.run should be called in dry_run"

            # Pages should NOT have been generated
            assert not generate_pages_mock.called, "generate_pages should not be called in dry_run mode"

            # README should NOT have been distilled
            assert not distill_readme_mock.called, "distill_readme should not be called in dry_run mode"

            # PR should NOT have been created
            assert not create_pr_mock.called, "create_autodoc_pr should not be called in dry_run mode"

            # Pull request URL should be None
            assert result["pull_request_url"] is None

            # Structure should exist (it's saved by extract_structure task)
            resp = await client.get(f"/jobs/{job_id}/structure")
            assert resp.status_code == 200
            structure = resp.json()
            assert len(structure["sections"]) == 2

            # Pages should NOT exist
            resp = await client.get(f"/documents/{repo_id}/pages/core-module")
            assert resp.status_code == 404

    # -------------------------------------------------------------------
    # 4.4  Quality gate failure: structure below floor
    # -------------------------------------------------------------------

    async def test_quality_gate_failure(self, client, db_session, prefect_harness):
        """Structure below minimum floor -> job FAILED, no pages generated."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Use a structure stub with low score and below_floor=True
        structure_mock = make_structure_stub(score=3.0, below_floor=True)
        generate_pages_mock = AsyncMock(side_effect=_make_generate_pages_side_effect())
        close_pr_mock, create_pr_mock = make_pr_stub()

        quality_patches = [
            patch(
                "src.flows.full_generation.clone_repository",
                side_effect=make_clone_stub(FIXTURE_PATH),
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
                generate_pages_mock,
            ),
            patch(
                "src.flows.scope_processing.distill_readme",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.scope_processing.generate_embeddings_task",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                close_pr_mock,
            ),
            patch(
                "src.flows.full_generation.create_autodoc_pr",
                create_pr_mock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
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

        with contextlib.ExitStack() as stack:
            for p in quality_patches:
                stack.enter_context(p)

            # Create job
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id},
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]

            # Wait for flow
            result = await _poll_job(client, job_id, timeout=30.0)

            # Job should FAIL due to quality gate
            assert result["status"] == "FAILED", (
                f"Expected FAILED due to quality gate, got {result['status']}: {result.get('error_message')}"
            )

            # Error message should indicate failure (quality gate or scope failure)
            error_msg = result.get("error_message") or ""
            assert any(kw in error_msg.lower() for kw in ("quality", "below", "floor", "minimum", "failed", "error")), (
                f"Expected failure-related error, got: {error_msg}"
            )

            # Pages should NOT have been generated (quality gate fails before pages)
            assert not generate_pages_mock.called, "generate_pages should not be called when structure is below floor"

            # PR should NOT have been created
            assert not create_pr_mock.called, "create_autodoc_pr should not be called when quality gate fails"

            # No pages should exist for this repo
            resp = await client.get(f"/documents/{repo_id}/pages/core-module")
            assert resp.status_code == 404
