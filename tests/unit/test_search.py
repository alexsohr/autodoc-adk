"""Unit tests for SearchRepo and search_documents orchestrator."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.database.repos.search_repo import (
    HybridSearchResult,
    SearchRepo,
    SemanticSearchResult,
    TextSearchResult,
    _LATEST_VERSION_SUBQUERY,
)
from src.errors import PermanentError
from src.services.search import (
    _extract_snippet,
    search_documents,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REPO_ID = uuid.uuid4()
PAGE_ID = uuid.uuid4()
BRANCH = "main"
FAKE_EMBEDDING = [0.1] * 3072


def _make_text_row(
    *,
    page_id: uuid.UUID = PAGE_ID,
    page_key: str = "getting-started",
    title: str = "Getting Started",
    content: str = "Install the package using pip.",
    score: float = 0.85,
    scope_path: str = ".",
) -> SimpleNamespace:
    """Simulate a SQLAlchemy Row returned by execute() for text search."""
    return SimpleNamespace(
        page_id=page_id,
        page_key=page_key,
        title=title,
        content=content,
        score=score,
        scope_path=scope_path,
    )


def _make_semantic_row(
    *,
    page_id: uuid.UUID = PAGE_ID,
    page_key: str = "architecture",
    title: str = "Architecture Overview",
    content: str = "The system uses an event-driven architecture.",
    score: float = 0.92,
    best_chunk_content: str = "Event bus processes messages asynchronously.",
    best_chunk_heading_path: list[str] | None = None,
    scope_path: str = ".",
) -> SimpleNamespace:
    return SimpleNamespace(
        page_id=page_id,
        page_key=page_key,
        title=title,
        content=content,
        score=score,
        best_chunk_content=best_chunk_content,
        best_chunk_heading_path=best_chunk_heading_path or ["Architecture", "Event Bus"],
        scope_path=scope_path,
    )


def _make_hybrid_row(
    *,
    page_id: uuid.UUID = PAGE_ID,
    page_key: str = "api-reference",
    title: str = "API Reference",
    content: str = "## Endpoints\n\nThe API exposes REST endpoints.",
    score: float = 0.035,
    best_chunk_content: str | None = "POST /search returns results.",
    best_chunk_heading_path: list[str] | None = None,
    scope_path: str = ".",
) -> SimpleNamespace:
    return SimpleNamespace(
        page_id=page_id,
        page_key=page_key,
        title=title,
        content=content,
        score=score,
        best_chunk_content=best_chunk_content,
        best_chunk_heading_path=best_chunk_heading_path,
        scope_path=scope_path,
    )


def _mock_session(rows: list) -> AsyncMock:
    """Return an AsyncMock session whose execute() returns the given rows."""
    session = AsyncMock()
    session.execute.return_value = iter(rows)
    return session


# ===================================================================
# SearchRepo tests
# ===================================================================


class TestSearchRepoTextSearch:
    """Tests for SearchRepo.text_search."""

    @pytest.mark.asyncio
    async def test_returns_text_search_results(self):
        row = _make_text_row()
        session = _mock_session([row])
        repo = SearchRepo(session)

        results = await repo.text_search(
            query="install",
            repository_id=REPO_ID,
            branch=BRANCH,
            limit=5,
        )

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, TextSearchResult)
        assert r.page_id == PAGE_ID
        assert r.page_key == "getting-started"
        assert r.title == "Getting Started"
        assert r.content == "Install the package using pip."
        assert r.score == 0.85
        assert r.scope_path == "."

    @pytest.mark.asyncio
    async def test_passes_correct_params_without_scope(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.text_search(
            query="deploy",
            repository_id=REPO_ID,
            branch=BRANCH,
            limit=10,
        )

        session.execute.assert_awaited_once()
        _, kwargs = session.execute.call_args
        # kwargs is empty; params are passed as second positional arg
        args = session.execute.call_args[0]
        params = args[1]
        assert params["query"] == "deploy"
        assert params["repo_id"] == REPO_ID
        assert params["branch"] == BRANCH
        assert params["limit"] == 10
        assert "scope_path" not in params

    @pytest.mark.asyncio
    async def test_passes_scope_path_when_provided(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.text_search(
            query="install",
            repository_id=REPO_ID,
            branch=BRANCH,
            scope_path="packages/core",
            limit=10,
        )

        args = session.execute.call_args[0]
        params = args[1]
        assert params["scope_path"] == "packages/core"

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rows(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        results = await repo.text_search(
            query="nonexistent",
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_multiple_rows(self):
        rows = [
            _make_text_row(page_key="page-a", score=0.9),
            _make_text_row(page_key="page-b", score=0.7),
        ]
        session = _mock_session(rows)
        repo = SearchRepo(session)

        results = await repo.text_search(
            query="example",
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        assert len(results) == 2
        assert results[0].page_key == "page-a"
        assert results[1].page_key == "page-b"


class TestSearchRepoSemanticSearch:
    """Tests for SearchRepo.semantic_search."""

    @pytest.mark.asyncio
    async def test_returns_semantic_search_results(self):
        row = _make_semantic_row()
        session = _mock_session([row])
        repo = SearchRepo(session)

        results = await repo.semantic_search(
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            limit=5,
        )

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, SemanticSearchResult)
        assert r.page_key == "architecture"
        assert r.best_chunk_content == "Event bus processes messages asynchronously."
        assert r.best_chunk_heading_path == ["Architecture", "Event Bus"]
        assert r.score == 0.92

    @pytest.mark.asyncio
    async def test_embedding_passed_as_string(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.semantic_search(
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        args = session.execute.call_args[0]
        params = args[1]
        assert params["query_embedding"] == str(FAKE_EMBEDDING)

    @pytest.mark.asyncio
    async def test_scope_path_included_when_set(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.semantic_search(
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            scope_path="services/auth",
        )

        args = session.execute.call_args[0]
        params = args[1]
        assert params["scope_path"] == "services/auth"

    @pytest.mark.asyncio
    async def test_scope_path_absent_when_none(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.semantic_search(
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            scope_path=None,
        )

        args = session.execute.call_args[0]
        params = args[1]
        assert "scope_path" not in params

    @pytest.mark.asyncio
    async def test_heading_path_converted_to_list(self):
        """The repo calls list() on row.best_chunk_heading_path."""
        row = _make_semantic_row(best_chunk_heading_path=("A", "B"))
        session = _mock_session([row])
        repo = SearchRepo(session)

        results = await repo.semantic_search(
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        assert results[0].best_chunk_heading_path == ["A", "B"]
        assert isinstance(results[0].best_chunk_heading_path, list)


class TestSearchRepoHybridSearch:
    """Tests for SearchRepo.hybrid_search."""

    @pytest.mark.asyncio
    async def test_returns_hybrid_search_results(self):
        row = _make_hybrid_row()
        session = _mock_session([row])
        repo = SearchRepo(session)

        results = await repo.hybrid_search(
            query="api endpoints",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, HybridSearchResult)
        assert r.page_key == "api-reference"
        assert r.score == 0.035

    @pytest.mark.asyncio
    async def test_nullable_chunk_fields(self):
        """HybridSearchResult supports None for chunk fields."""
        row = _make_hybrid_row(
            best_chunk_content=None,
            best_chunk_heading_path=None,
        )
        session = _mock_session([row])
        repo = SearchRepo(session)

        results = await repo.hybrid_search(
            query="api",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        assert results[0].best_chunk_content is None
        assert results[0].best_chunk_heading_path is None

    @pytest.mark.asyncio
    async def test_rrf_k_passed_as_param(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="test",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            rrf_k=42,
        )

        args = session.execute.call_args[0]
        params = args[1]
        assert params["rrf_k"] == 42

    @pytest.mark.asyncio
    async def test_scope_path_filtering(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="auth",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            scope_path="packages/auth",
        )

        args = session.execute.call_args[0]
        params = args[1]
        assert params["scope_path"] == "packages/auth"


class TestHybridSearchSQLStructure:
    """Validate that the hybrid_search SQL contains key RRF components.

    We inspect the SQL text object passed to session.execute().
    """

    @pytest.mark.asyncio
    async def test_sql_contains_rrf_formula_components(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="test",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        sql_arg = session.execute.call_args[0][0]
        sql_text = sql_arg.text

        # RRF formula: 1.0 / (:rrf_k + COALESCE(...))
        assert "COALESCE" in sql_text
        assert ":rrf_k" in sql_text
        assert "1000" in sql_text  # penalty rank for absent results

    @pytest.mark.asyncio
    async def test_sql_contains_full_outer_join(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="test",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        sql_arg = session.execute.call_args[0][0]
        sql_text = sql_arg.text

        assert "FULL OUTER JOIN" in sql_text

    @pytest.mark.asyncio
    async def test_sql_uses_latest_version_subquery(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="test",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
        )

        sql_arg = session.execute.call_args[0][0]
        sql_text = sql_arg.text

        assert "MAX(version)" in sql_text

    @pytest.mark.asyncio
    async def test_scope_filter_included_in_sql_when_provided(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="test",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            scope_path="pkg/foo",
        )

        sql_arg = session.execute.call_args[0][0]
        sql_text = sql_arg.text

        assert ":scope_path" in sql_text

    @pytest.mark.asyncio
    async def test_scope_filter_absent_in_sql_when_none(self):
        session = _mock_session([])
        repo = SearchRepo(session)

        await repo.hybrid_search(
            query="test",
            query_embedding=FAKE_EMBEDDING,
            repository_id=REPO_ID,
            branch=BRANCH,
            scope_path=None,
        )

        sql_arg = session.execute.call_args[0][0]
        sql_text = sql_arg.text

        assert "scope_path = :scope_path" not in sql_text


# ===================================================================
# _extract_snippet tests
# ===================================================================


class TestExtractSnippet:
    """Tests for the snippet extraction helper."""

    def test_empty_content(self):
        assert _extract_snippet("") == ""

    def test_short_content_unchanged(self):
        text = "A short paragraph."
        assert _extract_snippet(text) == text

    def test_strips_leading_heading(self):
        text = "## Heading\nParagraph text here."
        result = _extract_snippet(text)
        assert result == "Heading\nParagraph text here."
        assert not result.startswith("#")

    def test_strips_h1_heading(self):
        text = "# Title\nBody."
        result = _extract_snippet(text)
        assert result == "Title\nBody."

    def test_strips_h6_heading(self):
        text = "###### Deep Heading\nContent."
        result = _extract_snippet(text)
        assert result == "Deep Heading\nContent."

    def test_truncates_at_word_boundary(self):
        # Create a string longer than 200 chars
        words = "word " * 50  # 250 chars
        result = _extract_snippet(words, max_length=200)
        assert result.endswith("...")
        assert len(result) <= 204  # 200 + "..."

    def test_no_mid_word_cut(self):
        text = "abcdefghij " * 25  # 275 chars
        result = _extract_snippet(text, max_length=50)
        # Should end at a word boundary + "..."
        assert result.endswith("...")
        # The part before "..." should not end with a partial word
        body = result[:-3]
        assert body.endswith("abcdefghij")

    def test_no_ellipsis_when_under_limit(self):
        text = "Short text."
        result = _extract_snippet(text, max_length=200)
        assert "..." not in result

    def test_custom_max_length(self):
        text = "The quick brown fox jumps over the lazy dog and then runs away."
        result = _extract_snippet(text, max_length=30)
        assert result.endswith("...")
        assert len(result) <= 34  # 30 + "..." + word boundary slack


# ===================================================================
# search_documents orchestrator tests
# ===================================================================


class TestSearchDocumentsText:
    """Text search delegates to search_repo.text_search, no embedding."""

    @pytest.mark.asyncio
    async def test_delegates_to_text_search(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.text_search.return_value = [
            TextSearchResult(
                page_id=PAGE_ID,
                page_key="intro",
                title="Introduction",
                content="Welcome to the docs.",
                score=0.8,
                scope_path=".",
            )
        ]

        with patch("src.services.search.embed_query") as mock_embed:
            response = await search_documents(
                query="welcome",
                search_type="text",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

            mock_embed.assert_not_called()

        mock_repo.text_search.assert_awaited_once()
        assert response.search_type == "text"
        assert response.total == 1
        assert response.results[0].page_key == "intro"
        assert response.results[0].snippet == "Welcome to the docs."

    @pytest.mark.asyncio
    async def test_text_results_have_no_chunk_fields(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.text_search.return_value = [
            TextSearchResult(
                page_id=PAGE_ID,
                page_key="intro",
                title="Introduction",
                content="Welcome.",
                score=0.8,
                scope_path=".",
            )
        ]

        with patch("src.services.search.embed_query"):
            response = await search_documents(
                query="welcome",
                search_type="text",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

        result = response.results[0]
        assert result.best_chunk_content is None
        assert result.best_chunk_heading_path is None


class TestSearchDocumentsSemantic:
    """Semantic search calls embed_query, then search_repo.semantic_search."""

    @pytest.mark.asyncio
    async def test_calls_embed_then_semantic_search(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.semantic_search.return_value = [
            SemanticSearchResult(
                page_id=PAGE_ID,
                page_key="arch",
                title="Architecture",
                content="Event-driven design.",
                score=0.91,
                best_chunk_content="Message bus pattern.",
                best_chunk_heading_path=["Arch", "Bus"],
                scope_path=".",
            )
        ]

        with patch("src.services.search.embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_EMBEDDING

            response = await search_documents(
                query="event driven",
                search_type="semantic",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

            mock_embed.assert_awaited_once_with("event driven")

        mock_repo.semantic_search.assert_awaited_once()
        call_kwargs = mock_repo.semantic_search.call_args.kwargs
        assert call_kwargs["query_embedding"] == FAKE_EMBEDDING

        assert response.search_type == "semantic"
        assert response.total == 1
        result = response.results[0]
        assert result.best_chunk_content == "Message bus pattern."
        assert result.best_chunk_heading_path == ["Arch", "Bus"]


class TestSearchDocumentsHybrid:
    """Hybrid search calls embed_query, then search_repo.hybrid_search."""

    @pytest.mark.asyncio
    async def test_calls_embed_then_hybrid_search(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.hybrid_search.return_value = [
            HybridSearchResult(
                page_id=PAGE_ID,
                page_key="api-ref",
                title="API Reference",
                content="REST API docs.",
                score=0.04,
                best_chunk_content="POST /search",
                best_chunk_heading_path=["API", "Search"],
                scope_path=".",
            )
        ]

        with patch("src.services.search.embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_EMBEDDING

            response = await search_documents(
                query="search endpoint",
                search_type="hybrid",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

            mock_embed.assert_awaited_once_with("search endpoint")

        mock_repo.hybrid_search.assert_awaited_once()
        call_kwargs = mock_repo.hybrid_search.call_args.kwargs
        assert call_kwargs["query"] == "search endpoint"
        assert call_kwargs["query_embedding"] == FAKE_EMBEDDING

        assert response.search_type == "hybrid"
        assert response.total == 1

    @pytest.mark.asyncio
    async def test_hybrid_results_have_nullable_chunk_fields(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.hybrid_search.return_value = [
            HybridSearchResult(
                page_id=PAGE_ID,
                page_key="page-x",
                title="Page X",
                content="Only matched via text search.",
                score=0.01,
                best_chunk_content=None,
                best_chunk_heading_path=None,
                scope_path=".",
            )
        ]

        with patch("src.services.search.embed_query", new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = FAKE_EMBEDDING

            response = await search_documents(
                query="text only",
                search_type="hybrid",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

        result = response.results[0]
        assert result.best_chunk_content is None
        assert result.best_chunk_heading_path is None


class TestSearchDocumentsInvalidType:
    """Invalid search_type raises PermanentError."""

    @pytest.mark.asyncio
    async def test_raises_permanent_error(self):
        mock_repo = AsyncMock(spec=SearchRepo)

        with pytest.raises(PermanentError, match="Invalid search_type"):
            await search_documents(
                query="anything",
                search_type="fuzzy",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

    @pytest.mark.asyncio
    async def test_error_message_lists_valid_types(self):
        mock_repo = AsyncMock(spec=SearchRepo)

        with pytest.raises(PermanentError) as exc_info:
            await search_documents(
                query="anything",
                search_type="invalid",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

        msg = str(exc_info.value)
        assert "hybrid" in msg
        assert "semantic" in msg
        assert "text" in msg


class TestSearchDocumentsResultMapping:
    """Verify that results are mapped into SearchResult with snippets."""

    @pytest.mark.asyncio
    async def test_snippet_extracted_from_content(self):
        long_content = "## Getting Started\n" + "word " * 100
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.text_search.return_value = [
            TextSearchResult(
                page_id=PAGE_ID,
                page_key="start",
                title="Getting Started",
                content=long_content,
                score=0.7,
                scope_path=".",
            )
        ]

        with patch("src.services.search.embed_query"):
            response = await search_documents(
                query="start",
                search_type="text",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

        snippet = response.results[0].snippet
        # Heading should be stripped
        assert not snippet.startswith("#")
        # Content was truncated
        assert snippet.endswith("...")

    @pytest.mark.asyncio
    async def test_scope_path_propagated(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.text_search.return_value = [
            TextSearchResult(
                page_id=PAGE_ID,
                page_key="k",
                title="T",
                content="C",
                score=0.5,
                scope_path="packages/core",
            )
        ]

        with patch("src.services.search.embed_query"):
            response = await search_documents(
                query="q",
                search_type="text",
                repository_id=REPO_ID,
                branch=BRANCH,
                scope="packages/core",
                search_repo=mock_repo,
            )

        assert response.results[0].scope_path == "packages/core"

    @pytest.mark.asyncio
    async def test_scope_passed_to_repo(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.text_search.return_value = []

        with patch("src.services.search.embed_query"):
            await search_documents(
                query="q",
                search_type="text",
                repository_id=REPO_ID,
                branch=BRANCH,
                scope="libs/shared",
                search_repo=mock_repo,
            )

        call_kwargs = mock_repo.text_search.call_args.kwargs
        assert call_kwargs["scope_path"] == "libs/shared"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        mock_repo = AsyncMock(spec=SearchRepo)
        mock_repo.text_search.return_value = []

        with patch("src.services.search.embed_query"):
            response = await search_documents(
                query="nonexistent",
                search_type="text",
                repository_id=REPO_ID,
                branch=BRANCH,
                search_repo=mock_repo,
            )

        assert response.total == 0
        assert response.results == []


# ===================================================================
# Latest-version subquery constant test
# ===================================================================


class TestLatestVersionSubquery:
    """Validate the reusable SQL fragment."""

    def test_contains_max_version(self):
        assert "MAX(version)" in _LATEST_VERSION_SUBQUERY

    def test_scoped_to_repo_branch(self):
        assert ":repo_id" in _LATEST_VERSION_SUBQUERY
        assert ":branch" in _LATEST_VERSION_SUBQUERY
