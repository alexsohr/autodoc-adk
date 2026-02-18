"""Tests for Phase 9 webhook receiver (T076, T077).

Routes under test:
    POST /webhooks/push
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from src.api.app import create_app
from src.api.dependencies import get_job_repo, get_repository_repo, get_wiki_repo
from src.api.routes.webhooks import parse_bitbucket_push, parse_github_push

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

REPO_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()


def _make_repo(
    repo_id: uuid.UUID = REPO_ID,
    url: str = "https://github.com/org/repo.git",
    provider: str = "github",
    branch_mappings: dict | None = None,
    public_branch: str = "main",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=repo_id,
        url=url,
        provider=provider,
        org="org",
        name="repo",
        branch_mappings=branch_mappings or {"main": "main", "develop": "develop"},
        public_branch=public_branch,
        access_token=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_job(
    job_id: uuid.UUID = JOB_ID,
    status: str = "PENDING",
    mode: str = "full",
    branch: str = "main",
    repository_id: uuid.UUID = REPO_ID,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        repository_id=repository_id,
        status=status,
        mode=mode,
        branch=branch,
        commit_sha=None,
        force=False,
        dry_run=False,
        prefect_flow_run_id=None,
        app_commit_sha=None,
        quality_report=None,
        token_usage=None,
        config_warnings=None,
        callback_url=None,
        error_message=None,
        pull_request_url=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _github_payload(
    clone_url: str = "https://github.com/org/repo.git",
    ref: str = "refs/heads/main",
    after: str = "abc123def456",
) -> dict:
    return {
        "ref": ref,
        "after": after,
        "repository": {"clone_url": clone_url},
    }


def _bitbucket_payload(
    href: str = "https://bitbucket.org/org/repo",
    branch: str = "main",
    commit_hash: str = "abc123def456",
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


# ---------------------------------------------------------------------------
# T077: Payload parser unit tests
# ---------------------------------------------------------------------------


class TestParseGitHubPush:
    """Unit tests for parse_github_push."""

    def test_valid_payload(self):
        url, branch, sha = parse_github_push(_github_payload())
        assert url == "https://github.com/org/repo.git"
        assert branch == "main"
        assert sha == "abc123def456"

    def test_strips_refs_heads_prefix(self):
        _, branch, _ = parse_github_push(
            _github_payload(ref="refs/heads/feature/new-thing")
        )
        assert branch == "feature/new-thing"

    def test_raises_on_missing_clone_url(self):
        payload = {"ref": "refs/heads/main", "after": "abc123", "repository": {}}
        with pytest.raises(ValueError, match="clone_url"):
            parse_github_push(payload)

    def test_raises_on_missing_repository(self):
        payload = {"ref": "refs/heads/main", "after": "abc123"}
        with pytest.raises(ValueError, match="clone_url"):
            parse_github_push(payload)

    def test_raises_on_tag_ref(self):
        payload = _github_payload(ref="refs/tags/v1.0.0")
        with pytest.raises(ValueError, match="refs/heads"):
            parse_github_push(payload)

    def test_raises_on_missing_ref(self):
        payload = {"after": "abc123", "repository": {"clone_url": "url"}}
        with pytest.raises(ValueError, match="ref"):
            parse_github_push(payload)

    def test_raises_on_missing_after(self):
        payload = {
            "ref": "refs/heads/main",
            "repository": {"clone_url": "url"},
        }
        with pytest.raises(ValueError, match="after"):
            parse_github_push(payload)


class TestParseBitbucketPush:
    """Unit tests for parse_bitbucket_push."""

    def test_valid_payload(self):
        url, branch, sha = parse_bitbucket_push(_bitbucket_payload())
        assert url == "https://bitbucket.org/org/repo"
        assert branch == "main"
        assert sha == "abc123def456"

    def test_raises_on_missing_href(self):
        payload = {"repository": {"links": {}}, "push": {"changes": []}}
        with pytest.raises(ValueError, match="href"):
            parse_bitbucket_push(payload)

    def test_raises_on_missing_repository(self):
        payload = {"push": {"changes": []}}
        with pytest.raises(ValueError, match="href"):
            parse_bitbucket_push(payload)

    def test_raises_on_empty_changes(self):
        payload = {
            "repository": {"links": {"html": {"href": "url"}}},
            "push": {"changes": []},
        }
        with pytest.raises(ValueError, match="changes"):
            parse_bitbucket_push(payload)

    def test_raises_on_missing_push(self):
        payload = {"repository": {"links": {"html": {"href": "url"}}}}
        with pytest.raises(ValueError, match="changes"):
            parse_bitbucket_push(payload)


# ---------------------------------------------------------------------------
# T076: Webhook route integration tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def app() -> FastAPI:
    return create_app()


@pytest.fixture()
def mock_job_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_active_for_repo = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=_make_job())
    return repo


@pytest.fixture()
def mock_repository_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def mock_wiki_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_latest_structure = AsyncMock(return_value=None)
    return repo


@pytest.fixture()
async def client(
    app: FastAPI,
    mock_job_repo: AsyncMock,
    mock_repository_repo: AsyncMock,
    mock_wiki_repo: AsyncMock,
) -> httpx.AsyncClient:
    app.dependency_overrides[get_job_repo] = lambda: mock_job_repo
    app.dependency_overrides[get_repository_repo] = lambda: mock_repository_repo
    app.dependency_overrides[get_wiki_repo] = lambda: mock_wiki_repo

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestWebhookRoute:
    """Tests for POST /webhooks/push."""

    async def test_github_push_registered_repo_creates_job(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """GitHub push for registered repo + configured branch -> 202 with job_id."""
        mock_repository_repo.get_by_url.return_value = _make_repo()

        with patch("src.api.routes.webhooks._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/webhooks/push",
                json=_github_payload(),
                headers={"X-GitHub-Event": "push"},
            )

        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        mock_job_repo.create.assert_awaited_once()

    async def test_bitbucket_push_registered_repo_creates_job(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Bitbucket push for registered repo + configured branch -> 202 with job_id."""
        mock_repository_repo.get_by_url.return_value = _make_repo(
            url="https://bitbucket.org/org/repo",
            provider="bitbucket",
        )

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

    async def test_unregistered_repo_returns_204(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Push for unregistered repo -> 204 skip."""
        mock_repository_repo.get_by_url.return_value = None

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 204
        mock_job_repo.create.assert_not_awaited()

    async def test_non_configured_branch_returns_204(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Push for branch not in branch_mappings -> 204 skip."""
        mock_repository_repo.get_by_url.return_value = _make_repo()

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(ref="refs/heads/feature/not-configured"),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 204
        mock_job_repo.create.assert_not_awaited()

    async def test_idempotency_returns_existing_job(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """Rapid successive pushes return existing active job -> 202."""
        mock_repository_repo.get_by_url.return_value = _make_repo()
        existing_job = _make_job(status="RUNNING")
        mock_job_repo.get_active_for_repo.return_value = existing_job

        response = await client.post(
            "/webhooks/push",
            json=_github_payload(),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["job_id"] == str(existing_job.id)
        mock_job_repo.create.assert_not_awaited()

    async def test_invalid_payload_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        """Invalid GitHub payload (missing fields) -> 400."""
        response = await client.post(
            "/webhooks/push",
            json={"ref": "refs/heads/main"},  # missing repository and after
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 400

    async def test_unknown_provider_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        """No matching provider headers -> 400."""
        response = await client.post(
            "/webhooks/push",
            json={"some": "payload"},
        )

        assert response.status_code == 400
        assert "detect Git provider" in response.json()["detail"]

    async def test_non_push_github_event_returns_204(
        self,
        client: httpx.AsyncClient,
    ):
        """GitHub event that is not 'push' (e.g. 'pull_request') -> 204."""
        response = await client.post(
            "/webhooks/push",
            json={"action": "opened"},
            headers={"X-GitHub-Event": "pull_request"},
        )

        assert response.status_code == 204

    async def test_non_push_bitbucket_event_returns_204(
        self,
        client: httpx.AsyncClient,
    ):
        """Bitbucket event that is not 'repo:push' -> 204."""
        response = await client.post(
            "/webhooks/push",
            json={"some": "payload"},
            headers={"X-Event-Key": "repo:commit_status_created"},
        )

        assert response.status_code == 204

    async def test_incremental_mode_when_structure_exists(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """When wiki structure exists, mode should be incremental."""
        mock_repository_repo.get_by_url.return_value = _make_repo()
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
        # Verify job was created with mode=incremental
        create_call = mock_job_repo.create.call_args
        assert create_call.kwargs["mode"] == "incremental"

    async def test_full_mode_when_no_structure(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
        mock_job_repo: AsyncMock,
    ):
        """When no wiki structure exists, mode should be full."""
        mock_repository_repo.get_by_url.return_value = _make_repo()
        mock_wiki_repo.get_latest_structure.return_value = None

        with patch("src.api.routes.webhooks._submit_flow", new_callable=AsyncMock):
            response = await client.post(
                "/webhooks/push",
                json=_github_payload(),
                headers={"X-GitHub-Event": "push"},
            )

        assert response.status_code == 202
        create_call = mock_job_repo.create.call_args
        assert create_call.kwargs["mode"] == "full"

    async def test_github_tag_push_returns_400(
        self,
        client: httpx.AsyncClient,
    ):
        """GitHub push with a tag ref -> 400 (not a branch push)."""
        response = await client.post(
            "/webhooks/push",
            json=_github_payload(ref="refs/tags/v1.0.0"),
            headers={"X-GitHub-Event": "push"},
        )

        assert response.status_code == 400
        assert "refs/heads" in response.json()["detail"]
