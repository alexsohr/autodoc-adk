"""Integration tests for webhook receiver endpoints.

Routes under test:
    POST /webhooks/push
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from tests.integration.test_api.conftest import (
    JOB_ID,
    make_job,
    make_repository,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Payload helpers
# ---------------------------------------------------------------------------


def _github_payload(
    clone_url: str = "https://github.com/acme/widgets",
    ref: str = "refs/heads/main",
    after: str = "abc123def456abc123def456abc123def456abc1",
) -> dict:
    return {
        "ref": ref,
        "after": after,
        "repository": {"clone_url": clone_url},
    }


def _bitbucket_payload(
    href: str = "https://bitbucket.org/acme/widgets",
    branch: str = "main",
    commit_hash: str = "abc123def456abc123def456abc123def456abc1",
) -> dict:
    return {
        "repository": {"links": {"html": {"href": href}}},
        "push": {
            "changes": [
                {
                    "new": {
                        "name": branch,
                        "target": {"hash": commit_hash},
                    }
                }
            ]
        },
    }


# ===================================================================
# POST /webhooks/push — GitHub
# ===================================================================


class TestGitHubWebhook:
    """Tests for POST /webhooks/push with GitHub headers."""

    async def test_github_push_creates_job_202(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """GitHub push for registered repo + configured branch -> 202."""
        mock_repository_repo.get_by_url.return_value = make_repository()
        mock_job_repo.create.return_value = make_job()
        mock_wiki_repo.get_latest_structure.return_value = None  # -> full

        with patch("src.api.routes.webhooks._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/webhooks/push",
                json=_github_payload(),
                headers={"X-GitHub-Event": "push"},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        assert data["job_id"] == str(JOB_ID)
        mock_job_repo.create.assert_awaited_once()

    async def test_github_push_full_mode_when_no_structure(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """When no existing wiki structure, mode is full."""
        mock_repository_repo.get_by_url.return_value = make_repository()
        mock_job_repo.create.return_value = make_job(mode="full")
        mock_wiki_repo.get_latest_structure.return_value = None

        with patch("src.api.routes.webhooks._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/webhooks/push",
                json=_github_payload(),
                headers={"X-GitHub-Event": "push"},
            )

        assert response.status_code == 202
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["mode"] == "full"

    async def test_github_push_incremental_mode_when_structure_exists(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """When wiki structure exists, mode is incremental."""
        mock_repository_repo.get_by_url.return_value = make_repository()
        mock_job_repo.create.return_value = make_job(mode="incremental")
        mock_wiki_repo.get_latest_structure.return_value = SimpleNamespace(
            id=uuid.uuid4()
        )

        with patch("src.api.routes.webhooks._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/webhooks/push",
                json=_github_payload(),
                headers={"X-GitHub-Event": "push"},
            )

        assert response.status_code == 202
        call_kwargs = mock_job_repo.create.call_args.kwargs
        assert call_kwargs["mode"] == "incremental"

    async def test_github_non_push_event_returns_204(
        self,
        client: httpx.AsyncClient,
    ):
        """Non-push GitHub events (e.g., pull_request) are skipped."""
        response = await client.post(
            "/webhooks/push",
            json={"action": "opened"},
            headers={"X-GitHub-Event": "pull_request"},
        )

        assert response.status_code == 204

    async def test_github_invalid_payload_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        """Invalid GitHub payload (missing required fields) returns 400."""
        response = await client.post(
            "/webhooks/push",
            json={"ref": "refs/heads/main"},  # missing repository and after
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 400

    async def test_github_tag_push_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        """GitHub push with tag ref returns 400."""
        response = await client.post(
            "/webhooks/push",
            json=_github_payload(ref="refs/tags/v1.0.0"),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 400
        assert "refs/heads" in response.json()["detail"]


# ===================================================================
# POST /webhooks/push — Bitbucket
# ===================================================================


class TestBitbucketWebhook:
    """Tests for POST /webhooks/push with Bitbucket headers."""

    async def test_bitbucket_push_creates_job_202(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Bitbucket push for registered repo + configured branch -> 202."""
        mock_repository_repo.get_by_url.return_value = make_repository(
            url="https://bitbucket.org/acme/widgets",
            provider="bitbucket",
        )
        mock_job_repo.create.return_value = make_job()
        mock_wiki_repo.get_latest_structure.return_value = None

        with patch("src.api.routes.webhooks._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/webhooks/push",
                json=_bitbucket_payload(),
                headers={"X-Event-Key": "repo:push"},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        mock_job_repo.create.assert_awaited_once()

    async def test_bitbucket_non_push_event_returns_204(
        self,
        client: httpx.AsyncClient,
    ):
        """Non-push Bitbucket events are skipped."""
        response = await client.post(
            "/webhooks/push",
            json={"some": "payload"},
            headers={"X-Event-Key": "repo:commit_status_created"},
        )

        assert response.status_code == 204


# ===================================================================
# POST /webhooks/push — Skip conditions
# ===================================================================


class TestWebhookSkipConditions:
    """Tests for webhook skip paths (204 responses)."""

    async def test_unregistered_repo_returns_204(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Repo URL not registered -> 204 skip, no job created."""
        mock_repository_repo.get_by_url.return_value = None

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 204
        mock_job_repo.create.assert_not_awaited()

    async def test_branch_not_in_mappings_returns_204(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Push to branch not in branch_mappings -> 204 skip."""
        mock_repository_repo.get_by_url.return_value = make_repository(
            branch_mappings={"main": "main"},  # no "feature/xxx"
        )

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(ref="refs/heads/feature/not-mapped"),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 204
        mock_job_repo.create.assert_not_awaited()


# ===================================================================
# POST /webhooks/push — Idempotency
# ===================================================================


class TestWebhookIdempotency:
    """Tests for webhook idempotency (duplicate push handling)."""

    async def test_existing_active_job_returns_202_with_existing_id(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Rapid successive pushes return existing active job, no new job created."""
        mock_repository_repo.get_by_url.return_value = make_repository()
        existing_job = make_job(status="RUNNING")
        mock_job_repo.get_active_for_repo.return_value = existing_job

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == str(JOB_ID)
        # No new job should have been created
        mock_job_repo.create.assert_not_awaited()

    async def test_idempotency_with_pending_job(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Existing PENDING job is returned instead of creating a new one."""
        mock_repository_repo.get_by_url.return_value = make_repository()
        pending_job = make_job(status="PENDING")
        mock_job_repo.get_active_for_repo.return_value = pending_job

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 202
        assert response.json()["job_id"] == str(JOB_ID)
        mock_job_repo.create.assert_not_awaited()


# ===================================================================
# POST /webhooks/push — Unknown provider
# ===================================================================


class TestWebhookUnknownProvider:
    """Tests for webhooks from unknown providers."""

    async def test_no_provider_headers_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        """No X-GitHub-Event or X-Event-Key header -> 400."""
        response = await client.post(
            "/webhooks/push",
            json={"some": "payload"},
        )

        assert response.status_code == 400
        assert "detect Git provider" in response.json()["detail"]
