from __future__ import annotations

import asyncio
import contextlib
import os
import shutil
import uuid
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.errors import PermanentError, QualityError, TransientError
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

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "sample-repo")

_REPO_COUNTER = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register_repo(client) -> dict:
    """Register a sample repository and return the JSON response body.

    Each call uses a unique URL suffix so that tests within the same DB
    transaction do not collide on the unique URL constraint.
    """
    global _REPO_COUNTER
    _REPO_COUNTER += 1
    resp = await client.post(
        "/repositories",
        json={
            "url": f"https://github.com/test-org/sample-project-{_REPO_COUNTER}",
            "provider": "github",
            "branch_mappings": {"main": "production"},
            "public_branch": "main",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _poll_job(client, job_id: str, *, timeout: float = 15.0) -> dict:
    """Poll GET /jobs/{id} until a terminal status or *timeout* seconds."""
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


def _make_good_scope_result(*, write_structure: bool = False) -> ScopeProcessingResult | None:
    """Build a canned ScopeProcessingResult that passes the quality gate.

    If *write_structure* is True, return ``None`` (caller must use a
    side_effect that writes to the DB instead).
    """
    if write_structure:
        return None

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


def _default_autodoc_config():
    """Return a default AutodocConfig(scope_path=".")."""
    from src.services.config_loader import AutodocConfig

    return AutodocConfig(scope_path=".")


def _flow_patches(
    *,
    clone_side_effect=None,
    scope_result: ScopeProcessingResult | None = _make_good_scope_result(),
    scope_side_effect=None,
    close_stale_mock=None,
    create_pr_mock=None,
    callback_mock=None,
):
    """Return a list of ``patch`` context managers for all external calls.

    Strategy: we patch at the *import site* inside the flow orchestrator
    modules (``full_generation``, ``incremental_update``).  By stubbing
    ``scope_processing_flow`` we avoid running any agent code, embedding
    generation, or internal DB writes that would require a real
    DATABASE_URL.

    For clone we also patch at the orchestrator import site because both
    ``full_generation`` and ``incremental_update`` import
    ``clone_repository`` at module level.
    """
    if clone_side_effect is None:
        clone_side_effect = make_clone_stub(fixture_path=FIXTURE_PATH)

    scope_mock = AsyncMock(side_effect=scope_side_effect, return_value=scope_result)

    if close_stale_mock is None and create_pr_mock is None:
        close_stale_mock, create_pr_mock = make_pr_stub()
    elif close_stale_mock is None:
        close_stale_mock = AsyncMock(return_value=0)
    elif create_pr_mock is None:
        create_pr_mock = AsyncMock(return_value="https://github.com/test/pull/1")

    if callback_mock is None:
        callback_mock = make_callback_stub()

    return [
        # Clone — at orchestrator import sites
        patch("src.flows.full_generation.clone_repository", side_effect=clone_side_effect),
        patch("src.flows.incremental_update.clone_repository", side_effect=clone_side_effect),
        # Scope processing — replaces entire sub-flow
        patch("src.flows.full_generation.scope_processing_flow", scope_mock),
        # Discover — return a single default config so the orchestrator has
        # exactly one scope to process (avoids real filesystem walk).
        patch(
            "src.flows.full_generation.discover_autodoc_configs",
            new_callable=AsyncMock,
            return_value=[_default_autodoc_config()],
        ),
        patch(
            "src.flows.incremental_update.discover_autodoc_configs",
            new_callable=AsyncMock,
            return_value=[_default_autodoc_config()],
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
    ]


# ---------------------------------------------------------------------------
# 4.11  Job Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestJobIdempotency:
    """POST /jobs returns existing active job instead of creating a duplicate."""

    async def test_duplicate_job_returns_200_with_same_id(self, client, db_session, prefect_harness):
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Override _submit_flow with a no-op so the job stays in PENDING
        # state between the two POST requests.  The prefect_harness fixture
        # already patches _submit_flow to run synchronously; here we
        # replace it with a no-op so the flow never executes and the job
        # remains active (PENDING) for the idempotency check.
        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            # First request — creates a new job (201)
            resp1 = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp1.status_code == 201, resp1.text
            job1 = resp1.json()

            # Second request with identical params — should return the
            # existing active job (200) because the first is still PENDING
            resp2 = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp2.status_code == 200, resp2.text
            job2 = resp2.json()

            assert job1["id"] == job2["id"], "Expected idempotent return of the same job ID"


# ---------------------------------------------------------------------------
# 4.12  Transient Error Retry
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestTransientErrorRetry:
    """Clone task retries on TransientError and job eventually completes."""

    async def test_transient_error_retried_to_completion(self, client, db_session, prefect_harness):
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # To test Prefect task retry, we must NOT replace clone_repository
        # at the flow import site (that would bypass the Prefect task
        # decorator and its retry logic).  Instead, we patch the provider
        # inside the clone task so the @task(retries=2) decorator is still
        # active.  The provider's clone_repository raises TransientError on
        # the first call, then succeeds on subsequent calls.
        call_count = 0

        async def _clone_with_transient_retry(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TransientError("network timeout")
            dest_dir = kwargs.get("dest_dir") or args[3]
            temp_dir = dest_dir
            shutil.copytree(FIXTURE_PATH, temp_dir, dirs_exist_ok=True)
            return (temp_dir, "abc123fake")

        mock_provider = MagicMock()
        mock_provider.clone_repository = AsyncMock(side_effect=_clone_with_transient_retry)

        # Build patches: use the provider-level patch for clone instead of
        # replacing the whole clone_repository task.
        scope_result = _make_good_scope_result()
        scope_mock = AsyncMock(return_value=scope_result)
        close_stale_mock, create_pr_mock = make_pr_stub()
        callback_mock = make_callback_stub()

        patches = [
            # Clone provider — patched inside clone task so Prefect retries work
            patch("src.flows.tasks.clone.get_provider", return_value=mock_provider),
            # Scope processing — replaces entire sub-flow
            patch("src.flows.full_generation.scope_processing_flow", scope_mock),
            # Discover
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_default_autodoc_config()],
            ),
            # PR
            patch("src.flows.full_generation.close_stale_autodoc_prs", close_stale_mock),
            patch("src.flows.full_generation.create_autodoc_pr", create_pr_mock),
            # Metrics
            patch("src.flows.full_generation.aggregate_job_metrics", new_callable=AsyncMock, return_value={}),
            # Callback
            patch("src.flows.full_generation.deliver_callback", callback_mock),
            # Cleanup
            patch("src.flows.full_generation.cleanup_workspace", new_callable=AsyncMock),
        ]

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED after transient retry, got {result['status']}: {result.get('error_message')}"
            )


# ---------------------------------------------------------------------------
# 4.13  Permanent Error
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestPermanentError:
    """Clone raises PermanentError -> job ends up FAILED."""

    async def test_permanent_error_fails_job(self, client, db_session, prefect_harness):
        repo = await _register_repo(client)
        repo_id = repo["id"]

        async def _always_fail(*args, **kwargs):
            raise PermanentError("repository not found")

        patches = _flow_patches(clone_side_effect=_always_fail)

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "FAILED"
            assert "repository not found" in (result.get("error_message") or "")


# ---------------------------------------------------------------------------
# 4.14  Quality Error
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestQualityError:
    """Structure extraction below minimum floor -> job FAILED, no pages."""

    async def test_quality_error_fails_job_with_no_pages(self, client, db_session, prefect_harness):
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # scope_processing_flow raises QualityError when the structure
        # score is below the minimum floor.  All scopes failing means the
        # orchestrator flow sees all results as exceptions and raises
        # PermanentError("All N scope(s) failed").
        async def _quality_error_scope(*args, **kwargs):
            raise QualityError("Structure extraction below minimum floor for scope '.' (score=3.0)")

        patches = _flow_patches(scope_side_effect=_quality_error_scope)

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "FAILED", (
                f"Expected FAILED due to quality gate, got {result['status']}: {result.get('error_message')}"
            )

            # Verify quality-related error message.
            # The orchestrator catches the all-scopes-failed case and wraps
            # it in a PermanentError whose message includes "scope(s) failed".
            error_msg = result.get("error_message") or ""
            assert any(kw in error_msg.lower() for kw in ("quality", "scope", "failed")), (
                f"Expected quality/scope error, got: {error_msg}"
            )

            # No structure should have been created (the scope_processing_flow
            # raised before any DB write).
            structure_resp = await client.get(f"/jobs/{job_id}/structure")
            assert structure_resp.status_code == 404


# ---------------------------------------------------------------------------
# 4.25  Mode Auto-Detection
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestModeAutoDetection:
    """First job is full; second auto-detects incremental; force overrides."""

    async def test_mode_auto_detection_and_force_override(self, client, db_session, prefect_harness):
        repo = await _register_repo(client)
        repo_id = repo["id"]

        clone_stub = make_clone_stub(fixture_path=FIXTURE_PATH)

        # For mode auto-detection, the second job must see a wiki_structure
        # row in the DB created by the first job.  We achieve this by
        # giving the scope_processing_flow mock a side_effect that writes
        # a structure row to the test DB (via the patched session factory)
        # and then returns a normal ScopeProcessingResult.
        agent_stub = make_structure_stub(score=8.2, below_floor=False)
        spec = agent_stub.return_value.output
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

            return ScopeProcessingResult(
                structure_result=StructureTaskResult(
                    final_score=8.2,
                    passed_quality_gate=True,
                    below_minimum_floor=False,
                    attempts=1,
                    token_usage=TokenUsageResult(input_tokens=1500, output_tokens=800, total_tokens=2300, calls=2),
                    output_title=spec.title,
                    output_description=spec.description,
                    sections_json=sections_json,
                ),
                page_results=[],
                readme_result=ReadmeTaskResult(
                    final_score=7.5,
                    passed_quality_gate=True,
                    below_minimum_floor=False,
                    attempts=1,
                    content="# README\n",
                    token_usage=TokenUsageResult(input_tokens=100, output_tokens=50, total_tokens=150, calls=1),
                ),
            )

        patches = _flow_patches(
            clone_side_effect=clone_stub,
            scope_side_effect=_scope_with_db_write,
            scope_result=None,
        )

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # --- First job: should be "full" (no prior structure) ---
            resp1 = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp1.status_code == 201
            job1 = resp1.json()
            assert job1["mode"] == "full", f"First job should be full mode, got {job1['mode']}"

            # Wait for the full generation flow to complete so the
            # wiki_structure row is committed to the test DB.
            result1 = await _poll_job(client, job1["id"], timeout=30.0)
            assert result1["status"] == "COMPLETED", (
                f"First job should complete, got {result1['status']}: {result1.get('error_message')}"
            )

            # --- Second job: should be "incremental" (structure now exists) ---
            resp2 = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp2.status_code == 201
            job2 = resp2.json()
            assert job2["mode"] == "incremental", f"Second job should be incremental mode, got {job2['mode']}"

            # The incremental flow will likely fail because
            # provider.compare_commits is not stubbed, but the mode
            # detection is the primary assertion.
            await _poll_job(client, job2["id"], timeout=30.0)

            # --- Third job: force=true should override to "full" ---
            resp3 = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                    "force": True,
                },
            )
            assert resp3.status_code == 201
            job3 = resp3.json()
            assert job3["mode"] == "full", f"Forced job should be full mode, got {job3['mode']}"


