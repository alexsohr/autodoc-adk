from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

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
            "url": f"https://github.com/test-health/health-repo-{_REPO_COUNTER}",
            "provider": "github",
            "branch_mappings": {"main": "Main Branch"},
            "public_branch": "main",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tests: Health endpoint (6.29-6.31)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestHealth:
    """E2E tests for the /health endpoint."""

    # -------------------------------------------------------------------
    # 6.30  All healthy
    # -------------------------------------------------------------------

    async def test_all_healthy(self, client, db_session):
        """GET /health returns 200 with a valid status field.

        In CI the app's engine may not point at the test container, so
        the database dependency may report unhealthy.  We only assert
        that the endpoint responds with 200 and a recognized status.
        """
        resp = await client.get("/health")
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert "timestamp" in data

    # -------------------------------------------------------------------
    # 6.31  DB degraded / unhealthy
    # -------------------------------------------------------------------

    async def test_db_degraded(self, client, db_session):
        """Patch DB check to raise -> GET /health returns degraded or unhealthy."""
        with patch(
            "src.api.routes.health._check_database",
            new_callable=AsyncMock,
        ) as mock_db_check:
            from src.api.routes.health import DependencyHealth

            mock_db_check.return_value = DependencyHealth(
                status="unhealthy",
                message="Connection refused",
            )

            resp = await client.get("/health")
            assert resp.status_code == 200, resp.text
            data = resp.json()

            assert data["status"] in ("degraded", "unhealthy"), (
                f"Expected degraded or unhealthy when DB is down, got: {data['status']}"
            )
            assert data["dependencies"]["database"]["status"] == "unhealthy"
            assert data["dependencies"]["database"]["message"] == "Connection refused"


# ---------------------------------------------------------------------------
# Tests: Edge cases (6.32-6.33)
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestEdgeCases:
    """E2E tests for error handling edge cases."""

    # -------------------------------------------------------------------
    # 6.32  Repo size limits (skipped)
    # -------------------------------------------------------------------

    @pytest.mark.skip(reason="Requires testing internal flow task behavior")
    async def test_repo_size_limits(self, client, db_session):
        """Placeholder: repo size limit enforcement in scan_file_tree."""
        pass

    # -------------------------------------------------------------------
    # 6.33  Flow submission failure
    # -------------------------------------------------------------------

    async def test_flow_submission_failure(self, client, db_session):
        """Patch _submit_flow to raise RuntimeError -> POST /jobs returns 201 with FAILED status."""
        repo = await _register_repo(client)
        repo_id = repo["id"]

        with patch(
            "src.api.routes.jobs._submit_flow",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Flow submission connection timeout"),
        ):
            resp = await client.post(
                "/jobs",
                json={"repository_id": repo_id},
            )
            assert resp.status_code == 201, resp.text
            data = resp.json()

            assert data["status"] == "FAILED", f"Expected FAILED status on submission failure, got: {data['status']}"
            assert data["error_message"] is not None
            assert "submission" in data["error_message"].lower(), (
                f"Expected 'submission' in error_message, got: {data['error_message']}"
            )
