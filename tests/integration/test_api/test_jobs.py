"""Integration tests for job lifecycle endpoints.

Routes under test:
    POST /jobs
    GET  /jobs
    GET  /jobs/{job_id}
    POST /jobs/{job_id}/cancel
    POST /jobs/{job_id}/retry
    GET  /jobs/{job_id}/structure
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tests.integration.test_api.conftest import (
    JOB_ID,
    REPO_ID,
    STRUCTURE_ID,
    UNKNOWN_ID,
    make_job,
    make_repository,
    make_structure,
    make_structure_for_response,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _mock_update_status(job_id, status, **kwargs):
    """Simulate a DB update that returns a job with the new status."""
    return make_job(job_id=job_id, status=status, **kwargs)


# ===================================================================
# POST /jobs
# ===================================================================


class TestCreateJob:
    """Tests for POST /jobs."""

    async def test_create_new_job_returns_201(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """New job for a registered repo creates and returns 201."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = None  # -> full mode
        new_job = make_job(mode="full")
        mock_job_repo.create.return_value = new_job

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/jobs",
                json={"repository_id": str(REPO_ID)},
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(JOB_ID)
        assert data["repository_id"] == str(REPO_ID)
        assert data["status"] == "PENDING"
        assert data["mode"] == "full"
        assert data["branch"] == "main"
        assert data["force"] is False
        assert data["dry_run"] is False

    async def test_create_job_incremental_mode(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """When wiki structure already exists, mode is incremental."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()
        new_job = make_job(mode="incremental")
        mock_job_repo.create.return_value = new_job

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/jobs",
                json={"repository_id": str(REPO_ID)},
            )

        assert response.status_code == 201
        # Verify create was called with mode="incremental"
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["mode"] == "incremental"

    async def test_create_job_force_full(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """force=true always produces mode='full' regardless of existing structure."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()
        new_job = make_job(mode="full", force=True)
        mock_job_repo.create.return_value = new_job

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/jobs",
                json={"repository_id": str(REPO_ID), "force": True},
            )

        assert response.status_code == 201
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["mode"] == "full"
        assert call_kwargs["force"] is True

    async def test_idempotency_returns_existing_active_job_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """If an active job already exists, return it with status 200."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        existing_job = make_job(status="RUNNING")
        mock_job_repo.get_active_for_repo.return_value = existing_job

        response = await client.post(
            "/jobs",
            json={"repository_id": str(REPO_ID)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(JOB_ID)
        assert data["status"] == "RUNNING"
        # No new job should be created
        mock_job_repo.create.assert_not_awaited()

    async def test_repo_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Non-existent repository_id returns 404."""
        mock_repository_repo.get_by_id.return_value = None

        response = await client.post(
            "/jobs",
            json={"repository_id": str(UNKNOWN_ID)},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_branch_not_in_mappings_returns_422(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Branch not in branch_mappings returns 422."""
        mock_repository_repo.get_by_id.return_value = make_repository(
            branch_mappings={"main": "main"},
        )

        response = await client.post(
            "/jobs",
            json={
                "repository_id": str(REPO_ID),
                "branch": "feature/not-mapped",
            },
        )

        assert response.status_code == 422
        assert "not in repository branch_mappings" in response.json()["detail"]

    async def test_create_with_explicit_branch(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Explicit branch param overrides public_branch default."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = None
        mock_job_repo.create.return_value = make_job(branch="develop")

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/jobs",
                json={
                    "repository_id": str(REPO_ID),
                    "branch": "develop",
                },
            )

        assert response.status_code == 201
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["branch"] == "develop"

    async def test_create_with_callback_url(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """callback_url is passed through to job creation."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = None
        mock_job_repo.create.return_value = make_job(
            callback_url="https://example.com/webhook",
        )

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/jobs",
                json={
                    "repository_id": str(REPO_ID),
                    "callback_url": "https://example.com/webhook",
                },
            )

        assert response.status_code == 201
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["callback_url"] == "https://example.com/webhook"

    async def test_create_dry_run(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """dry_run=true is passed through to job creation."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = None
        mock_job_repo.create.return_value = make_job(dry_run=True)

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/jobs",
                json={
                    "repository_id": str(REPO_ID),
                    "dry_run": True,
                },
            )

        assert response.status_code == 201
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["dry_run"] is True


# ===================================================================
# GET /jobs
# ===================================================================


class TestListJobs:
    """Tests for GET /jobs."""

    async def test_list_empty(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Empty result returns empty items list."""
        mock_job_repo.list.return_value = []

        response = await client.get("/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["next_cursor"] is None
        assert data["limit"] == 20

    async def test_list_with_items(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Returns jobs as JobResponse objects."""
        jobs = [make_job(job_id=JOB_ID), make_job(job_id=uuid.uuid4())]
        mock_job_repo.list.return_value = jobs

        response = await client.get("/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    async def test_list_with_repository_id_filter(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """repository_id filter is passed to repo.list()."""
        mock_job_repo.list.return_value = []

        await client.get("/jobs", params={"repository_id": str(REPO_ID)})

        call_kwargs = mock_job_repo.list.call_args.kwargs
        assert call_kwargs["repository_id"] == REPO_ID

    async def test_list_with_status_filter(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """status filter is passed to repo.list()."""
        mock_job_repo.list.return_value = []

        await client.get("/jobs", params={"status": "RUNNING"})

        call_kwargs = mock_job_repo.list.call_args.kwargs
        assert call_kwargs["status"] == "RUNNING"

    async def test_list_with_branch_filter(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """branch filter is passed to repo.list()."""
        mock_job_repo.list.return_value = []

        await client.get("/jobs", params={"branch": "develop"})

        call_kwargs = mock_job_repo.list.call_args.kwargs
        assert call_kwargs["branch"] == "develop"

    async def test_list_pagination(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """When len(rows) == limit, next_cursor is set."""
        job_1 = make_job(job_id=JOB_ID)
        job_2_id = uuid.uuid4()
        job_2 = make_job(job_id=job_2_id)
        mock_job_repo.list.return_value = [job_1, job_2]

        response = await client.get("/jobs", params={"limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert data["next_cursor"] == str(job_2_id)
        assert data["limit"] == 2

    async def test_list_combined_filters(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Multiple filters can be combined."""
        mock_job_repo.list.return_value = []

        await client.get(
            "/jobs",
            params={
                "repository_id": str(REPO_ID),
                "status": "COMPLETED",
                "branch": "main",
                "limit": 5,
            },
        )

        call_kwargs = mock_job_repo.list.call_args.kwargs
        assert call_kwargs["repository_id"] == REPO_ID
        assert call_kwargs["status"] == "COMPLETED"
        assert call_kwargs["branch"] == "main"
        assert call_kwargs["limit"] == 5


# ===================================================================
# GET /jobs/{job_id}
# ===================================================================


class TestGetJob:
    """Tests for GET /jobs/{job_id}."""

    async def test_get_existing_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Known job_id returns full JobResponse."""
        mock_job_repo.get_by_id.return_value = make_job()

        response = await client.get(f"/jobs/{JOB_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(JOB_ID)
        assert data["repository_id"] == str(REPO_ID)
        assert data["status"] == "PENDING"
        assert data["mode"] == "full"
        assert data["branch"] == "main"
        assert data["force"] is False
        assert data["dry_run"] is False
        assert "created_at" in data
        assert "updated_at" in data

    async def test_get_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Unknown job_id returns 404."""
        mock_job_repo.get_by_id.return_value = None

        response = await client.get(f"/jobs/{UNKNOWN_ID}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    async def test_get_completed_job_includes_quality_report(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Completed job response includes quality_report and pull_request_url."""
        job = make_job(
            status="COMPLETED",
            pull_request_url="https://github.com/acme/widgets/pull/42",
        )
        job.quality_report = {
            "overall_score": 8.5,
            "quality_threshold": 7.0,
            "passed": True,
            "total_pages": 10,
        }
        mock_job_repo.get_by_id.return_value = job

        response = await client.get(f"/jobs/{JOB_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert data["quality_report"]["overall_score"] == 8.5
        assert data["pull_request_url"] == "https://github.com/acme/widgets/pull/42"

    async def test_get_failed_job_includes_error_message(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Failed job response includes error_message."""
        job = make_job(status="FAILED", error_message="Embedding service timeout")
        mock_job_repo.get_by_id.return_value = job

        response = await client.get(f"/jobs/{JOB_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "FAILED"
        assert data["error_message"] == "Embedding service timeout"


# ===================================================================
# POST /jobs/{job_id}/cancel
# ===================================================================


class TestCancelJob:
    """Tests for POST /jobs/{job_id}/cancel."""

    async def test_cancel_pending_job_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """PENDING job can be cancelled -> 200 with CANCELLED status."""
        mock_job_repo.get_by_id.return_value = make_job(status="PENDING")
        mock_job_repo.update_status.side_effect = _mock_update_status

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"
        mock_job_repo.update_status.assert_awaited_once_with(JOB_ID, "CANCELLED")

    async def test_cancel_running_job_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """RUNNING job with prefect_flow_run_id -> cancel via Prefect + DB update."""
        prefect_id = str(uuid.uuid4())
        mock_job_repo.get_by_id.return_value = make_job(
            status="RUNNING",
            prefect_flow_run_id=prefect_id,
        )
        mock_job_repo.update_status.side_effect = _mock_update_status

        mock_prefect_client = AsyncMock()
        mock_prefect_client.set_flow_run_state = AsyncMock()
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"
        mock_prefect_client.set_flow_run_state.assert_awaited_once()

    async def test_cancel_completed_job_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """COMPLETED job cannot be cancelled -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="COMPLETED")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 409
        assert "COMPLETED" in response.json()["detail"]
        assert "cannot be cancelled" in response.json()["detail"]

    async def test_cancel_failed_job_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """FAILED job cannot be cancelled -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="FAILED")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 409
        assert "FAILED" in response.json()["detail"]

    async def test_cancel_already_cancelled_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Already CANCELLED job -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="CANCELLED")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 409
        assert "CANCELLED" in response.json()["detail"]

    async def test_cancel_nonexistent_job_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Unknown job_id returns 404."""
        mock_job_repo.get_by_id.return_value = None

        response = await client.post(f"/jobs/{UNKNOWN_ID}/cancel")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    async def test_cancel_running_prefect_failure_still_updates_db(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """If Prefect API fails, the DB is still updated to CANCELLED."""
        prefect_id = str(uuid.uuid4())
        mock_job_repo.get_by_id.return_value = make_job(
            status="RUNNING",
            prefect_flow_run_id=prefect_id,
        )
        mock_job_repo.update_status.side_effect = _mock_update_status

        mock_prefect_client = AsyncMock()
        mock_prefect_client.set_flow_run_state = AsyncMock(
            side_effect=RuntimeError("Prefect unreachable")
        )
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"
        mock_job_repo.update_status.assert_awaited_once_with(JOB_ID, "CANCELLED")


# ===================================================================
# POST /jobs/{job_id}/retry
# ===================================================================


class TestRetryJob:
    """Tests for POST /jobs/{job_id}/retry."""

    async def test_retry_failed_job_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """FAILED job is reset to PENDING and flow is re-submitted."""
        mock_job_repo.get_by_id.return_value = make_job(status="FAILED")
        mock_job_repo.update_status.side_effect = _mock_update_status
        mock_wiki_repo.get_latest_structure.return_value = None  # -> full mode

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PENDING"
        mock_job_repo.update_status.assert_awaited_once_with(
            JOB_ID,
            "PENDING",
            error_message=None,
            prefect_flow_run_id=None,
            commit_sha=None,
        )

    async def test_retry_non_failed_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Only FAILED jobs can be retried. COMPLETED -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="COMPLETED")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "COMPLETED" in response.json()["detail"]

    async def test_retry_pending_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """PENDING is not retryable -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="PENDING")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "PENDING" in response.json()["detail"]

    async def test_retry_running_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """RUNNING is not retryable -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="RUNNING")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "RUNNING" in response.json()["detail"]

    async def test_retry_cancelled_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """CANCELLED is terminal, not retryable -> 409."""
        mock_job_repo.get_by_id.return_value = make_job(status="CANCELLED")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "CANCELLED" in response.json()["detail"]

    async def test_retry_nonexistent_job_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Unknown job_id returns 404."""
        mock_job_repo.get_by_id.return_value = None

        response = await client.post(f"/jobs/{UNKNOWN_ID}/retry")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    async def test_retry_incremental_when_structure_exists(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """FAILED job with existing structure -> incremental mode on retry."""
        mock_job_repo.get_by_id.return_value = make_job(status="FAILED")
        mock_job_repo.update_status.side_effect = _mock_update_status
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_awaited_once()

    async def test_retry_forced_skips_structure_check(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """FAILED job with force=True skips wiki structure check."""
        mock_job_repo.get_by_id.return_value = make_job(status="FAILED", force=True)
        mock_job_repo.update_status.return_value = make_job(
            status="PENDING", force=True,
        )

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_not_awaited()


# ===================================================================
# GET /jobs/{job_id}/structure
# ===================================================================


class TestGetJobStructure:
    """Tests for GET /jobs/{job_id}/structure."""

    async def test_get_structure_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Returns wiki structure for the job's repo and branch."""
        mock_job_repo.get_by_id.return_value = make_job()
        structure = make_structure_for_response()
        mock_wiki_repo.get_latest_structure.return_value = structure

        response = await client.get(f"/jobs/{JOB_ID}/structure")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(STRUCTURE_ID)
        assert data["repository_id"] == str(REPO_ID)
        assert data["branch"] == "main"
        assert data["scope_path"] == "."
        assert data["version"] == 1
        assert data["title"] == "Root Documentation"

    async def test_get_structure_job_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
    ):
        """Unknown job_id returns 404."""
        mock_job_repo.get_by_id.return_value = None

        response = await client.get(f"/jobs/{UNKNOWN_ID}/structure")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    async def test_get_structure_no_structure_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Job exists but no structure found returns 404."""
        mock_job_repo.get_by_id.return_value = make_job()
        mock_wiki_repo.get_latest_structure.return_value = None

        response = await client.get(f"/jobs/{JOB_ID}/structure")

        assert response.status_code == 404
        assert "No structure found" in response.json()["detail"]
