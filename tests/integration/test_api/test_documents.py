"""Integration tests for document search and retrieval endpoints.

Routes under test:
    GET /documents/{repository_id}
    GET /documents/{repository_id}/pages/{page_key}
    GET /documents/{repository_id}/search
    GET /documents/{repository_id}/scopes
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.api.schemas.documents import SearchResponse, SearchResult
from tests.integration.test_api.conftest import (
    REPO_ID,
    UNKNOWN_ID,
    make_page,
    make_repository,
    make_structure,
)

pytestmark = pytest.mark.integration


# ===================================================================
# GET /documents/{repository_id}
# ===================================================================


class TestGetWiki:
    """Tests for GET /documents/{repository_id}."""

    async def test_returns_paginated_wiki_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Returns paginated wiki sections for a valid repo with wiki."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(f"/documents/{REPO_ID}")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "next_cursor" in data
        assert "limit" in data
        assert data["limit"] == 20
        # The fixture structure has 2 top-level sections
        assert len(data["items"]) == 2
        assert data["next_cursor"] is None
        assert data["items"][0]["title"] == "Getting Started"
        assert data["items"][1]["title"] == "API Reference"

    async def test_pagination_with_limit(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """limit=1 returns one section with a next_cursor."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(
            f"/documents/{REPO_ID}", params={"limit": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Getting Started"
        assert data["next_cursor"] == "1"

    async def test_pagination_follow_cursor(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Following the cursor returns the next page of sections."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(
            f"/documents/{REPO_ID}", params={"cursor": "1", "limit": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "API Reference"
        assert data["next_cursor"] is None  # No more sections

    async def test_repo_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Unknown repository returns 404."""
        mock_repository_repo.get_by_id.return_value = None

        response = await client.get(f"/documents/{UNKNOWN_ID}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_no_wiki_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Repo exists but no wiki structure returns 404."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = None

        response = await client.get(f"/documents/{REPO_ID}")

        assert response.status_code == 404
        assert "No wiki found" in response.json()["detail"]

    async def test_branch_param_forwarded(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """branch query param is forwarded to wiki_repo."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(
            f"/documents/{REPO_ID}", params={"branch": "develop"}
        )

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_awaited_once_with(
            repository_id=REPO_ID,
            branch="develop",
            scope_path=".",
        )

    async def test_scope_param_forwarded(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """scope query param is forwarded to wiki_repo."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(
            f"/documents/{REPO_ID}", params={"scope": "packages/core"}
        )

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_awaited_once_with(
            repository_id=REPO_ID,
            branch="main",
            scope_path="packages/core",
        )

    async def test_invalid_cursor_returns_400(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Non-numeric cursor returns 400."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(
            f"/documents/{REPO_ID}", params={"cursor": "not-a-number"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid cursor value"

    async def test_section_pages_structure(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Verify that pages within sections have the expected fields."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()

        response = await client.get(f"/documents/{REPO_ID}")

        data = response.json()
        page = data["items"][0]["pages"][0]
        assert page["page_key"] == "getting-started/overview"
        assert page["title"] == "Overview"
        assert page["importance"] == "high"
        assert page["page_type"] == "overview"


# ===================================================================
# GET /documents/{repository_id}/pages/{page_key}
# ===================================================================


class TestGetPage:
    """Tests for GET /documents/{repository_id}/pages/{page_key}."""

    async def test_returns_page_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Returns full page content for a valid page key."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()
        mock_wiki_repo.get_page_by_key.return_value = make_page()

        response = await client.get(
            f"/documents/{REPO_ID}/pages/getting-started/overview"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page_key"] == "getting-started/overview"
        assert data["title"] == "Overview"
        assert data["description"] == "Project overview"
        assert data["importance"] == "high"
        assert data["page_type"] == "overview"
        assert "# Overview" in data["content"]
        assert data["source_files"] == ["src/main.py", "src/utils.py"]
        assert data["related_pages"] == ["api/endpoints"]
        assert data["quality_score"] == 8.5

    async def test_repo_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Unknown repository returns 404."""
        mock_repository_repo.get_by_id.return_value = None

        response = await client.get(
            f"/documents/{UNKNOWN_ID}/pages/getting-started/overview"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_no_wiki_structure_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Repo exists but no wiki structure -> 404."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = None

        response = await client.get(
            f"/documents/{REPO_ID}/pages/getting-started/overview"
        )

        assert response.status_code == 404
        assert "No wiki found" in response.json()["detail"]

    async def test_page_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Page key doesn't exist returns 404."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()
        mock_wiki_repo.get_page_by_key.return_value = None

        response = await client.get(
            f"/documents/{REPO_ID}/pages/nonexistent/page"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Page not found"

    async def test_branch_and_scope_params_forwarded(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """branch and scope params are forwarded to get_latest_structure."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_latest_structure.return_value = make_structure()
        mock_wiki_repo.get_page_by_key.return_value = make_page()

        response = await client.get(
            f"/documents/{REPO_ID}/pages/getting-started/overview",
            params={"branch": "develop", "scope": "packages/core"},
        )

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_awaited_once_with(
            repository_id=REPO_ID,
            branch="develop",
            scope_path="packages/core",
        )

    async def test_defaults_to_public_branch(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """When no branch param, defaults to repo's public_branch."""
        mock_repository_repo.get_by_id.return_value = make_repository(
            public_branch="main",
        )
        mock_wiki_repo.get_latest_structure.return_value = make_structure()
        mock_wiki_repo.get_page_by_key.return_value = make_page()

        await client.get(f"/documents/{REPO_ID}/pages/getting-started/overview")

        call_kwargs = mock_wiki_repo.get_latest_structure.call_args.kwargs
        assert call_kwargs["branch"] == "main"


# ===================================================================
# GET /documents/{repository_id}/search
# ===================================================================


class TestSearchWiki:
    """Tests for GET /documents/{repository_id}/search."""

    async def test_text_search_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Text search returns results with correct shape."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_response = SearchResponse(
            results=[
                SearchResult(
                    page_key="api/endpoints",
                    title="Endpoints",
                    snippet="REST API endpoints for...",
                    score=0.85,
                    scope_path=".",
                ),
            ],
            total=1,
            search_type="text",
        )

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_search:
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "endpoints", "search_type": "text"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "text"
        assert data["total"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["page_key"] == "api/endpoints"
        assert data["results"][0]["score"] == 0.85

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["query"] == "endpoints"
        assert call_kwargs["search_type"] == "text"
        assert call_kwargs["repository_id"] == REPO_ID
        assert call_kwargs["branch"] == "main"

    async def test_semantic_search_returns_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Semantic search includes best_chunk_content and heading_path."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_response = SearchResponse(
            results=[
                SearchResult(
                    page_key="getting-started/overview",
                    title="Overview",
                    snippet="Project overview...",
                    score=0.92,
                    best_chunk_content="A relevant chunk about setup",
                    best_chunk_heading_path=["Getting Started", "Overview"],
                    scope_path=".",
                ),
            ],
            total=1,
            search_type="semantic",
        )

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "how to set up", "search_type": "semantic"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "semantic"
        result = data["results"][0]
        assert result["best_chunk_content"] == "A relevant chunk about setup"
        assert result["best_chunk_heading_path"] == ["Getting Started", "Overview"]

    async def test_hybrid_search_is_default(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """When no search_type specified, defaults to hybrid."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_response = SearchResponse(results=[], total=0, search_type="hybrid")

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_search:
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "overview"},
            )

        assert response.status_code == 200
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["search_type"] == "hybrid"

    async def test_repo_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Unknown repository returns 404."""
        mock_repository_repo.get_by_id.return_value = None

        response = await client.get(
            f"/documents/{UNKNOWN_ID}/search",
            params={"query": "test"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_scope_and_limit_forwarded(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """scope and limit params are forwarded to search_documents."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_response = SearchResponse(results=[], total=0, search_type="text")

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_search:
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={
                    "query": "auth",
                    "search_type": "text",
                    "scope": "packages/core",
                    "limit": 5,
                },
            )

        assert response.status_code == 200
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["scope"] == "packages/core"
        assert call_kwargs["limit"] == 5

    async def test_branch_param_forwarded(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """branch param is forwarded to search_documents."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_response = SearchResponse(results=[], total=0, search_type="text")

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_search:
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "test", "branch": "develop"},
            )

        assert response.status_code == 200
        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["branch"] == "develop"

    async def test_empty_results(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """No search results returns empty list with total=0."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_response = SearchResponse(results=[], total=0, search_type="text")

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "nonexistent", "search_type": "text"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total"] == 0


# ===================================================================
# GET /documents/{repository_id}/scopes
# ===================================================================


class TestListScopes:
    """Tests for GET /documents/{repository_id}/scopes."""

    async def test_returns_scopes_200(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Returns scope information for a valid repo."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        structure = make_structure()
        mock_wiki_repo.get_structures_for_repo.return_value = [structure]
        mock_wiki_repo.count_pages_for_structure.return_value = 5

        response = await client.get(f"/documents/{REPO_ID}/scopes")

        assert response.status_code == 200
        data = response.json()
        assert "scopes" in data
        assert len(data["scopes"]) == 1
        scope = data["scopes"][0]
        assert scope["scope_path"] == "."
        assert scope["title"] == "Root Documentation"
        assert scope["page_count"] == 5

    async def test_multiple_scopes(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """Multiple scopes are returned, one per unique scope_path."""
        mock_repository_repo.get_by_id.return_value = make_repository()

        root = make_structure(scope_path=".", version=1)
        sub = make_structure(
            structure_id=uuid.uuid4(),
            scope_path="packages/auth",
            version=1,
        )
        sub.title = "Auth Package"
        sub.description = "Authentication package docs"

        mock_wiki_repo.get_structures_for_repo.return_value = [root, sub]
        mock_wiki_repo.count_pages_for_structure.return_value = 3

        response = await client.get(f"/documents/{REPO_ID}/scopes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["scopes"]) == 2
        paths = [s["scope_path"] for s in data["scopes"]]
        assert "." in paths
        assert "packages/auth" in paths

    async def test_latest_version_used(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """When multiple versions exist, only the latest is used."""
        mock_repository_repo.get_by_id.return_value = make_repository()

        v1 = make_structure(scope_path=".", version=1)
        v2 = make_structure(scope_path=".", version=2)
        v2.title = "Updated Docs"

        # Ordered by (scope_path ASC, version ASC) per the code
        mock_wiki_repo.get_structures_for_repo.return_value = [v1, v2]
        mock_wiki_repo.count_pages_for_structure.return_value = 10

        response = await client.get(f"/documents/{REPO_ID}/scopes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["scopes"]) == 1
        assert data["scopes"][0]["title"] == "Updated Docs"

    async def test_repo_not_found_returns_404(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
    ):
        """Unknown repository returns 404."""
        mock_repository_repo.get_by_id.return_value = None

        response = await client.get(f"/documents/{UNKNOWN_ID}/scopes")

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_branch_param_forwarded(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """branch query param is forwarded to get_structures_for_repo."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_structures_for_repo.return_value = []

        response = await client.get(
            f"/documents/{REPO_ID}/scopes", params={"branch": "develop"}
        )

        assert response.status_code == 200
        mock_wiki_repo.get_structures_for_repo.assert_awaited_once_with(
            repository_id=REPO_ID,
            branch="develop",
        )

    async def test_empty_scopes(
        self,
        client: httpx.AsyncClient,
        mock_repository_repo: AsyncMock,
        mock_wiki_repo: AsyncMock,
    ):
        """No structures returns empty scopes list."""
        mock_repository_repo.get_by_id.return_value = make_repository()
        mock_wiki_repo.get_structures_for_repo.return_value = []

        response = await client.get(f"/documents/{REPO_ID}/scopes")

        assert response.status_code == 200
        data = response.json()
        assert data["scopes"] == []
