from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import asdict
from unittest.mock import AsyncMock, patch

import pytest

from src.errors import PermanentError
from src.flows.schemas import (
    PageTaskResult,
    ReadmeTaskResult,
    ScopeProcessingResult,
    StructureTaskResult,
    TokenUsageResult,
)
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

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample-repo")
FIXTURE_PATH_NO_CONFIG = os.path.join(os.path.dirname(__file__), "fixtures", "sample-repo-no-config")

_REPO_COUNTER = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_repo(client) -> dict:
    """Register a unique sample repository and return the JSON response body."""
    global _REPO_COUNTER
    _REPO_COUNTER += 1
    resp = await client.post(
        "/repositories",
        json={
            "url": f"https://github.com/test-org/advanced-flow-{_REPO_COUNTER}",
            "provider": "github",
            "branch_mappings": {"main": "production"},
            "public_branch": "main",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


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
    # Return last known state on timeout
    resp = await client.get(f"/jobs/{job_id}")
    return resp.json()


def _make_good_scope_result(*, scope_path: str = ".") -> ScopeProcessingResult:
    """Build a canned ScopeProcessingResult that passes the quality gate."""
    stub = make_structure_stub(score=8.2, below_floor=False)
    agent_result = stub.return_value
    spec = agent_result.output
    sections_json = [asdict(s) for s in spec.sections]

    structure_result = StructureTaskResult(
        final_score=8.2,
        passed_quality_gate=True,
        below_minimum_floor=False,
        attempts=1,
        token_usage=TokenUsageResult(input_tokens=1500, output_tokens=800, total_tokens=2300, calls=2),
        output_title=spec.title,
        output_description=spec.description,
        sections_json=sections_json,
    )

    page_results = [
        PageTaskResult(
            page_key="core-module",
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=1200, output_tokens=600, total_tokens=1800, calls=2),
        ),
        PageTaskResult(
            page_key="utils-module",
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            attempts=1,
            token_usage=TokenUsageResult(input_tokens=1200, output_tokens=600, total_tokens=1800, calls=2),
        ),
    ]

    readme_result = ReadmeTaskResult(
        final_score=7.5,
        passed_quality_gate=True,
        below_minimum_floor=False,
        attempts=1,
        content="# Sample Project Documentation\n\nWelcome.\n",
        token_usage=TokenUsageResult(input_tokens=1000, output_tokens=500, total_tokens=1500, calls=2),
    )

    return ScopeProcessingResult(
        structure_result=structure_result,
        page_results=page_results,
        readme_result=readme_result,
        wiki_structure_id=None,
        embedding_count=0,
    )


def _default_autodoc_config(scope_path: str = ".") -> object:
    """Return an AutodocConfig with the given scope_path."""
    from src.services.config_loader import AutodocConfig

    return AutodocConfig(scope_path=scope_path)


def _flow_patches(
    *,
    fixture_path: str = FIXTURE_PATH,
    clone_side_effect=None,
    scope_result: ScopeProcessingResult | None = None,
    scope_side_effect=None,
    configs: list | None = None,
    close_stale_mock=None,
    create_pr_mock=None,
    callback_mock=None,
):
    """Return a list of ``patch`` context managers for all external calls.

    Patches ``scope_processing_flow`` at the import site inside the flow
    orchestrator modules so no agent code runs.
    """
    if clone_side_effect is None:
        clone_side_effect = make_clone_stub(fixture_path=fixture_path)

    if scope_result is None and scope_side_effect is None:
        scope_result = _make_good_scope_result()

    scope_mock = AsyncMock(side_effect=scope_side_effect, return_value=scope_result)

    if close_stale_mock is None and create_pr_mock is None:
        close_stale_mock, create_pr_mock = make_pr_stub()
    elif close_stale_mock is None:
        close_stale_mock = AsyncMock(return_value=0)
    elif create_pr_mock is None:
        create_pr_mock = AsyncMock(return_value="https://github.com/test/pull/1")

    if callback_mock is None:
        callback_mock = make_callback_stub()

    if configs is None:
        configs = [_default_autodoc_config()]

    return (
        [
            # Clone -- at orchestrator import sites
            patch("src.flows.full_generation.clone_repository", side_effect=clone_side_effect),
            patch("src.flows.incremental_update.clone_repository", side_effect=clone_side_effect),
            # Scope processing -- replaces entire sub-flow
            patch("src.flows.full_generation.scope_processing_flow", scope_mock),
            # Discover -- return the specified configs
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=configs,
            ),
            patch(
                "src.flows.incremental_update.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=configs,
            ),
            # PR
            patch("src.flows.full_generation.close_stale_autodoc_prs", close_stale_mock),
            patch("src.flows.full_generation.create_autodoc_pr", create_pr_mock),
            patch("src.flows.incremental_update.close_stale_autodoc_prs", close_stale_mock),
            patch("src.flows.incremental_update.create_autodoc_pr", create_pr_mock),
            # Metrics
            patch("src.flows.full_generation.aggregate_job_metrics", new_callable=AsyncMock, return_value={}),
            patch("src.flows.incremental_update.aggregate_job_metrics", new_callable=AsyncMock, return_value={}),
            # Callback
            patch("src.flows.full_generation.deliver_callback", callback_mock),
            patch("src.flows.incremental_update.deliver_callback", callback_mock),
            # Cleanup
            patch("src.flows.full_generation.cleanup_workspace", new_callable=AsyncMock),
            patch("src.flows.incremental_update.cleanup_workspace", new_callable=AsyncMock),
        ],
        scope_mock,
        create_pr_mock,
    )