# ---------------------------------------------------------------------------
# 4.26  Job Creation Validation
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestJobCreationValidation:
    """Validation errors return appropriate HTTP status codes."""

    async def test_nonexistent_repository_returns_404(self, client, db_session, prefect_harness):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            "/jobs",
            json={"repository_id": fake_id, "branch": "main"},
        )
        assert resp.status_code == 404, resp.text
        assert "not found" in resp.json()["detail"].lower()

    async def test_invalid_branch_returns_422(self, client, db_session, prefect_harness):
        repo = await _register_repo(client)
        repo_id = repo["id"]

        resp = await client.post(
            "/jobs",
            json={
                "repository_id": repo_id,
                "branch": "nonexistent-branch",
            },
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert "nonexistent-branch" in detail
        assert "branch_mappings" in detail


# ---------------------------------------------------------------------------
# 5.9-5.13  Job Cancel
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestJobCancel:
    """POST /jobs/{id}/cancel cancels PENDING/RUNNING jobs; rejects terminal states."""

    async def test_cancel_pending(self, client, db_session, prefect_harness):
        """5.10: Cancel a PENDING job -> 200, status CANCELLED."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Patch _submit_flow with a no-op so the job stays PENDING
        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            # Verify job is PENDING before cancellation
            get_resp = await client.get(f"/jobs/{job_id}")
            assert get_resp.json()["status"] == "PENDING"

            # Cancel the PENDING job
            cancel_resp = await client.post(f"/jobs/{job_id}/cancel")
            assert cancel_resp.status_code == 200, cancel_resp.text
            assert cancel_resp.json()["status"] == "CANCELLED"

            # Confirm the status persisted
            get_resp2 = await client.get(f"/jobs/{job_id}")
            assert get_resp2.json()["status"] == "CANCELLED"

    async def test_cancel_running(self, client, db_session, prefect_harness):
        """5.11: Cancel a RUNNING job -> 200, status CANCELLED."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Use a slow scope_processing_flow to keep the job RUNNING
        hold_event = asyncio.Event()

        async def _slow_scope(**kwargs):
            """Block until the event is set, keeping the flow RUNNING."""
            await hold_event.wait()
            return _make_good_scope_result()

        patches = _flow_patches(scope_side_effect=_slow_scope, scope_result=None)

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            # Wait briefly for the flow to move to RUNNING
            deadline = asyncio.get_event_loop().time() + 10.0
            while asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.1)
                get_resp = await client.get(f"/jobs/{job_id}")
                if get_resp.json()["status"] == "RUNNING":
                    break

            # Cancel while RUNNING (or still PENDING — both are cancellable)
            cancel_resp = await client.post(f"/jobs/{job_id}/cancel")
            assert cancel_resp.status_code == 200, cancel_resp.text
            assert cancel_resp.json()["status"] == "CANCELLED"

            # Release the blocked scope so the background task can exit
            hold_event.set()

    async def test_cancel_completed_returns_409(self, client, db_session, prefect_harness):
        """5.12: Cancel a COMPLETED job -> 409."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

            # Attempt to cancel a completed job
            cancel_resp = await client.post(f"/jobs/{job_id}/cancel")
            assert cancel_resp.status_code == 409, cancel_resp.text
            assert "COMPLETED" in cancel_resp.json()["detail"]

    async def test_cancel_already_cancelled_returns_409(self, client, db_session, prefect_harness):
        """5.13: Cancel an already-cancelled job -> 409."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            # First cancel succeeds
            cancel_resp1 = await client.post(f"/jobs/{job_id}/cancel")
            assert cancel_resp1.status_code == 200
            assert cancel_resp1.json()["status"] == "CANCELLED"

            # Second cancel returns 409
            cancel_resp2 = await client.post(f"/jobs/{job_id}/cancel")
            assert cancel_resp2.status_code == 409, cancel_resp2.text
            assert "CANCELLED" in cancel_resp2.json()["detail"]


