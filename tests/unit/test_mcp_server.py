"""Tests for the MCP server (Phase 10 checkpoint).

Validates that external AI agents can discover repositories and query
their documentation via the ``find_repository`` and ``query_documents``
MCP tools.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.schemas.documents import SearchResponse, SearchResult
from src.errors import PermanentError
from src.mcp_server import find_repository, mcp, query_documents

# ---------------------------------------------------------------------------
# Raw functions (unwrapped from FunctionTool)
# ---------------------------------------------------------------------------

_find_repository_fn = find_repository.fn
_query_documents_fn = query_documents.fn

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REPO_ID = uuid.uuid4()
REPO_URL = "https://github.com/acme/widgets"


def _make_repo(
    *,
    id: uuid.UUID = REPO_ID,
    name: str = "widgets",
    provider: str = "github",
    url: str = REPO_URL,
    org: str = "acme",
    branch_mappings: dict | None = None,
    public_branch: str = "main",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        name=name,
        provider=provider,
        url=url,
        org=org,
        branch_mappings=branch_mappings or {"main": "main", "develop": "develop"},
        public_branch=public_branch,
    )


def _mock_session_and_factory():
    """Return ``(session, factory)`` where factory() is an async context manager."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=session)
    return session, factory


def _mock_ctx(session_factory):
    """Build a mock Context matching ``ctx.request_context.lifespan_context``."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"session_factory": session_factory}
    return ctx


def _mock_execute_result(rows: list) -> MagicMock:
    """Simulate ``session.execute(stmt)`` returning ORM rows via ``.scalars().all()``."""
    scalars = MagicMock()
    scalars.all.return_value = rows
    result = MagicMock()
    result.scalars.return_value = scalars
    return result


# ===================================================================
# Tool registration tests
# ===================================================================


class TestMCPServerRegistration:
    """Verify server metadata and tool schemas."""

    def test_server_name(self):
        assert mcp.name == "autodoc"

    def test_exactly_two_tools_registered(self):
        tools = list(mcp._tool_manager._tools.values())
        assert len(tools) == 2

    def test_find_repository_registered(self):
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        assert "find_repository" in tools

    def test_query_documents_registered(self):
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        assert "query_documents" in tools

    def test_find_repository_schema(self):
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        schema = tools["find_repository"].parameters
        props = schema["properties"]
        assert "search" in props
        assert schema["required"] == ["search"]

    def test_query_documents_schema(self):
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        schema = tools["query_documents"].parameters
        props = schema["properties"]
        assert "repository_id" in props
        assert "query" in props
        assert "search_type" in props
        assert props["search_type"]["default"] == "hybrid"
        assert "limit" in props
        assert props["limit"]["default"] == 10
        assert set(schema["required"]) == {"repository_id", "query"}

    def test_find_repository_description_mentions_key_terms(self):
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        desc = tools["find_repository"].description.lower()
        assert "name" in desc
        assert "url" in desc
        assert "partial" in desc

    def test_query_documents_description_mentions_search(self):
        tools = {t.name: t for t in mcp._tool_manager._tools.values()}
        desc = tools["query_documents"].description.lower()
        assert "search" in desc


# ===================================================================
# find_repository tests
# ===================================================================


class TestFindRepository:
    """Tests for the find_repository MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_matching_repositories(self):
        repo = _make_repo()
        session, factory = _mock_session_and_factory()
        session.execute.return_value = _mock_execute_result([repo])
        ctx = _mock_ctx(factory)

        result = await _find_repository_fn(search="widgets", ctx=ctx)

        assert "repositories" in result
        assert len(result["repositories"]) == 1
        r = result["repositories"][0]
        assert r["id"] == str(REPO_ID)
        assert r["name"] == "widgets"
        assert r["provider"] == "github"
        assert r["url"] == REPO_URL
        assert "main" in r["branches"]
        assert "develop" in r["branches"]

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_matches(self):
        session, factory = _mock_session_and_factory()
        session.execute.return_value = _mock_execute_result([])
        ctx = _mock_ctx(factory)

        result = await _find_repository_fn(search="nonexistent", ctx=ctx)

        assert result["repositories"] == []

    @pytest.mark.asyncio
    async def test_multiple_results(self):
        repos = [
            _make_repo(id=uuid.uuid4(), name="alpha"),
            _make_repo(id=uuid.uuid4(), name="beta"),
        ]
        session, factory = _mock_session_and_factory()
        session.execute.return_value = _mock_execute_result(repos)
        ctx = _mock_ctx(factory)

        result = await _find_repository_fn(search="a", ctx=ctx)

        assert len(result["repositories"]) == 2

    @pytest.mark.asyncio
    async def test_branches_extracted_from_branch_mappings_keys(self):
        repo = _make_repo(branch_mappings={"main": "main", "release/1.0": "release"})
        session, factory = _mock_session_and_factory()
        session.execute.return_value = _mock_execute_result([repo])
        ctx = _mock_ctx(factory)

        result = await _find_repository_fn(search="test", ctx=ctx)

        branches = result["repositories"][0]["branches"]
        assert set(branches) == {"main", "release/1.0"}

    @pytest.mark.asyncio
    async def test_session_execute_called(self):
        session, factory = _mock_session_and_factory()
        session.execute.return_value = _mock_execute_result([])
        ctx = _mock_ctx(factory)

        await _find_repository_fn(search="test", ctx=ctx)

        session.execute.assert_awaited_once()