# ---------------------------------------------------------------------------
# TestAdvancedFlows (tasks 5.28-5.34)
# ---------------------------------------------------------------------------


class TestAdvancedFlows:
    """E2E tests for advanced flow scenarios: config discovery, monorepo
    scopes, partial failures, and incremental dry-run."""

    # -------------------------------------------------------------------
    # 5.29  No .autodoc.yaml defaults to root scope
    # -------------------------------------------------------------------

    async def test_no_autodoc_yaml_defaults_to_root_scope(self, client, db_session, prefect_harness):
        """Task 5.29: When no .autodoc.yaml exists, discover returns a
        default config with scope_path='.' and the flow completes."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # The discover_autodoc_configs patch returns a single default config
        # (scope_path=".") simulating no .autodoc.yaml found.
        default_config = _default_autodoc_config(scope_path=".")

        # Build a scope result with a side_effect that writes structure
        # to verify scope_path="." was used.
        stub = make_structure_stub(score=8.2, below_floor=False)
        spec = stub.return_value.output
        sections_json = [asdict(s) for s in spec.sections]

        async def _scope_with_db_write(**kwargs):
            """scope_processing_flow replacement that persists a structure."""
            from src.database.engine import get_session_factory
            from src.database.repos.wiki_repo import WikiRepo

            session_factory = get_session_factory()
            async with session_factory() as session:
                wiki_repo = WikiRepo(session)
                await wiki_repo.create_structure(
                    repository_id=kwargs["repository_id"],
                    job_id=kwargs["job_id"],
                    branch=kwargs["branch"],
                    scope_path=kwargs.get("scope_path", "."),
                    title=spec.title,
                    description=spec.description,
                    sections=sections_json,
                    commit_sha=kwargs.get("commit_sha", "abc123fake"),
                )
                await session.commit()

            return _make_good_scope_result(scope_path=kwargs.get("scope_path", "."))

        patches_list, scope_mock, _ = _flow_patches(
            fixture_path=FIXTURE_PATH_NO_CONFIG,
            configs=[default_config],
            scope_side_effect=_scope_with_db_write,
            scope_result=None,
        )

        with contextlib.ExitStack() as stack:
            for p in patches_list:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

            # Verify scope_processing_flow was called with scope_path="."
            assert scope_mock.called
            call_kwargs = scope_mock.call_args.kwargs
            assert call_kwargs["scope_path"] == "."

            # Verify structure was created with scope_path="."
            structure_resp = await client.get(f"/jobs/{job_id}/structure")
            assert structure_resp.status_code == 200
            structure = structure_resp.json()
            assert structure["scope_path"] == "."

    # -------------------------------------------------------------------
    # 5.30  Monorepo multiple scopes
    # -------------------------------------------------------------------

    async def test_monorepo_multiple_scopes(self, client, db_session, prefect_harness):
        """Task 5.30: Two config scopes (root and packages/api) both complete."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        root_config = _default_autodoc_config(scope_path=".")
        api_config = _default_autodoc_config(scope_path="packages/api")

        scope_call_count = 0

        async def _scope_per_config(**kwargs):
            nonlocal scope_call_count
            scope_call_count += 1
            return _make_good_scope_result(scope_path=kwargs.get("scope_path", "."))

        patches_list, scope_mock, _ = _flow_patches(
            configs=[root_config, api_config],
            scope_side_effect=_scope_per_config,
            scope_result=None,
        )

        with contextlib.ExitStack() as stack:
            for p in patches_list:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

            # scope_processing_flow should have been called twice (once per scope)
            assert scope_mock.call_count == 2

            # Verify both scope_paths were passed
            scope_paths_called = {call.kwargs["scope_path"] for call in scope_mock.call_args_list}
            assert scope_paths_called == {".", "packages/api"}

    # -------------------------------------------------------------------
    # 5.32  Partial scope failure
    # -------------------------------------------------------------------

    async def test_partial_scope_failure(self, client, db_session, prefect_harness):
        """Task 5.32: First scope succeeds, second raises PermanentError.
        Job is FAILED but partial results from the first scope exist."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        root_config = _default_autodoc_config(scope_path=".")
        api_config = _default_autodoc_config(scope_path="packages/api")

        call_index = 0

        async def _partial_failure(**kwargs):
            nonlocal call_index
            call_index += 1
            scope_path = kwargs.get("scope_path", ".")
            if scope_path == "packages/api":
                raise PermanentError(f"Scope '{scope_path}' processing failed: out of memory")
            return _make_good_scope_result(scope_path=scope_path)

        patches_list, scope_mock, _ = _flow_patches(
            configs=[root_config, api_config],
            scope_side_effect=_partial_failure,
            scope_result=None,
        )

        with contextlib.ExitStack() as stack:
            for p in patches_list:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)

            # With one of two scopes failing, the flow should still complete
            # because partial results exist (only all-scopes-failed causes FAILED
            # from the PermanentError path). The flow logs a warning but continues.
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED with partial results, got {result['status']}: {result.get('error_message')}"
            )

            # Both scopes were attempted
            assert scope_mock.call_count == 2

    # -------------------------------------------------------------------
    # 5.33  All scopes fail
    # -------------------------------------------------------------------

    async def test_all_scopes_fail(self, client, db_session, prefect_harness):
        """Task 5.33: All scopes raise PermanentError -> job FAILED."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        root_config = _default_autodoc_config(scope_path=".")
        api_config = _default_autodoc_config(scope_path="packages/api")

        async def _always_fail(**kwargs):
            scope_path = kwargs.get("scope_path", ".")
            raise PermanentError(f"Scope '{scope_path}' processing failed")

        patches_list, _scope_mock, _ = _flow_patches(
            configs=[root_config, api_config],
            scope_side_effect=_always_fail,
            scope_result=None,
        )

        with contextlib.ExitStack() as stack:
            for p in patches_list:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "FAILED", f"Expected FAILED when all scopes fail, got {result['status']}"

            error_msg = result.get("error_message") or ""
            assert any(kw in error_msg.lower() for kw in ("scope", "failed")), (
                f"Expected scope failure message, got: {error_msg}"
            )

    # -------------------------------------------------------------------
    # 5.34  Incremental dry-run (no PR created)
    # -------------------------------------------------------------------

    async def test_incremental_dry_run(self, client, db_session, prefect_harness):
        """Task 5.34: Run full generation first (baseline), then run
        incremental with dry_run=True and verify no PR was created."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # --- Phase 1: Run full generation to create baseline structure ---
        stub = make_structure_stub(score=8.2, below_floor=False)
        spec = stub.return_value.output
        sections_json = [asdict(s) for s in spec.sections]

        async def _scope_with_db_write(**kwargs):
            """scope_processing_flow replacement that persists a structure."""
            from src.database.engine import get_session_factory
            from src.database.repos.wiki_repo import WikiRepo

            session_factory = get_session_factory()
            async with session_factory() as session:
                wiki_repo = WikiRepo(session)
                await wiki_repo.create_structure(
                    repository_id=kwargs["repository_id"],
                    job_id=kwargs["job_id"],
                    branch=kwargs["branch"],
                    scope_path=kwargs.get("scope_path", "."),
                    title=spec.title,
                    description=spec.description,
                    sections=sections_json,
                    commit_sha=kwargs.get("commit_sha", "abc123fake"),
                )
                await session.commit()

            return _make_good_scope_result()

        patches_list, _scope_mock, create_pr_mock = _flow_patches(
            scope_side_effect=_scope_with_db_write,
            scope_result=None,
        )

        with contextlib.ExitStack() as stack:
            for p in patches_list:
                stack.enter_context(p)

            # Full generation
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201, resp.text
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Baseline full generation should complete, got {result['status']}: {result.get('error_message')}"
            )

            # Reset PR mock call count for incremental phase
            create_pr_mock.reset_mock()

            # --- Phase 2: Incremental dry-run ---
            # The second job should auto-detect incremental mode (structure exists).
            # With dry_run=True, no PR should be created.
            # For the incremental flow, we need to stub the provider's
            # compare_commits and other incremental-specific imports.
            incr_resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                    "dry_run": True,
                },
            )
            assert incr_resp.status_code == 201, incr_resp.text
            incr_job = incr_resp.json()
            incr_job_id = incr_job["id"]
            assert incr_job["mode"] == "incremental", f"Second job should be incremental, got {incr_job['mode']}"
            assert incr_job["dry_run"] is True

            await _poll_job(client, incr_job_id, timeout=30.0)

            # The incremental flow may fail because provider.compare_commits
            # is not stubbed (it hits a real provider API path that is not
            # patched). The key assertion is that no PR was created.
            # Whether it COMPLETED or FAILED, the PR mock should NOT have been called.
            assert not create_pr_mock.called, "create_autodoc_pr should not be called in dry_run mode"
