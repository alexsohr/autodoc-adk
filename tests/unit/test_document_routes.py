"""Tests for the document API routes (src/api/routes/documents.py)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI

from src.api.app import create_app
from src.api.dependencies import get_repository_repo, get_search_repo, get_wiki_repo
from src.api.schemas.documents import SearchResponse, SearchResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ID = uuid.uuid4()
UNKNOWN_REPO_ID = uuid.uuid4()
STRUCTURE_ID = uuid.uuid4()


def _make_repository(repo_id: uuid.UUID = REPO_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=repo_id,
        public_branch="main",
        provider="github",
        url="https://github.com/org/repo",
        org="org",
        name="repo",
    )


def _make_structure(
    structure_id: uuid.UUID = STRUCTURE_ID,
    scope_path: str = ".",
    version: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=structure_id,
        repository_id=REPO_ID,
        branch="main",
        scope_path=scope_path,
        version=version,
        title="Root Docs",
        description="Root documentation scope",
        sections={
            "sections": [
                {
                    "title": "Getting Started",
                    "description": "Introduction section",
                    "pages": [
                        {
                            "page_key": "getting-started/overview",
                            "title": "Overview",
                            "description": "Project overview",
                            "importance": "high",
                            "page_type": "overview",
                        },
                    ],
                    "subsections": [],
                },
                {
                    "title": "API Reference",
                    "description": "API docs",
                    "pages": [
                        {
                            "page_key": "api/endpoints",
                            "title": "Endpoints",
                            "description": "REST endpoints",
                            "importance": "medium",
                            "page_type": "api",
                        },
                    ],
                    "subsections": [
                        {
                            "title": "Auth",
                            "description": "Auth subsection",
                            "pages": [
                                {
                                    "page_key": "api/auth",
                                    "title": "Authentication",
                                    "description": None,
                                    "importance": "high",
                                    "page_type": "module",
                                },
                            ],
                            "subsections": [],
                        },
                    ],
                },
                {
                    "title": "Internals",
                    "description": "Internal docs",
                    "pages": [],
                    "subsections": [],
                },
            ]
        },
        commit_sha="abc123" * 6 + "abcd",
    )


def _make_page(page_key: str = "getting-started/overview") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        wiki_structure_id=STRUCTURE_ID,
        page_key=page_key,
        title="Overview",
        description="Project overview",
        importance="high",
        page_type="overview",
        content="# Overview\n\nThis is the project overview.",
        source_files=["src/main.py", "src/utils.py"],
        related_pages=["api/endpoints"],
        quality_score=8.5,
    )


@pytest.fixture()
def app() -> FastAPI:
    """Create a fresh FastAPI app with dependency overrides for each test."""
    return create_app()


@pytest.fixture()
def mock_repo_repo() -> AsyncMock:
    repo_repo = AsyncMock()
    repo_repo.get_by_id = AsyncMock(side_effect=_repo_get_by_id)
    return repo_repo


async def _repo_get_by_id(repository_id: uuid.UUID):
    if repository_id == REPO_ID:
        return _make_repository()
    return None


@pytest.fixture()
def mock_wiki_repo() -> AsyncMock:
    wiki_repo = AsyncMock()
    wiki_repo.get_structures_for_repo = AsyncMock(return_value=[_make_structure()])
    wiki_repo.count_pages_for_structure = AsyncMock(return_value=3)
    wiki_repo.get_latest_structure = AsyncMock(return_value=_make_structure())
    wiki_repo.get_page_by_key = AsyncMock(return_value=_make_page())
    return wiki_repo


@pytest.fixture()
def mock_search_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
async def client(
    app: FastAPI,
    mock_repo_repo: AsyncMock,
    mock_wiki_repo: AsyncMock,
    mock_search_repo: AsyncMock,
) -> httpx.AsyncClient:
    """Return an async HTTPX test client with dependency overrides applied."""
    app.dependency_overrides[get_repository_repo] = lambda: mock_repo_repo
    app.dependency_overrides[get_wiki_repo] = lambda: mock_wiki_repo
    app.dependency_overrides[get_search_repo] = lambda: mock_search_repo

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===================================================================
# GET /documents/{repo_id}/scopes
# ===================================================================


class TestListScopes:
    """Tests for GET /documents/{repo_id}/scopes."""

    async def test_returns_scopes_for_valid_repo(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        response = await client.get(f"/documents/{REPO_ID}/scopes")

        assert response.status_code == 200
        data = response.json()
        assert "scopes" in data
        assert len(data["scopes"]) == 1
        scope = data["scopes"][0]
        assert scope["scope_path"] == "."
        assert scope["title"] == "Root Docs"
        assert scope["description"] == "Root documentation scope"
        assert scope["page_count"] == 3

    async def test_returns_404_for_unknown_repo(self, client: httpx.AsyncClient):
        response = await client.get(f"/documents/{UNKNOWN_REPO_ID}/scopes")

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_multiple_scopes_latest_version_per_scope(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        """When multiple versions exist per scope, only latest is returned."""
        struct_v1 = _make_structure(scope_path=".", version=1)
        struct_v2 = _make_structure(scope_path=".", version=2)
        struct_v2.title = "Root Docs v2"
        sub_struct = _make_structure(
            structure_id=uuid.uuid4(), scope_path="packages/core", version=1
        )
        sub_struct.title = "Core Package"
        sub_struct.description = "Core package docs"

        # get_structures_for_repo returns ordered by (scope_path ASC, version ASC)
        mock_wiki_repo.get_structures_for_repo = AsyncMock(
            return_value=[struct_v1, struct_v2, sub_struct]
        )
        mock_wiki_repo.count_pages_for_structure = AsyncMock(return_value=5)

        response = await client.get(f"/documents/{REPO_ID}/scopes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["scopes"]) == 2
        scope_paths = [s["scope_path"] for s in data["scopes"]]
        assert "." in scope_paths
        assert "packages/core" in scope_paths
        # The latest version for "." should be v2
        root_scope = next(s for s in data["scopes"] if s["scope_path"] == ".")
        assert root_scope["title"] == "Root Docs v2"

    async def test_passes_branch_param(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        response = await client.get(
            f"/documents/{REPO_ID}/scopes", params={"branch": "develop"}
        )

        assert response.status_code == 200
        mock_wiki_repo.get_structures_for_repo.assert_called_once_with(
            repository_id=REPO_ID, branch="develop"
        )


# ===================================================================
# GET /documents/{repo_id}/search
# ===================================================================


class TestSearchWiki:
    """Tests for GET /documents/{repo_id}/search."""

    async def test_returns_search_results_text(self, client: httpx.AsyncClient):
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

            mock_search.assert_called_once()
            call_kwargs = mock_search.call_args.kwargs
            assert call_kwargs["query"] == "endpoints"
            assert call_kwargs["search_type"] == "text"
            assert call_kwargs["repository_id"] == REPO_ID
            assert call_kwargs["branch"] == "main"

    async def test_returns_search_results_hybrid_default(
        self, client: httpx.AsyncClient
    ):
        mock_response = SearchResponse(
            results=[
                SearchResult(
                    page_key="getting-started/overview",
                    title="Overview",
                    snippet="Project overview...",
                    score=0.92,
                    best_chunk_content="A relevant chunk",
                    best_chunk_heading_path=["Getting Started", "Overview"],
                    scope_path=".",
                ),
            ],
            total=1,
            search_type="hybrid",
        )

        with patch(
            "src.api.routes.documents.search_documents",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_search:
            # No search_type specified -> defaults to "hybrid"
            response = await client.get(
                f"/documents/{REPO_ID}/search",
                params={"query": "overview"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["search_type"] == "hybrid"
            assert data["results"][0]["best_chunk_content"] == "A relevant chunk"

            call_kwargs = mock_search.call_args.kwargs
            assert call_kwargs["search_type"] == "hybrid"

    async def test_returns_404_for_unknown_repo(self, client: httpx.AsyncClient):
        response = await client.get(
            f"/documents/{UNKNOWN_REPO_ID}/search",
            params={"query": "test"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_passes_scope_and_limit(self, client: httpx.AsyncClient):
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


# ===================================================================
# GET /documents/{repo_id}/pages/{page_key}
# ===================================================================


class TestGetPage:
    """Tests for GET /documents/{repo_id}/pages/{page_key}."""

    async def test_returns_page_for_valid_key(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
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

    async def test_returns_404_for_unknown_repo(self, client: httpx.AsyncClient):
        response = await client.get(
            f"/documents/{UNKNOWN_REPO_ID}/pages/getting-started/overview"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_returns_404_for_unknown_page_key(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        mock_wiki_repo.get_page_by_key = AsyncMock(return_value=None)

        response = await client.get(
            f"/documents/{REPO_ID}/pages/nonexistent/page"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Page not found"

    async def test_returns_404_when_no_wiki_structure(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        mock_wiki_repo.get_latest_structure = AsyncMock(return_value=None)

        response = await client.get(
            f"/documents/{REPO_ID}/pages/getting-started/overview"
        )

        assert response.status_code == 404
        assert "No wiki found" in response.json()["detail"]

    async def test_passes_branch_and_scope_params(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        response = await client.get(
            f"/documents/{REPO_ID}/pages/getting-started/overview",
            params={"branch": "develop", "scope": "packages/core"},
        )

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_called_once_with(
            repository_id=REPO_ID,
            branch="develop",
            scope_path="packages/core",
        )


# ===================================================================
# GET /documents/{repo_id}
# ===================================================================


class TestGetWiki:
    """Tests for GET /documents/{repo_id}."""

    async def test_returns_paginated_wiki_sections(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        response = await client.get(f"/documents/{REPO_ID}")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "next_cursor" in data
        assert "limit" in data
        assert data["limit"] == 20
        # The fixture structure has 3 top-level sections, fits in one page
        assert len(data["items"]) == 3
        assert data["next_cursor"] is None

        # Verify section structure
        first_section = data["items"][0]
        assert first_section["title"] == "Getting Started"
        assert len(first_section["pages"]) == 1
        assert first_section["pages"][0]["page_key"] == "getting-started/overview"

        # Verify nested subsections
        second_section = data["items"][1]
        assert second_section["title"] == "API Reference"
        assert len(second_section["subsections"]) == 1
        assert second_section["subsections"][0]["title"] == "Auth"

    async def test_returns_404_for_unknown_repo(self, client: httpx.AsyncClient):
        response = await client.get(f"/documents/{UNKNOWN_REPO_ID}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Repository not found"

    async def test_pagination_with_cursor(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        """Verify cursor-based pagination over top-level sections."""
        # Request with limit=1 to get just the first section
        response = await client.get(
            f"/documents/{REPO_ID}", params={"limit": 1}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Getting Started"
        assert data["next_cursor"] == "1"
        assert data["limit"] == 1

        # Follow cursor to get the second section
        response2 = await client.get(
            f"/documents/{REPO_ID}",
            params={"limit": 1, "cursor": data["next_cursor"]},
        )

        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["items"]) == 1
        assert data2["items"][0]["title"] == "API Reference"
        assert data2["next_cursor"] == "2"

        # Follow cursor to get the third (last) section
        response3 = await client.get(
            f"/documents/{REPO_ID}",
            params={"limit": 1, "cursor": data2["next_cursor"]},
        )

        assert response3.status_code == 200
        data3 = response3.json()
        assert len(data3["items"]) == 1
        assert data3["items"][0]["title"] == "Internals"
        assert data3["next_cursor"] is None  # No more sections

    async def test_returns_404_when_no_wiki_structure(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        mock_wiki_repo.get_latest_structure = AsyncMock(return_value=None)

        response = await client.get(f"/documents/{REPO_ID}")

        assert response.status_code == 404
        assert "No wiki found" in response.json()["detail"]

    async def test_passes_branch_and_scope_params(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        response = await client.get(
            f"/documents/{REPO_ID}",
            params={"branch": "develop", "scope": "packages/core"},
        )

        assert response.status_code == 200
        mock_wiki_repo.get_latest_structure.assert_called_once_with(
            repository_id=REPO_ID,
            branch="develop",
            scope_path="packages/core",
        )

    async def test_invalid_cursor_returns_400(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        response = await client.get(
            f"/documents/{REPO_ID}", params={"cursor": "not-a-number"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid cursor value"

    async def test_empty_sections(
        self, client: httpx.AsyncClient, mock_wiki_repo: AsyncMock
    ):
        """Structure with no sections returns empty items list."""
        empty_structure = _make_structure()
        empty_structure.sections = {"sections": []}
        mock_wiki_repo.get_latest_structure = AsyncMock(return_value=empty_structure)

        response = await client.get(f"/documents/{REPO_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["next_cursor"] is None
