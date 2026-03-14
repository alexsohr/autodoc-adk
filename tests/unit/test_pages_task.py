from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.common.agent_result import AgentResult, TokenUsage
from src.agents.page_generator.schemas import GeneratedPage
from src.agents.structure_extractor.schemas import PageSpec
from src.flows.schemas import PageTaskResult, StructureTaskResult, TokenUsageResult
from src.flows.tasks.pages import generate_pages, generate_single_page
from src.services.config_loader import AutodocConfig, StyleConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config() -> AutodocConfig:
    return AutodocConfig(
        include=[],
        exclude=[],
        style=StyleConfig(audience="developers", tone="neutral", detail_level="standard"),
        custom_instructions="",
    )


def _make_page_spec(page_key: str = "test-page") -> PageSpec:
    return PageSpec(
        page_key=page_key,
        title=f"Title for {page_key}",
        description="A test page",
        importance="medium",
        page_type="overview",
        source_files=["src/main.py"],
        related_pages=[],
    )


def _make_agent_result(page_key: str = "test-page", score: float = 8.0) -> AgentResult[GeneratedPage]:
    return AgentResult(
        output=GeneratedPage(
            page_key=page_key,
            title=f"Title for {page_key}",
            content="# Test content",
            source_files=["src/main.py"],
        ),
        attempts=1,
        final_score=score,
        passed_quality_gate=True,
        below_minimum_floor=False,
        token_usage=TokenUsage(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            calls=2,
        ),
    )


def _make_structure_result(page_keys: list[str]) -> StructureTaskResult:
    pages = [
        {"page_key": k, "title": f"Title {k}", "description": "desc"}
        for k in page_keys
    ]
    return StructureTaskResult(
        final_score=8.0,
        passed_quality_gate=True,
        below_minimum_floor=False,
        attempts=1,
        token_usage=TokenUsageResult(),
        sections_json=[{"pages": pages, "subsections": []}],
    )


def _patch_settings():
    settings = MagicMock()
    settings.DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test"
    return patch("src.flows.tasks.pages.get_settings", return_value=settings)


def _patch_session_service():
    return patch(
        "google.adk.sessions.DatabaseSessionService",
        return_value=MagicMock(),
    )


def _patch_db():
    """Patch create_async_engine and WikiRepo for per-task engine creation."""
    mock_wiki_repo = AsyncMock()
    mock_wiki_repo.create_pages = AsyncMock()

    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_factory = MagicMock(return_value=mock_ctx)
    mock_engine = AsyncMock()
    mock_engine.dispose = AsyncMock()

    return (
        patch("src.flows.tasks.pages.create_async_engine", return_value=mock_engine),
        patch("src.flows.tasks.pages.async_sessionmaker", return_value=mock_factory),
        patch("src.flows.tasks.pages.WikiRepo", return_value=mock_wiki_repo),
    )


# ---------------------------------------------------------------------------
# generate_single_page tests
# ---------------------------------------------------------------------------


class TestGenerateSinglePage:
    """Unit tests for the generate_single_page task."""

    async def test_success(self):
        """A successful agent run returns a PageTaskResult and persists the page."""
        page_spec = _make_page_spec()
        agent_result = _make_agent_result()
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(return_value=agent_result)

        db_patches = _patch_db()

        with (
            _patch_settings(),
            _patch_session_service(),
            patch("src.flows.tasks.pages.PageGenerator", return_value=mock_agent),
            db_patches[0],
            db_patches[1],
            db_patches[2] as mock_wiki_repo_cls,
        ):
            result = await generate_single_page.fn(
                job_id=uuid.uuid4(),
                wiki_structure_id=uuid.uuid4(),
                page_spec=page_spec,
                repo_path="/tmp/repo",
                config=_make_config(),
            )

        assert isinstance(result, PageTaskResult)
        assert result.page_key == "test-page"
        assert result.final_score == 8.0
        assert result.passed_quality_gate is True
        assert result.attempts == 1
        assert result.token_usage.total_tokens == 150
        # Verify DB write occurred
        mock_wiki_repo_cls.return_value.create_pages.assert_awaited_once()

    async def test_failure_propagates(self):
        """When the agent raises, the exception propagates (no internal catch)."""
        page_spec = _make_page_spec()
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM timeout"))

        with (
            _patch_settings(),
            _patch_session_service(),
            patch("src.flows.tasks.pages.PageGenerator", return_value=mock_agent),
            pytest.raises(RuntimeError, match="LLM timeout"),
        ):
            await generate_single_page.fn(
                job_id=uuid.uuid4(),
                wiki_structure_id=uuid.uuid4(),
                page_spec=page_spec,
                repo_path="/tmp/repo",
                config=_make_config(),
            )


