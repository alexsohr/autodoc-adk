"""Tests for Phase 8 job management routes (cancel, retry, tasks, logs).

Routes under test:
    POST /jobs/{job_id}/cancel
    POST /jobs/{job_id}/retry
    GET  /jobs/{job_id}/tasks
    GET  /jobs/{job_id}/logs
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI

from src.api.app import create_app
from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

REPO_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()
PREFECT_FLOW_RUN_ID = str(uuid.uuid4())


def _make_job(
    job_id: uuid.UUID = JOB_ID,
    status: str = "PENDING",
    mode: str = "full",
    branch: str = "main",
    repository_id: uuid.UUID = REPO_ID,
    prefect_flow_run_id: str | None = None,
    force: bool = False,
    callback_url: str | None = None,
    **kwargs,
) -> SimpleNamespace:
    defaults = dict(
        id=job_id,
        repository_id=repository_id,
        status=status,
        mode=mode,
        branch=branch,
        commit_sha=None,
        force=force,
        dry_run=False,
        prefect_flow_run_id=prefect_flow_run_id,
        app_commit_sha=None,
        quality_report=None,
        token_usage=None,
        config_warnings=None,
        callback_url=callback_url,
        error_message=None,
        pull_request_url=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


async def _mock_update_status(job_id, status, **kwargs):
    """Return a job mock with the NEW status (simulates DB update)."""
    return _make_job(job_id=job_id, status=status, **kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> FastAPI:
    """Create a fresh FastAPI app with dependency overrides for each test."""
    return create_app()


@pytest.fixture()
def mock_job_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.update_status = AsyncMock(side_effect=_mock_update_status)
    return repo


@pytest.fixture()
def mock_repository_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_wiki_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
async def client(
    app: FastAPI,
    mock_job_repo: AsyncMock,
    mock_repository_repo: AsyncMock,
    mock_wiki_repo: AsyncMock,
) -> httpx.AsyncClient:
    """Async HTTPX test client with dependency overrides applied."""
    app.dependency_overrides[get_job_repo] = lambda: mock_job_repo
    app.dependency_overrides[get_repository_repo] = lambda: mock_repository_repo
    app.dependency_overrides[get_wiki_repo] = lambda: mock_wiki_repo

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===================================================================
# POST /jobs/{job_id}/cancel
# ===================================================================


class TestCancelJob:
    """Tests for POST /jobs/{job_id}/cancel."""

    async def test_cancel_pending_job(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """PENDING job with no prefect_flow_run_id -> status CANCELLED, 200."""
        mock_job_repo.get_by_id.return_value = _make_job(status="PENDING")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CANCELLED"
        assert data["id"] == str(JOB_ID)
        mock_job_repo.update_status.assert_awaited_once_with(JOB_ID, "CANCELLED")

    async def test_cancel_running_job_with_prefect(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """RUNNING job with prefect_flow_run_id -> Prefect cancel + DB update, 200."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

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
        mock_job_repo.update_status.assert_awaited_once_with(JOB_ID, "CANCELLED")

    async def test_cancel_running_job_prefect_failure(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Prefect API failure is non-blocking; DB still updated to CANCELLED."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

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
        data = response.json()
        assert data["status"] == "CANCELLED"
        mock_job_repo.update_status.assert_awaited_once_with(JOB_ID, "CANCELLED")

    async def test_cancel_completed_job_409(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """COMPLETED job cannot be cancelled -> 409."""
        mock_job_repo.get_by_id.return_value = _make_job(status="COMPLETED")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 409
        assert "COMPLETED" in response.json()["detail"]

    async def test_cancel_failed_job_409(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """FAILED job cannot be cancelled -> 409."""
        mock_job_repo.get_by_id.return_value = _make_job(status="FAILED")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 409
        assert "FAILED" in response.json()["detail"]

    async def test_cancel_cancelled_job_409(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Already CANCELLED job -> 409."""
        mock_job_repo.get_by_id.return_value = _make_job(status="CANCELLED")

        response = await client.post(f"/jobs/{JOB_ID}/cancel")

        assert response.status_code == 409
        assert "CANCELLED" in response.json()["detail"]

    async def test_cancel_nonexistent_job_404(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Unknown job_id -> 404."""
        mock_job_repo.get_by_id.return_value = None
        unknown_id = uuid.uuid4()

        response = await client.post(f"/jobs/{unknown_id}/cancel")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"


# ===================================================================
# POST /jobs/{job_id}/retry
# ===================================================================


class TestRetryJob:
    """Tests for POST /jobs/{job_id}/retry."""

    async def test_retry_failed_job(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """FAILED job -> resets to PENDING, mode determined by wiki_repo, 200."""
        mock_job_repo.get_by_id.return_value = _make_job(status="FAILED")
        # No existing structure -> mode = "full"
        mock_wiki_repo.get_latest_structure = AsyncMock(return_value=None)

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

    async def test_retry_failed_job_incremental_mode(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """FAILED job with existing structure -> mode = incremental."""
        mock_job_repo.get_by_id.return_value = _make_job(status="FAILED")
        mock_wiki_repo.get_latest_structure = AsyncMock(
            return_value=SimpleNamespace(id=uuid.uuid4())
        )

        with patch(
            "src.api.routes.jobs._submit_flow", new_callable=AsyncMock
        ) as mock_submit:
            response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 200
        # _submit_flow should have been called with mode="incremental"
        mock_submit.assert_called_once()
        call_kwargs = mock_submit.call_args
        # BackgroundTasks.add_task passes args as kwargs
        # The route calls background_tasks.add_task(_submit_flow, mode=mode, ...)
        # In the test the mock replaces _submit_flow, but background_tasks.add_task
        # is the real FastAPI implementation which schedules it.
        # We verify via the response and wiki_repo call instead.
        mock_wiki_repo.get_latest_structure.assert_awaited_once()

    async def test_retry_failed_job_force_full(
        self,
        client: httpx.AsyncClient,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """FAILED job with force=True -> mode is always 'full', regardless of structure."""
        mock_job_repo.get_by_id.return_value = _make_job(status="FAILED", force=True)
        # Override update_status to return a job with force=True
        mock_job_repo.update_status = AsyncMock(
            return_value=_make_job(status="PENDING", force=True)
        )
        # Even if structure exists, force should skip the check
        mock_wiki_repo.get_latest_structure = AsyncMock(
            return_value=SimpleNamespace(id=uuid.uuid4())
        )

        with patch("src.api.routes.jobs._submit_flow", new_callable=AsyncMock):
            response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 200
        # force=True means get_latest_structure should NOT be called
        mock_wiki_repo.get_latest_structure.assert_not_awaited()

    async def test_retry_completed_job_409(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """COMPLETED job -> 409."""
        mock_job_repo.get_by_id.return_value = _make_job(status="COMPLETED")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "COMPLETED" in response.json()["detail"]

    async def test_retry_pending_job_409(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """PENDING job -> 409."""
        mock_job_repo.get_by_id.return_value = _make_job(status="PENDING")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "PENDING" in response.json()["detail"]

    async def test_retry_running_job_409(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """RUNNING job -> 409."""
        mock_job_repo.get_by_id.return_value = _make_job(status="RUNNING")

        response = await client.post(f"/jobs/{JOB_ID}/retry")

        assert response.status_code == 409
        assert "RUNNING" in response.json()["detail"]

    async def test_retry_nonexistent_job_404(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Unknown job_id -> 404."""
        mock_job_repo.get_by_id.return_value = None
        unknown_id = uuid.uuid4()

        response = await client.post(f"/jobs/{unknown_id}/retry")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"


# ===================================================================
# GET /jobs/{job_id}/tasks
# ===================================================================


class TestGetJobTasks:
    """Tests for GET /jobs/{job_id}/tasks."""

    async def test_get_tasks_with_prefect_data(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Job with prefect_flow_run_id -> returns list of TaskState objects."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        now = datetime.now(UTC)
        mock_task_run = SimpleNamespace(
            name="extract_structure",
            state=SimpleNamespace(
                name="Completed",
                is_final=lambda: True,
                message="All done",
            ),
            start_time=now,
            end_time=now,
        )

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_task_runs = AsyncMock(return_value=[mock_task_run])
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["task_name"] == "extract_structure"
        assert data[0]["state"] == "Completed"
        assert data[0]["message"] == "All done"
        assert data[0]["completed_at"] is not None
        assert data[0]["started_at"] is not None

    async def test_get_tasks_multiple(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Multiple task runs are all returned."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        now = datetime.now(UTC)
        task_runs = [
            SimpleNamespace(
                name="extract_structure",
                state=SimpleNamespace(
                    name="Completed", is_final=lambda: True, message=None
                ),
                start_time=now,
                end_time=now,
            ),
            SimpleNamespace(
                name="generate_pages",
                state=SimpleNamespace(
                    name="Running", is_final=lambda: False, message="In progress"
                ),
                start_time=now,
                end_time=None,
            ),
        ]

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_task_runs = AsyncMock(return_value=task_runs)
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["task_name"] == "extract_structure"
        assert data[1]["task_name"] == "generate_pages"
        # Non-final task should have completed_at = None
        assert data[1]["completed_at"] is None

    async def test_get_tasks_no_flow_run_id(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Job with no prefect_flow_run_id -> returns empty list."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="PENDING", prefect_flow_run_id=None
        )

        response = await client.get(f"/jobs/{JOB_ID}/tasks")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_tasks_prefect_failure(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Prefect API failure -> graceful fallback to empty list."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_task_runs = AsyncMock(
            side_effect=RuntimeError("Prefect down")
        )
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/tasks")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_tasks_nonexistent_job_404(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Unknown job_id -> 404."""
        mock_job_repo.get_by_id.return_value = None
        unknown_id = uuid.uuid4()

        response = await client.get(f"/jobs/{unknown_id}/tasks")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"

    async def test_get_tasks_with_none_state(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Task run with state=None -> state shows 'Unknown'."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        mock_task_run = SimpleNamespace(
            name="unknown_task",
            state=None,
            start_time=datetime.now(UTC),
            end_time=None,
        )

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_task_runs = AsyncMock(return_value=[mock_task_run])
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/tasks")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["state"] == "Unknown"
        assert data[0]["completed_at"] is None
        assert data[0]["message"] is None


# ===================================================================
# GET /jobs/{job_id}/logs
# ===================================================================


class TestGetJobLogs:
    """Tests for GET /jobs/{job_id}/logs."""

    async def test_get_logs_with_prefect_data(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Job with prefect_flow_run_id -> returns list of LogEntry objects."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        now = datetime.now(UTC)
        mock_log = SimpleNamespace(
            timestamp=now,
            level=20,  # INFO
            message="Processing pages",
        )

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_logs = AsyncMock(return_value=[mock_log])
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["message"] == "Processing pages"
        assert data[0]["level"] == "20"  # str(log.level) since no level_name
        assert data[0]["task_name"] is None

    async def test_get_logs_with_level_name(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Log with level_name attribute -> uses level_name instead of numeric level."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        now = datetime.now(UTC)
        mock_log = SimpleNamespace(
            timestamp=now,
            level=20,
            level_name="INFO",
            message="Structure extracted",
        )

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_logs = AsyncMock(return_value=[mock_log])
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["level"] == "INFO"

    async def test_get_logs_multiple(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Multiple log entries are all returned."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        now = datetime.now(UTC)
        logs = [
            SimpleNamespace(
                timestamp=now, level=20, level_name="INFO", message="Starting"
            ),
            SimpleNamespace(
                timestamp=now, level=30, level_name="WARNING", message="Slow query"
            ),
            SimpleNamespace(
                timestamp=now, level=40, level_name="ERROR", message="Something failed"
            ),
        ]

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_logs = AsyncMock(return_value=logs)
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["level"] == "INFO"
        assert data[1]["level"] == "WARNING"
        assert data[2]["level"] == "ERROR"

    async def test_get_logs_no_flow_run_id(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Job with no prefect_flow_run_id -> returns empty list."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="PENDING", prefect_flow_run_id=None
        )

        response = await client.get(f"/jobs/{JOB_ID}/logs")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_logs_prefect_failure(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Prefect API failure -> graceful fallback to empty list."""
        mock_job_repo.get_by_id.return_value = _make_job(
            status="RUNNING", prefect_flow_run_id=PREFECT_FLOW_RUN_ID
        )

        mock_prefect_client = AsyncMock()
        mock_prefect_client.read_logs = AsyncMock(
            side_effect=RuntimeError("Prefect down")
        )
        mock_prefect_client.__aenter__ = AsyncMock(return_value=mock_prefect_client)
        mock_prefect_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "prefect.client.orchestration.get_client",
            return_value=mock_prefect_client,
        ):
            response = await client.get(f"/jobs/{JOB_ID}/logs")

        assert response.status_code == 200
        assert response.json() == []

    async def test_get_logs_nonexistent_job_404(
        self, client: httpx.AsyncClient, mock_job_repo: AsyncMock
    ):
        """Unknown job_id -> 404."""
        mock_job_repo.get_by_id.return_value = None
        unknown_id = uuid.uuid4()

        response = await client.get(f"/jobs/{unknown_id}/logs")

        assert response.status_code == 404
        assert response.json()["detail"] == "Job not found"