# ===================================================================
# query_documents tests
# ===================================================================


class TestQueryDocuments:
    """Tests for the query_documents MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_search_results(self):
        repo = _make_repo()
        search_response = SearchResponse(
            results=[
                SearchResult(
                    page_key="getting-started",
                    title="Getting Started",
                    snippet="Install the package...",
                    score=0.85,
                    best_chunk_content="Run pip install",
                    best_chunk_heading_path=["Setup", "Install"],
                    scope_path=".",
                ),
            ],
            total=1,
            search_type="hybrid",
        )

        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = search_response

            result = await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="install",
                ctx=ctx,
            )

        assert "results" in result
        assert result["total"] == 1
        assert result["search_type"] == "hybrid"
        r = result["results"][0]
        assert r["page_key"] == "getting-started"
        assert r["title"] == "Getting Started"
        assert r["snippet"] == "Install the package..."
        assert r["score"] == 0.85
        assert r["best_chunk_content"] == "Run pip install"
        assert r["best_chunk_heading_path"] == ["Setup", "Install"]
        assert r["scope_path"] == "."

    @pytest.mark.asyncio
    async def test_invalid_uuid_returns_error(self):
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        result = await _query_documents_fn(
            repository_id="not-a-uuid",
            query="test",
            ctx=ctx,
        )

        assert "error" in result
        assert "Invalid repository_id" in result["error"]

    @pytest.mark.asyncio
    async def test_repo_not_found_returns_error(self):
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with patch("src.mcp_server.RepositoryRepo") as mock_repo_cls:
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = None
            mock_repo_cls.return_value = mock_repo_inst

            result = await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                ctx=ctx,
            )

        assert "error" in result
        assert "Repository not found" in result["error"]

    @pytest.mark.asyncio
    async def test_uses_public_branch_for_search(self):
        repo = _make_repo(public_branch="develop")
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = SearchResponse(
                results=[], total=0, search_type="hybrid"
            )

            await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                ctx=ctx,
            )

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["branch"] == "develop"

    @pytest.mark.asyncio
    async def test_defaults_to_hybrid_search(self):
        repo = _make_repo()
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = SearchResponse(
                results=[], total=0, search_type="hybrid"
            )

            await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                ctx=ctx,
            )

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["search_type"] == "hybrid"

    @pytest.mark.asyncio
    async def test_custom_search_type_and_limit(self):
        repo = _make_repo()
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = SearchResponse(
                results=[], total=0, search_type="text"
            )

            await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                search_type="text",
                limit=5,
                ctx=ctx,
            )

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["search_type"] == "text"
        assert call_kwargs["limit"] == 5

    @pytest.mark.asyncio
    async def test_invalid_search_type_returns_error(self):
        repo = _make_repo()
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch(
                "src.mcp_server.search_documents",
                new_callable=AsyncMock,
                side_effect=PermanentError("Invalid search_type 'fuzzy'"),
            ),
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst

            result = await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                search_type="fuzzy",
                ctx=ctx,
            )

        assert "error" in result
        assert "Invalid search_type" in result["error"]

    @pytest.mark.asyncio
    async def test_results_with_null_chunk_fields(self):
        repo = _make_repo()
        search_response = SearchResponse(
            results=[
                SearchResult(
                    page_key="page-a",
                    title="Page A",
                    snippet="Content of page A.",
                    score=0.6,
                    best_chunk_content=None,
                    best_chunk_heading_path=None,
                    scope_path=".",
                ),
            ],
            total=1,
            search_type="text",
        )

        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = search_response

            result = await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                search_type="text",
                ctx=ctx,
            )

        r = result["results"][0]
        assert r["best_chunk_content"] is None
        assert r["best_chunk_heading_path"] is None

    @pytest.mark.asyncio
    async def test_passes_repository_id_to_search(self):
        repo = _make_repo()
        _session, factory = _mock_session_and_factory()
        ctx = _mock_ctx(factory)

        with (
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = SearchResponse(
                results=[], total=0, search_type="hybrid"
            )

            await _query_documents_fn(
                repository_id=str(REPO_ID),
                query="test",
                ctx=ctx,
            )

        call_kwargs = mock_search.call_args.kwargs
        assert call_kwargs["repository_id"] == REPO_ID


# ===================================================================
# MCP Client integration test
# ===================================================================


class TestMCPClientIntegration:
    """Test tools via FastMCP Client (in-process transport).

    Patches the lifespan so no real database connection is needed.
    """

    @pytest.mark.asyncio
    async def test_find_repository_via_client(self):
        repo = _make_repo()

        session, factory = _mock_session_and_factory()
        session.execute.return_value = _mock_execute_result([repo])

        with (
            patch("src.mcp_server.get_session_factory", return_value=factory),
            patch("src.mcp_server.dispose_engine", new_callable=AsyncMock),
        ):
            from fastmcp import Client

            async with Client(mcp) as client:
                result = await client.call_tool(
                    "find_repository", {"search": "widgets"}
                )

        # CallToolResult has content list with TextContent blocks
        assert result.content is not None
        assert not result.is_error

    @pytest.mark.asyncio
    async def test_query_documents_via_client(self):
        repo = _make_repo()
        search_response = SearchResponse(
            results=[
                SearchResult(
                    page_key="intro",
                    title="Introduction",
                    snippet="Welcome.",
                    score=0.9,
                ),
            ],
            total=1,
            search_type="hybrid",
        )

        _session, factory = _mock_session_and_factory()

        with (
            patch("src.mcp_server.get_session_factory", return_value=factory),
            patch("src.mcp_server.dispose_engine", new_callable=AsyncMock),
            patch("src.mcp_server.RepositoryRepo") as mock_repo_cls,
            patch("src.mcp_server.search_documents", new_callable=AsyncMock) as mock_search,
        ):
            mock_repo_inst = AsyncMock()
            mock_repo_inst.get_by_id.return_value = repo
            mock_repo_cls.return_value = mock_repo_inst
            mock_search.return_value = search_response

            from fastmcp import Client

            async with Client(mcp) as client:
                result = await client.call_tool(
                    "query_documents",
                    {"repository_id": str(REPO_ID), "query": "intro"},
                )

        assert result.content is not None
        assert not result.is_error