# ---------------------------------------------------------------------------
# generate_pages flow tests
# ---------------------------------------------------------------------------

def _make_page_task_result(page_key: str = "test-page", score: float = 8.0) -> PageTaskResult:
    return PageTaskResult(
        page_key=page_key,
        final_score=score,
        passed_quality_gate=True,
        below_minimum_floor=False,
        attempts=1,
        token_usage=TokenUsageResult(
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            calls=2,
        ),
    )


class TestGeneratePages:
    """Unit tests for the generate_pages flow (fan-out/fan-in logic)."""

    async def test_fan_out_all_succeed(self):
        """All 3 page specs succeed — 3 results returned."""
        keys = ["page-a", "page-b", "page-c"]

        def mock_submit(**kwargs):
            page_key = kwargs["page_spec"].page_key
            future = MagicMock()
            future.result = MagicMock(return_value=_make_page_task_result(page_key))
            return future

        with (
            patch.object(generate_single_page, "submit", side_effect=mock_submit),
            patch("src.flows.tasks.pages.wait"),
        ):
                results = await generate_pages.fn(
                    job_id=uuid.uuid4(),
                    wiki_structure_id=uuid.uuid4(),
                    structure_result=_make_structure_result(keys),
                    repo_path="/tmp/repo",
                    config=_make_config(),
                )

        assert len(results) == 3
        assert {r.page_key for r in results} == set(keys)

    async def test_partial_failure(self):
        """2 succeed + 1 fails — 2 results returned."""
        keys = ["page-a", "page-b", "page-c"]

        def mock_submit(**kwargs):
            page_key = kwargs["page_spec"].page_key
            future = MagicMock()
            if page_key == "page-b":
                future.result = MagicMock(side_effect=RuntimeError("LLM timeout"))
            else:
                future.result = MagicMock(return_value=_make_page_task_result(page_key))
            return future

        with (
            patch.object(generate_single_page, "submit", side_effect=mock_submit),
            patch("src.flows.tasks.pages.wait"),
        ):
                results = await generate_pages.fn(
                    job_id=uuid.uuid4(),
                    wiki_structure_id=uuid.uuid4(),
                    structure_result=_make_structure_result(keys),
                    repo_path="/tmp/repo",
                    config=_make_config(),
                )

        assert len(results) == 2
        assert {r.page_key for r in results} == {"page-a", "page-c"}

    async def test_empty_specs(self):
        """Empty sections_json returns empty list without submitting tasks."""
        result = await generate_pages.fn(
            job_id=uuid.uuid4(),
            wiki_structure_id=uuid.uuid4(),
            structure_result=StructureTaskResult(
                final_score=8.0,
                passed_quality_gate=True,
                below_minimum_floor=False,
                attempts=1,
                token_usage=TokenUsageResult(),
                sections_json=[],
            ),
            repo_path="/tmp/repo",
            config=_make_config(),
        )

        assert result == []

    async def test_all_fail(self):
        """All pages fail — raises RuntimeError."""
        keys = ["page-a", "page-b"]

        def mock_submit(**kwargs):
            future = MagicMock()
            future.result = MagicMock(side_effect=RuntimeError("boom"))
            return future

        with (
            patch.object(generate_single_page, "submit", side_effect=mock_submit),
            patch("src.flows.tasks.pages.wait"),
            pytest.raises(RuntimeError, match="All 2 page generation tasks failed"),
        ):
            await generate_pages.fn(
                job_id=uuid.uuid4(),
                wiki_structure_id=uuid.uuid4(),
                structure_result=_make_structure_result(keys),
                repo_path="/tmp/repo",
                config=_make_config(),
            )

    async def test_none_sections_json(self):
        """None sections_json returns empty list."""
        result = await generate_pages.fn(
            job_id=uuid.uuid4(),
            wiki_structure_id=uuid.uuid4(),
            structure_result=StructureTaskResult(
                final_score=8.0,
                passed_quality_gate=True,
                below_minimum_floor=False,
                attempts=1,
                token_usage=TokenUsageResult(),
                sections_json=None,
            ),
            repo_path="/tmp/repo",
            config=_make_config(),
        )

        assert result == []
