"""E2E tests for incremental documentation update flow.

Exercises the incremental pipeline through the API with real database
persistence (via testcontainers), verifying:

  - Only affected pages are regenerated (changed file overlap)
  - Empty diff short-circuits with no_changes=true
  - Structural changes trigger StructureExtractor re-extraction
  - Mode auto-detection (full when no baseline exists)

Each test first runs a full generation to establish baseline structures
and pages, then triggers incremental mode and asserts selective behavior.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.flows.schemas import (
    PageTaskResult,
    ReadmeTaskResult,
    TokenUsageResult,
)
from tests.e2e.stubs import (
    make_callback_stub,
    make_clone_stub,
    make_compare_commits_stub,
    make_pr_stub,
    make_structure_stub,
)

FIXTURE_DIR = str(Path(__file__).parent / "fixtures" / "sample-repo")


# ---------------------------------------------------------------------------
# Helpers
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


def _make_generate_pages_side_effect():
    """Create a side_effect for generate_pages that saves pages to the test DB.

    Uses the same approach as test_full_generation: writes WikiPage records
    via the patched session factory and returns PageTaskResult list.
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
        from src.database.engine import get_session_factory
        from src.database.models.wiki_page import WikiPage
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
    structure_mock=None,
    generate_pages_side_effect=None,
    distill_readme_side_effect=None,
):
    """Return patches for a full generation flow (same approach as test_full_generation).

    These patches target the correct import sites:
    - clone: src.flows.full_generation.clone_repository
    - structure: src.flows.tasks.structure.StructureExtractor.run
    - generate_pages: src.flows.scope_processing.generate_pages
    - distill_readme: src.flows.scope_processing.distill_readme
    - embeddings: src.flows.scope_processing.generate_embeddings_task
    """
    if structure_mock is None:
        structure_mock = make_structure_stub()
    if generate_pages_side_effect is None:
        generate_pages_side_effect = _make_generate_pages_side_effect()
    if distill_readme_side_effect is None:
        distill_readme_side_effect = _make_distill_readme_side_effect()

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


def _incremental_patches(
    *,
    compare_files: list[str] | None = None,
    structure_mock=None,
    generate_pages_side_effect=None,
    distill_readme_side_effect=None,
):
    """Return patches for the incremental_update flow.

    Patches target the import sites inside src.flows.incremental_update.
    The incremental flow imports tasks at module level:
    - clone_repository, get_provider, extract_structure, generate_pages,
      distill_readme, scan_file_tree, discover_autodoc_configs, etc.
    """
    if compare_files is None:
        compare_files = ["src/core.py"]

    compare_mock = make_compare_commits_stub(compare_files)
    mock_provider = MagicMock()
    mock_provider.compare_commits = compare_mock

    if structure_mock is None:
        structure_mock = make_structure_stub()
    if generate_pages_side_effect is None:
        generate_pages_side_effect = _make_generate_pages_side_effect()
    if distill_readme_side_effect is None:
        distill_readme_side_effect = _make_distill_readme_side_effect()

    close_stale_mock, create_pr_mock = make_pr_stub()
    callback_mock = make_callback_stub()

    return (
        [
            # Clone
            patch(
                "src.flows.incremental_update.clone_repository",
                side_effect=make_clone_stub(FIXTURE_DIR),
            ),
            # Provider (for compare_commits)
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            # Structure extractor — patched at the task module where the agent is used
            patch(
                "src.flows.tasks.structure.StructureExtractor.run",
                structure_mock,
            ),
            # Session service — prevent ADK DB session connections
            patch(
                "src.services.session.SanitizedDatabaseSessionService",
            ),
            # generate_pages — patched at incremental_update import site
            patch(
                "src.flows.incremental_update.generate_pages",
                side_effect=generate_pages_side_effect,
            ),
            # distill_readme — patched at incremental_update import site
            patch(
                "src.flows.incremental_update.distill_readme",
                side_effect=distill_readme_side_effect,
            ),
            # PR tasks
            patch(
                "src.flows.incremental_update.close_stale_autodoc_prs",
                close_stale_mock,
            ),
            patch(
                "src.flows.incremental_update.create_autodoc_pr",
                create_pr_mock,
            ),
            # Metrics
            patch(
                "src.flows.incremental_update.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={},
            ),
            # Callback
            patch(
                "src.flows.incremental_update.deliver_callback",
                callback_mock,
            ),
            # Cleanup
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.tasks.cleanup.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ],
        structure_mock,
        generate_pages_side_effect,
    )