# ---------------------------------------------------------------------------
# 6.8-6.13  Job Listing
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestJobListing:
    """GET /jobs with filters and pagination."""

    async def test_filter_by_repository_id(self, client, db_session, prefect_harness):
        """6.9: Filter jobs by repository_id returns only that repo's jobs."""
        repo_a = await _register_repo(client)
        repo_b = await _register_repo(client)

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # Create a job for repo A
            resp_a = await client.post(
                "/jobs",
                json={"repository_id": repo_a["id"], "branch": "main"},
            )
            assert resp_a.status_code == 201
            job_a = resp_a.json()
            await _poll_job(client, job_a["id"], timeout=30.0)

            # Create a job for repo B
            resp_b = await client.post(
                "/jobs",
                json={"repository_id": repo_b["id"], "branch": "main"},
            )
            assert resp_b.status_code == 201
            job_b = resp_b.json()
            await _poll_job(client, job_b["id"], timeout=30.0)

        # Filter by repo A
        list_resp = await client.get(f"/jobs?repository_id={repo_a['id']}")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) >= 1
        assert all(item["repository_id"] == repo_a["id"] for item in items)
        assert not any(item["repository_id"] == repo_b["id"] for item in items)

    async def test_filter_by_status(self, client, db_session, prefect_harness):
        """6.10: Filter by status=COMPLETED returns only completed jobs."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Create a job that completes successfully
        success_patches = _flow_patches()
        with contextlib.ExitStack() as stack:
            for p in success_patches:
                stack.enter_context(p)
            resp_ok = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp_ok.status_code == 201
            result = await _poll_job(client, resp_ok.json()["id"], timeout=30.0)
            assert result["status"] == "COMPLETED"

        # Create a job that fails
        async def _always_fail(*args, **kwargs):
            raise PermanentError("forced failure for filter test")

        fail_patches = _flow_patches(clone_side_effect=_always_fail)
        with contextlib.ExitStack() as stack:
            for p in fail_patches:
                stack.enter_context(p)
            resp_fail = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main", "force": True},
            )
            assert resp_fail.status_code == 201
            result = await _poll_job(client, resp_fail.json()["id"], timeout=30.0)
            assert result["status"] == "FAILED"

        # Filter by COMPLETED
        list_resp = await client.get(f"/jobs?repository_id={repo_id}&status=COMPLETED")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) >= 1
        assert all(item["status"] == "COMPLETED" for item in items)

    async def test_filter_by_branch(self, client, db_session, prefect_harness):
        """6.11: Filter by branch returns correct results."""
        # Register a repo with two branches
        global _REPO_COUNTER
        _REPO_COUNTER += 1
        resp = await client.post(
            "/repositories",
            json={
                "url": f"https://github.com/test-org/branch-filter-{_REPO_COUNTER}",
                "provider": "github",
                "branch_mappings": {"main": "production", "develop": "staging"},
                "public_branch": "main",
            },
        )
        assert resp.status_code == 201
        repo = resp.json()
        repo_id = repo["id"]

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            # Create job on main
            resp_main = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp_main.status_code == 201
            await _poll_job(client, resp_main.json()["id"], timeout=30.0)

            # Create job on develop
            resp_dev = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "develop"},
            )
            assert resp_dev.status_code == 201
            await _poll_job(client, resp_dev.json()["id"], timeout=30.0)

        # Filter by branch=develop
        list_resp = await client.get(f"/jobs?repository_id={repo_id}&branch=develop")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) >= 1
        assert all(item["branch"] == "develop" for item in items)

    async def test_combined_filters(self, client, db_session, prefect_harness):
        """6.12: Filter by repo_id + status uses AND logic."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Create a completed job
        success_patches = _flow_patches()
        with contextlib.ExitStack() as stack:
            for p in success_patches:
                stack.enter_context(p)
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            result = await _poll_job(client, resp.json()["id"], timeout=30.0)
            assert result["status"] == "COMPLETED"

        # Combined filter: repo_id + status=FAILED should return nothing
        # because the only job for this repo is COMPLETED
        list_resp = await client.get(f"/jobs?repository_id={repo_id}&status=FAILED")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert items == []

        # Combined filter: repo_id + status=COMPLETED should return the job
        list_resp2 = await client.get(f"/jobs?repository_id={repo_id}&status=COMPLETED")
        assert list_resp2.status_code == 200
        items2 = list_resp2.json()["items"]
        assert len(items2) >= 1
        assert all(item["repository_id"] == repo_id for item in items2)
        assert all(item["status"] == "COMPLETED" for item in items2)

    async def test_empty_job_results(self, client, db_session, prefect_harness):
        """6.13: Filter by status=CANCELLED with no cancelled jobs returns empty."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Create a completed job (not cancelled)
        patches = _flow_patches()
        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            result = await _poll_job(client, resp.json()["id"], timeout=30.0)
            assert result["status"] == "COMPLETED"

        # Filter by CANCELLED — should be empty
        list_resp = await client.get(f"/jobs?repository_id={repo_id}&status=CANCELLED")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert data["items"] == []


# ---------------------------------------------------------------------------
# 6.14-6.18  Job Detail
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestJobDetail:
    """GET /jobs/{id} detail checks for quality_report, error, tasks, and logs."""

    async def test_completed_job_has_quality_report(self, client, db_session, prefect_harness):
        """6.14: Completed job GET returns quality_report and token_usage."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

        # Fetch the job detail
        detail_resp = await client.get(f"/jobs/{job_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "COMPLETED"
        # quality_report and token_usage may or may not be set depending on
        # whether aggregate_job_metrics populates them.  The key assertion is
        # that the fields are present in the response schema.
        assert "quality_report" in detail
        assert "token_usage" in detail

    async def test_failed_job_has_error_message(self, client, db_session, prefect_harness):
        """6.15: Failed job GET returns error_message."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        async def _always_fail(*args, **kwargs):
            raise PermanentError("deliberate failure for detail test")

        patches = _flow_patches(clone_side_effect=_always_fail)

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "FAILED"

        detail_resp = await client.get(f"/jobs/{job_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "FAILED"
        assert detail["error_message"] is not None
        assert "deliberate failure" in detail["error_message"]

    async def test_nonexistent_job(self, client, db_session, prefect_harness):
        """6.16: GET /jobs/{random_uuid} returns 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/jobs/{fake_id}")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_tasks_without_flow_run_id(self, client, db_session, prefect_harness):
        """6.17: PENDING job with no flow run returns empty task list."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            # Job is PENDING with no prefect_flow_run_id
            tasks_resp = await client.get(f"/jobs/{job_id}/tasks")
            assert tasks_resp.status_code == 200
            assert tasks_resp.json() == []

    async def test_logs_without_flow_run_id(self, client, db_session, prefect_harness):
        """6.18: PENDING job with no flow run returns empty log list."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            # Job is PENDING with no prefect_flow_run_id
            logs_resp = await client.get(f"/jobs/{job_id}/logs")
            assert logs_resp.status_code == 200
            assert logs_resp.json() == []


# ---------------------------------------------------------------------------
# 5.14-5.17  Job Retry
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestJobRetry:
    """POST /jobs/{id}/retry resets FAILED jobs to PENDING; rejects non-FAILED states."""

    async def test_retry_failed_job(self, client, db_session, prefect_harness):
        """5.15: Retry a FAILED job -> 200, resets to PENDING, eventually COMPLETED."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # First, create a job that fails permanently
        async def _always_fail(*args, **kwargs):
            raise PermanentError("repository not found")

        fail_patches = _flow_patches(clone_side_effect=_always_fail)

        with contextlib.ExitStack() as stack:
            for p in fail_patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "FAILED"

        # Now retry the failed job — this time with working patches
        success_patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in success_patches:
                stack.enter_context(p)

            retry_resp = await client.post(f"/jobs/{job_id}/retry")
            assert retry_resp.status_code == 200, retry_resp.text
            assert retry_resp.json()["status"] == "PENDING"

            # The retried job should eventually complete
            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED after retry, got {result['status']}: {result.get('error_message')}"
            )

    async def test_retry_non_failed_returns_409(self, client, db_session, prefect_harness):
        """5.16: Retry a COMPLETED job -> 409."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        patches = _flow_patches()

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED"

            # Attempt to retry a completed job
            retry_resp = await client.post(f"/jobs/{job_id}/retry")
            assert retry_resp.status_code == 409, retry_resp.text
            assert "COMPLETED" in retry_resp.json()["detail"]

    async def test_retry_nonexistent_returns_404(self, client, db_session, prefect_harness):
        """5.17: Retry a nonexistent job -> 404."""
        fake_id = str(uuid.uuid4())
        retry_resp = await client.post(f"/jobs/{fake_id}/retry")
        assert retry_resp.status_code == 404, retry_resp.text
        assert "not found" in retry_resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 5.24-5.26  Callback Delivery
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestCallbackDelivery:
    """Callback webhook is delivered on job completion and failure."""

    async def test_callback_on_success(self, client, db_session, prefect_harness):
        """5.25: Callback delivered with status=COMPLETED on successful job."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        callback_mock = make_callback_stub()
        patches = _flow_patches(callback_mock=callback_mock)

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                    "callback_url": "https://example.com/callback",
                },
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

            # Verify callback was called
            assert callback_mock.call_count >= 1, "Callback should have been called"

            # Verify callback was called with the correct status
            call_kwargs = callback_mock.call_args.kwargs
            assert call_kwargs["status"] == "COMPLETED"
            assert call_kwargs["job_id"] == uuid.UUID(job_id)
            assert call_kwargs["callback_url"] == "https://example.com/callback"

    async def test_callback_on_failure(self, client, db_session, prefect_harness):
        """5.26: Callback delivered with status=FAILED on failed job."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        async def _always_fail(*args, **kwargs):
            raise PermanentError("clone failed permanently")

        callback_mock = make_callback_stub()
        patches = _flow_patches(
            clone_side_effect=_always_fail,
            callback_mock=callback_mock,
        )

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={
                    "repository_id": repo_id,
                    "branch": "main",
                    "callback_url": "https://example.com/callback",
                },
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "FAILED"

            # Verify callback was called with FAILED status
            assert callback_mock.call_count >= 1, "Callback should have been called on failure"

            call_kwargs = callback_mock.call_args.kwargs
            assert call_kwargs["status"] == "FAILED"
            assert call_kwargs["job_id"] == uuid.UUID(job_id)
            assert call_kwargs["callback_url"] == "https://example.com/callback"
            assert call_kwargs.get("error_message") is not None


# ---------------------------------------------------------------------------
# 5.27  Stale PR Cleanup
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestStalePrCleanup:
    """Stale autodoc PRs are closed before a new PR is created."""

    async def test_stale_prs_closed_before_new_pr(self, client, db_session, prefect_harness):
        """5.27: close_stale_autodoc_prs called before create_autodoc_pr."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        # Track invocation order using a shared list
        call_order: list[str] = []

        async def _close_stale_tracking(*args, **kwargs):
            call_order.append("close_stale")
            return 0

        async def _create_pr_tracking(*args, **kwargs):
            call_order.append("create_pr")
            return "https://github.com/test/sample-project/pull/999"

        close_stale_mock = AsyncMock(side_effect=_close_stale_tracking)
        create_pr_mock = AsyncMock(side_effect=_create_pr_tracking)

        patches = _flow_patches(
            close_stale_mock=close_stale_mock,
            create_pr_mock=create_pr_mock,
        )

        with contextlib.ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)

            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id, "branch": "main"},
            )
            assert resp.status_code == 201
            job_id = resp.json()["id"]

            result = await _poll_job(client, job_id, timeout=30.0)
            assert result["status"] == "COMPLETED", (
                f"Expected COMPLETED, got {result['status']}: {result.get('error_message')}"
            )

            # Verify both were called
            assert close_stale_mock.call_count >= 1, "close_stale_autodoc_prs should have been called"
            assert create_pr_mock.call_count >= 1, "create_autodoc_pr should have been called"

            # Verify ordering: close_stale was called before create_pr
            assert call_order.index("close_stale") < call_order.index("create_pr"), (
                f"Expected close_stale before create_pr, got order: {call_order}"
            )
