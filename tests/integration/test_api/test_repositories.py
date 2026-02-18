"""Integration tests for repository CRUD endpoints.

Routes under test:
    POST   /repositories
    GET    /repositories
    GET    /repositories/{repository_id}
    PATCH  /repositories/{repository_id}
    DELETE /repositories/{repository_id}
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

from tests.integration.test_api.conftest import (
    REPO_ID,
    REPO_ID_2,
    UNKNOWN_ID,
    make_repository,
)

pytestmark = pytest.mark.integration


# ===================================================================
# POST /repositories
# ===================================================================


class TestRegisterRepository:
    """Tests for POST /repositories."""

    async def test_register_valid_github_repo_returns_201(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Successful registration returns 201 with the full RepositoryResponse."""
        repo = make_repository()
        mock_repository_repo.create.return_value = repo

        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(REPO_ID)
        assert data["url"] == "https://github.com/acme/widgets"
        assert data["provider"] == "github"
        assert data["org"] == "acme"
        assert data["name"] == "widgets"
        assert data["branch_mappings"] == {"main": "main", "develop": "develop"}
        assert data["public_branch"] == "main"
        assert "created_at" in data
        assert "updated_at" in data

    async def test_register_valid_bitbucket_repo_returns_201(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Bitbucket repos are also accepted."""
        repo = make_repository(
            url="https://bitbucket.org/acme/widgets",
            provider="bitbucket",
        )
        mock_repository_repo.create.return_value = repo

        response = await client.post(
            "/repositories",
            json={
                "url": "https://bitbucket.org/acme/widgets",
                "provider": "bitbucket",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "bitbucket"

    async def test_register_duplicate_url_returns_409(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Duplicate URL raises IntegrityError which maps to 409."""
        mock_repository_repo.create.side_effect = IntegrityError(
            "duplicate key", params=None, orig=Exception()
        )

        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    async def test_register_public_branch_not_in_mappings_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """public_branch must be a key in branch_mappings (Pydantic validation)."""
        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "develop",  # not in branch_mappings
            },
        )

        assert response.status_code == 422

    async def test_register_empty_branch_mappings_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """branch_mappings must have at least one entry."""
        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {},
                "public_branch": "main",
            },
        )

        assert response.status_code == 422

    async def test_register_missing_required_fields_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """Omitting required fields triggers validation error."""
        response = await client.post(
            "/repositories",
            json={"url": "https://github.com/acme/widgets"},
        )

        assert response.status_code == 422

    async def test_register_invalid_provider_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """Provider must be 'github' or 'bitbucket'."""
        response = await client.post(
            "/repositories",
            json={
                "url": "https://gitlab.com/acme/widgets",
                "provider": "gitlab",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )

        assert response.status_code == 422

    async def test_register_url_host_mismatch_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """GitHub provider with non-github.com URL returns 422."""
        response = await client.post(
            "/repositories",
            json={
                "url": "https://gitlab.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )

        assert response.status_code == 422
        assert "github.com" in response.json()["detail"]

    async def test_register_url_with_missing_path_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """URL without /{org}/{name} path returns 422."""
        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
            },
        )

        assert response.status_code == 422
        assert "/{org}/{name}" in response.json()["detail"]

    async def test_register_with_access_token(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Access token is passed to create but not leaked in response."""
        repo = make_repository()
        mock_repository_repo.create.return_value = repo

        response = await client.post(
            "/repositories",
            json={
                "url": "https://github.com/acme/widgets",
                "provider": "github",
                "branch_mappings": {"main": "main"},
                "public_branch": "main",
                "access_token": "ghp_secret123",
            },
        )

        assert response.status_code == 201
        # Verify access_token was passed to create
        call_kwargs = mock_repository_repo.create.call_args.kwargs
        assert call_kwargs["access_token"] == "ghp_secret123"
        # Response should not contain access_token
        assert "access_token" not in response.json()


# ===================================================================
# GET /repositories
# ===================================================================


class TestListRepositories:
    """Tests for GET /repositories."""

    async def test_list_empty(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Empty database returns empty items list."""
        mock_repository_repo.list.return_value = []

        response = await client.get("/repositories")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["next_cursor"] is None
        assert data["limit"] == 20

    async def test_list_with_items(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Returns repositories as RepositoryResponse objects."""
        repos = [make_repository(repo_id=REPO_ID), make_repository(repo_id=REPO_ID_2)]
        mock_repository_repo.list.return_value = repos

        response = await client.get("/repositories")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == str(REPO_ID)
        assert data["items"][1]["id"] == str(REPO_ID_2)

    async def test_list_with_pagination_cursor(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """When len(rows) == limit, next_cursor is set to last item's id."""
        # Simulate exactly limit=2 rows returned -> has next page
        repos = [make_repository(repo_id=REPO_ID), make_repository(repo_id=REPO_ID_2)]
        mock_repository_repo.list.return_value = repos

        response = await client.get("/repositories", params={"limit": 2})

        assert response.status_code == 200
        data = response.json()
        assert data["next_cursor"] == str(REPO_ID_2)
        assert data["limit"] == 2

    async def test_list_passes_cursor_param(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Cursor query param is forwarded to repo.list()."""
        mock_repository_repo.list.return_value = []

        await client.get(
            "/repositories",
            params={"cursor": str(REPO_ID), "limit": 10},
        )

        mock_repository_repo.list.assert_awaited_once_with(
            cursor=REPO_ID,
            limit=10,
        )

    async def test_list_no_next_cursor_when_fewer_than_limit(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """When fewer items than limit, next_cursor is None."""
        mock_repository_repo.list.return_value = [make_repository()]

        response = await client.get("/repositories", params={"limit": 20})

        data = response.json()
        assert data["next_cursor"] is None

    async def test_list_custom_limit(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Custom limit is respected."""
        mock_repository_repo.list.return_value = []

        response = await client.get("/repositories", params={"limit": 5})

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5


# ===================================================================
# GET /repositories/{repository_id}
# ===================================================================


class TestGetRepository:
    """Tests for GET /repositories/{repository_id}."""

    async def test_get_existing_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Known repository_id returns full RepositoryResponse."""
        mock_repository_repo.get_by_id.return_value = make_repository()

        response = await client.get(f"/repositories/{REPO_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(REPO_ID)
        assert data["url"] == "https://github.com/acme/widgets"
        assert data["provider"] == "github"
        assert data["org"] == "acme"
        assert data["name"] == "widgets"

    async def test_get_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Unknown repository_id returns 404."""
        mock_repository_repo.get_by_id.return_value = None

        response = await client.get(f"/repositories/{UNKNOWN_ID}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"


# ===================================================================
# PATCH /repositories/{repository_id}
# ===================================================================


class TestUpdateRepository:
    """Tests for PATCH /repositories/{repository_id}."""

    async def test_update_branch_mappings_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Updating branch_mappings returns the updated repository."""
        updated = make_repository(
            branch_mappings={"main": "main", "staging": "staging"},
        )
        mock_repository_repo.update.return_value = updated

        response = await client.patch(
            f"/repositories/{REPO_ID}",
            json={"branch_mappings": {"main": "main", "staging": "staging"}},
        )

        assert response.status_code == 200
        data = response.json()
        assert "staging" in data["branch_mappings"]

    async def test_update_public_branch_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Updating public_branch that exists in branch_mappings succeeds."""
        existing = make_repository(
            branch_mappings={"main": "main", "develop": "develop"},
        )
        mock_repository_repo.get_by_id.return_value = existing
        updated = make_repository(public_branch="develop")
        mock_repository_repo.update.return_value = updated

        response = await client.patch(
            f"/repositories/{REPO_ID}",
            json={"public_branch": "develop"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["public_branch"] == "develop"

    async def test_update_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Updating nonexistent repository returns 404."""
        mock_repository_repo.update.return_value = None

        response = await client.patch(
            f"/repositories/{UNKNOWN_ID}",
            json={"branch_mappings": {"main": "main"}},
        )

        assert response.status_code == 404

    async def test_update_no_fields_returns_422(
        self,
        client: httpx.AsyncClient,
    ):
        """Empty update body returns 422."""
        response = await client.patch(
            f"/repositories/{REPO_ID}",
            json={},
        )

        assert response.status_code == 422
        assert "No fields to update" in response.json()["detail"]

    async def test_update_public_branch_not_in_mappings_returns_422(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Setting public_branch to a branch not in mappings returns 422."""
        existing = make_repository(branch_mappings={"main": "main"})
        mock_repository_repo.get_by_id.return_value = existing

        response = await client.patch(
            f"/repositories/{REPO_ID}",
            json={"public_branch": "nonexistent"},
        )

        assert response.status_code == 422
        assert "must be a key in branch_mappings" in response.json()["detail"]

    async def test_update_public_branch_with_new_mappings(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """When both branch_mappings and public_branch are updated,
        validates against the new mappings."""
        updated = make_repository(
            branch_mappings={"staging": "staging"},
            public_branch="staging",
        )
        mock_repository_repo.update.return_value = updated

        response = await client.patch(
            f"/repositories/{REPO_ID}",
            json={
                "branch_mappings": {"staging": "staging"},
                "public_branch": "staging",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["public_branch"] == "staging"


# ===================================================================
# DELETE /repositories/{repository_id}
# ===================================================================


class TestDeleteRepository:
    """Tests for DELETE /repositories/{repository_id}."""

    async def test_delete_existing_returns_204(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Successful deletion returns 204 with empty body."""
        mock_repository_repo.delete.return_value = True

        response = await client.delete(f"/repositories/{REPO_ID}")

        assert response.status_code == 204
        assert response.content == b""

    async def test_delete_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Deleting a nonexistent repository returns 404."""
        mock_repository_repo.delete.return_value = False

        response = await client.delete(f"/repositories/{UNKNOWN_ID}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"