@pytest.mark.e2e
class TestIncrementalUpdate:
    """E2E tests for the incremental_update_flow via the API."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _run_full_generation(self, client, db_session, prefect_harness):
        """Register a repo, run full generation, wait for completion.

        Uses the same proven patching approach as test_full_generation.py.
        Returns (repo_id, job_id) after the full-generation flow finishes.
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
        assert resp.status_code == 201
        repo_id = resp.json()["id"]

        patches = _full_generation_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # 2. Create full-generation job
            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                },
            )
            assert resp.status_code == 201
            job_data = resp.json()
            assert job_data["mode"] == "full"
            job_id = job_data["id"]

            # 3. Wait for the background flow task to complete
            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", f"Full generation failed: {result.get('error_message')}"

        return repo_id, job_id

    # ------------------------------------------------------------------
    # 4.5-4.6: test_affected_pages_only
    # ------------------------------------------------------------------

    async def test_affected_pages_only(self, client, db_session, prefect_harness):
        """Only pages whose source_files overlap changed files are regenerated."""
        repo_id, _full_job_id = await self._run_full_generation(
            client,
            db_session,
            prefect_harness,
        )

        # Track which page specs are passed to generate_pages
        generated_page_keys: list[str] = []
        original_side_effect = _make_generate_pages_side_effect()

        async def _tracking_generate_pages(**kwargs):
            """Wrapper that tracks which pages are generated."""
            from src.flows.tasks.pages import _reconstruct_page_specs

            structure_result = kwargs.get("structure_result")
            if structure_result and structure_result.sections_json:
                page_specs = _reconstruct_page_specs(structure_result.sections_json)
                for ps in page_specs:
                    generated_page_keys.append(ps.page_key)
            return await original_side_effect(**kwargs)

        incr_patches, incr_structure_mock, _ = _incremental_patches(
            compare_files=["src/core.py"],
            generate_pages_side_effect=_tracking_generate_pages,
        )

        with contextlib.ExitStack() as stack:
            for p in incr_patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                },
            )
            assert resp.status_code == 201
            incr_data = resp.json()
            assert incr_data["mode"] == "incremental"
            incr_job_id = incr_data["id"]

            result = await _poll_job(client, incr_job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", f"Incremental update failed: {result.get('error_message')}"

        # Only core-module should be regenerated (src/core.py changed)
        assert "core-module" in generated_page_keys, (
            f"Expected core-module to be regenerated, but got: {generated_page_keys}"
        )
        # utils-module and project-overview should NOT be regenerated
        assert "utils-module" not in generated_page_keys, (
            f"utils-module should NOT be regenerated but was: {generated_page_keys}"
        )
        assert "project-overview" not in generated_page_keys, (
            f"project-overview should NOT be regenerated but was: {generated_page_keys}"
        )

        # Structure extractor should NOT have been called (no structural change)
        assert incr_structure_mock.call_count == 0

    # ------------------------------------------------------------------
    # 4.7: test_no_changes_short_circuit
    # ------------------------------------------------------------------

    async def test_no_changes_short_circuit(self, client, db_session, prefect_harness):
        """Empty diff short-circuits: no agents called, quality_report.no_changes=true."""
        repo_id, _full_job_id = await self._run_full_generation(
            client,
            db_session,
            prefect_harness,
        )

        incr_patches, incr_structure_mock, _ = _incremental_patches(
            compare_files=[],  # Empty diff
        )

        with contextlib.ExitStack() as stack:
            for p in incr_patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                },
            )
            assert resp.status_code == 201
            incr_data = resp.json()
            assert incr_data["mode"] == "incremental"
            incr_job_id = incr_data["id"]

            result = await _poll_job(client, incr_job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", f"No-changes incremental failed: {result.get('error_message')}"

        # quality_report should contain no_changes=true
        qr = result.get("quality_report")
        assert qr is not None, "Expected quality_report to be set"
        assert qr.get("no_changes") is True, f"Expected no_changes=true in quality_report, got: {qr}"

        # No structure extraction should have been called
        assert incr_structure_mock.call_count == 0, "StructureExtractor should NOT be called for no-changes incremental"

    # ------------------------------------------------------------------
    # 4.8: test_structural_change
    # ------------------------------------------------------------------

    async def test_structural_change(self, client, db_session, prefect_harness):
        """Structural file changes trigger StructureExtractor re-extraction."""
        repo_id, _full_job_id = await self._run_full_generation(
            client,
            db_session,
            prefect_harness,
        )

        incr_structure_mock = make_structure_stub()

        # __init__.py is a structural indicator — triggers re-extraction
        incr_patches, _, _ = _incremental_patches(
            compare_files=["src/__init__.py"],
            structure_mock=incr_structure_mock,
        )

        with contextlib.ExitStack() as stack:
            for p in incr_patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                },
            )
            assert resp.status_code == 201
            incr_data = resp.json()
            assert incr_data["mode"] == "incremental"
            incr_job_id = incr_data["id"]

            result = await _poll_job(client, incr_job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Structural-change incremental failed: {result.get('error_message')}"
            )

        # StructureExtractor SHOULD have been called because __init__.py is
        # a structural indicator detected by _detect_structural_changes()
        assert incr_structure_mock.call_count > 0, "StructureExtractor should be called when structural files change"

    # ------------------------------------------------------------------
    # 4.9: test_no_baseline_auto_detects_full
    # ------------------------------------------------------------------

    async def test_no_baseline_auto_detects_full(self, client, db_session, prefect_harness):
        """Without prior structure, mode auto-detection selects 'full' (not incremental)."""
        # Register repo but do NOT run full generation
        resp = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/test/fresh-project",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201
        repo_id = resp.json()["id"]

        patches = _full_generation_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # Create job without force — should auto-detect "full" because
            # no wiki structure exists for this repo
            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                    "force": False,
                },
            )
            assert resp.status_code == 201
            job_data = resp.json()

            # The key assertion: mode should be "full" when no baseline exists
            assert job_data["mode"] == "full", (
                f"Expected mode=full for repo with no prior structure, got: {job_data['mode']}"
            )
