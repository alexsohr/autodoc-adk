"""Unit tests for reconcile_stale_jobs startup reconciliation."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.flows.tasks.reconcile import reconcile_stale_jobs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(
    *,
    job_id: uuid.UUID | None = None,
    prefect_flow_run_id: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id or uuid.uuid4(),
        status="RUNNING",
        prefect_flow_run_id=prefect_flow_run_id,
    )


def _make_flow_run(*, is_final: bool, state_name: str = "Running") -> SimpleNamespace:
    state = SimpleNamespace(name=state_name)
    state.is_final = lambda: is_final
    return SimpleNamespace(state=state)


def _setup_mocks(
    mock_get_client: MagicMock,
    mock_job_repo_cls: MagicMock,
    running_jobs: list,
) -> tuple[AsyncMock, AsyncMock]:
    """Wire up the mock JobRepo and Prefect client, returning (mock_repo, mock_client)."""
    mock_repo = AsyncMock()
    mock_job_repo_cls.return_value = mock_repo
    mock_repo.get_running_jobs = AsyncMock(return_value=running_jobs)
    mock_repo.update_status = AsyncMock()

    mock_client = AsyncMock()
    # get_client() returns an async-context-manager
    mock_get_client.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_get_client.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_repo, mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReconcileStaleJobs:
    """Tests for :func:`reconcile_stale_jobs`."""

    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_no_running_jobs(self, MockJobRepo: MagicMock) -> None:
        """When there are no RUNNING jobs, nothing should be updated."""
        mock_repo = AsyncMock()
        MockJobRepo.return_value = mock_repo
        mock_repo.get_running_jobs = AsyncMock(return_value=[])
        mock_repo.update_status = AsyncMock()

        await reconcile_stale_jobs(session=AsyncMock())

        mock_repo.get_running_jobs.assert_awaited_once()
        mock_repo.update_status.assert_not_awaited()

    @patch("prefect.client.orchestration.get_client")
    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_running_job_no_flow_run_id(
        self, MockJobRepo: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """A RUNNING job with no prefect_flow_run_id should be marked FAILED."""
        job = _make_job(prefect_flow_run_id=None)
        mock_repo, _mock_client = _setup_mocks(mock_get_client, MockJobRepo, [job])

        await reconcile_stale_jobs(session=AsyncMock())

        mock_repo.update_status.assert_awaited_once()
        call_args = mock_repo.update_status.call_args
        assert call_args[0][0] == job.id
        assert call_args[0][1] == "FAILED"
        assert "no flow run ID" in call_args[1]["error_message"]

    @patch("prefect.client.orchestration.get_client")
    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_running_job_prefect_final_state(
        self, MockJobRepo: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """A RUNNING job whose Prefect flow run is in a final state should be marked FAILED."""
        flow_run_id = str(uuid.uuid4())
        job = _make_job(prefect_flow_run_id=flow_run_id)
        mock_repo, mock_client = _setup_mocks(mock_get_client, MockJobRepo, [job])
        mock_client.read_flow_run = AsyncMock(
            return_value=_make_flow_run(is_final=True, state_name="Completed")
        )

        await reconcile_stale_jobs(session=AsyncMock())

        mock_repo.update_status.assert_awaited_once()
        call_args = mock_repo.update_status.call_args
        assert call_args[0][0] == job.id
        assert call_args[0][1] == "FAILED"
        assert "Stale job reconciled on startup" in call_args[1]["error_message"]

    @patch("prefect.client.orchestration.get_client")
    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_running_job_still_active(
        self, MockJobRepo: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """A RUNNING job whose Prefect flow run is still active should be left alone."""
        flow_run_id = str(uuid.uuid4())
        job = _make_job(prefect_flow_run_id=flow_run_id)
        mock_repo, mock_client = _setup_mocks(mock_get_client, MockJobRepo, [job])
        mock_client.read_flow_run = AsyncMock(
            return_value=_make_flow_run(is_final=False, state_name="Running")
        )

        await reconcile_stale_jobs(session=AsyncMock())

        mock_repo.update_status.assert_not_awaited()

    @patch("prefect.client.orchestration.get_client")
    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_running_job_prefect_read_fails(
        self, MockJobRepo: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """When reading the Prefect flow run fails, the job should be marked FAILED."""
        flow_run_id = str(uuid.uuid4())
        job = _make_job(prefect_flow_run_id=flow_run_id)
        mock_repo, mock_client = _setup_mocks(mock_get_client, MockJobRepo, [job])
        mock_client.read_flow_run = AsyncMock(
            side_effect=Exception("Prefect unavailable")
        )

        await reconcile_stale_jobs(session=AsyncMock())

        mock_repo.update_status.assert_awaited_once()
        call_args = mock_repo.update_status.call_args
        assert call_args[0][0] == job.id
        assert call_args[0][1] == "FAILED"
        assert "Stale job reconciled on startup" in call_args[1]["error_message"]

    @patch("prefect.client.orchestration.get_client")
    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_multiple_jobs_mixed(
        self, MockJobRepo: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """Multiple RUNNING jobs with different scenarios are handled independently."""
        job_no_id = _make_job(prefect_flow_run_id=None)
        job_active = _make_job(prefect_flow_run_id=str(uuid.uuid4()))
        job_final = _make_job(prefect_flow_run_id=str(uuid.uuid4()))

        mock_repo, mock_client = _setup_mocks(
            mock_get_client, MockJobRepo, [job_no_id, job_active, job_final]
        )

        async def _read_flow_run(flow_run_id: uuid.UUID) -> SimpleNamespace:
            if str(flow_run_id) == job_active.prefect_flow_run_id:
                return _make_flow_run(is_final=False, state_name="Running")
            if str(flow_run_id) == job_final.prefect_flow_run_id:
                return _make_flow_run(is_final=True, state_name="Failed")
            raise AssertionError(f"Unexpected flow_run_id: {flow_run_id}")

        mock_client.read_flow_run = AsyncMock(side_effect=_read_flow_run)

        await reconcile_stale_jobs(session=AsyncMock())

        # Two jobs should have been marked FAILED (no-id + final)
        assert mock_repo.update_status.await_count == 2

        # Collect the job ids that were updated
        updated_ids = {
            call.args[0] for call in mock_repo.update_status.call_args_list
        }
        assert job_no_id.id in updated_ids
        assert job_final.id in updated_ids
        assert job_active.id not in updated_ids

    @patch("prefect.client.orchestration.get_client")
    @patch("src.flows.tasks.reconcile.JobRepo")
    async def test_flow_run_state_none_treated_as_active(
        self, MockJobRepo: MagicMock, mock_get_client: MagicMock
    ) -> None:
        """A flow run with state=None should be treated as still active (skip)."""
        flow_run_id = str(uuid.uuid4())
        job = _make_job(prefect_flow_run_id=flow_run_id)
        mock_repo, mock_client = _setup_mocks(mock_get_client, MockJobRepo, [job])
        mock_client.read_flow_run = AsyncMock(
            return_value=SimpleNamespace(state=None)
        )

        await reconcile_stale_jobs(session=AsyncMock())

        mock_repo.update_status.assert_not_awaited()
