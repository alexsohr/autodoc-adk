"""Integration tests for full_generation_flow and incremental_update_flow.

These tests use ``prefect.testing.utilities.prefect_test_harness`` to run
Prefect flows in a temporary, in-memory environment. External dependencies
(LLM calls, git operations, provider APIs, database) are mocked so that
only the Prefect flow orchestration logic is exercised.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.common.agent_result import AgentResult, TokenUsage
from src.agents.page_generator.schemas import GeneratedPage
from src.agents.readme_distiller.schemas import ReadmeOutput
from src.agents.structure_extractor.schemas import (
    PageSpec,
    SectionSpec,
    WikiStructureSpec,
)
from src.services.config_loader import AutodocConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ID = uuid.uuid4()
JOB_ID = uuid.uuid4()
BRANCH = "main"
COMMIT_SHA = "abc123def456789012345678901234567890abcd"
BASELINE_SHA = "000000000000000000000000000000000000dead"
REPO_PATH = "/tmp/autodoc_test_clone"


# ---------------------------------------------------------------------------
# Helpers — mock factories
# ---------------------------------------------------------------------------


def _make_repository(
    repo_id: uuid.UUID = REPO_ID,
) -> SimpleNamespace:
    """Create a fake Repository-like object."""
    return SimpleNamespace(
        id=repo_id,
        provider="github",
        url="https://github.com/org/repo",
        org="org",
        name="repo",
        branch_mappings={"main": "main"},
        public_branch="main",
        access_token="ghp_test_token",
    )


def _make_job(
    job_id: uuid.UUID = JOB_ID,
    status: str = "PENDING",
    callback_url: str | None = None,
    **kwargs,
) -> SimpleNamespace:
    """Create a fake Job-like object."""
    defaults = dict(
        id=job_id,
        repository_id=REPO_ID,
        status=status,
        mode="full",
        branch=BRANCH,
        commit_sha=None,
        force=False,
        dry_run=False,
        prefect_flow_run_id=None,
        app_commit_sha=None,
        quality_report=None,
        token_usage=None,
        config_warnings=None,
        callback_url=callback_url,
        error_message=None,
        pull_request_url=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_wiki_structure(
    repo_id: uuid.UUID = REPO_ID,
    branch: str = BRANCH,
    scope_path: str = ".",
) -> SimpleNamespace:
    """Create a fake WikiStructure-like object."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        repository_id=repo_id,
        branch=branch,
        scope_path=scope_path,
        version=1,
        title="Test Project",
        description="Test project docs",
        sections=[
            {
                "title": "Core",
                "description": "Core module docs",
                "pages": [
                    {
                        "page_key": "core-overview",
                        "title": "Core Overview",
                        "description": "Overview of core module",
                        "importance": "high",
                        "page_type": "overview",
                        "source_files": ["src/core.py"],
                        "related_pages": [],
                    },
                ],
                "subsections": [],
            },
        ],
        commit_sha=BASELINE_SHA,
    )


def _make_wiki_page(
    structure_id: uuid.UUID | None = None,
    page_key: str = "core-overview",
) -> SimpleNamespace:
    """Create a fake WikiPage-like object."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        wiki_structure_id=structure_id or uuid.uuid4(),
        page_key=page_key,
        title="Core Overview",
        description="Overview of core module",
        importance="high",
        page_type="overview",
        source_files=["src/core.py"],
        related_pages=[],
        content="# Core Overview\n\nThis is the core module.",
        quality_score=8.5,
    )


def _make_structure_result(
    below_floor: bool = False,
) -> AgentResult[WikiStructureSpec]:
    """Create a fake AgentResult for structure extraction."""
    return AgentResult(
        output=WikiStructureSpec(
            title="Test Project",
            description="Test project documentation",
            sections=[
                SectionSpec(
                    title="Core",
                    description="Core module docs",
                    pages=[
                        PageSpec(
                            page_key="core-overview",
                            title="Core Overview",
                            description="Overview of core module",
                            importance="high",
                            page_type="overview",
                            source_files=["src/core.py"],
                            related_pages=[],
                        ),
                    ],
                    subsections=[],
                ),
            ],
        ),
        attempts=1,
        final_score=8.5,
        passed_quality_gate=True,
        below_minimum_floor=below_floor,
        evaluation_history=[],
        token_usage=TokenUsage(
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            calls=2,
        ),
    )


def _make_page_result(
    page_key: str = "core-overview",
    below_floor: bool = False,
) -> AgentResult[GeneratedPage]:
    """Create a fake AgentResult for page generation."""
    return AgentResult(
        output=GeneratedPage(
            page_key=page_key,
            title="Core Overview",
            content="# Core Overview\n\nThis is the core module.",
            source_files=["src/core.py"],
        ),
        attempts=1,
        final_score=8.0,
        passed_quality_gate=True,
        below_minimum_floor=below_floor,
        evaluation_history=[],
        token_usage=TokenUsage(
            input_tokens=800,
            output_tokens=400,
            total_tokens=1200,
            calls=2,
        ),
    )


def _make_readme_result(
    below_floor: bool = False,
) -> AgentResult[ReadmeOutput]:
    """Create a fake AgentResult for README distillation."""
    return AgentResult(
        output=ReadmeOutput(content="# Test Project\n\nA great project."),
        attempts=1,
        final_score=8.0,
        passed_quality_gate=True,
        below_minimum_floor=below_floor,
        evaluation_history=[],
        token_usage=TokenUsage(
            input_tokens=600,
            output_tokens=300,
            total_tokens=900,
            calls=2,
        ),
    )


def _make_config(scope_path: str = ".") -> AutodocConfig:
    """Create a default AutodocConfig."""
    return AutodocConfig(scope_path=scope_path)


def _build_mock_session_factory(
    job: SimpleNamespace,
    repository: SimpleNamespace,
    wiki_structure: SimpleNamespace | None = None,
    wiki_pages: list | None = None,
):
    """Build a mock session factory that returns mock repos.

    Returns (session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo)
    so tests can inspect or override return values.
    """
    mock_job_repo = AsyncMock()
    mock_job_repo.update_status = AsyncMock(return_value=job)
    mock_job_repo.get_by_id = AsyncMock(return_value=job)

    mock_repo_repo = AsyncMock()
    mock_repo_repo.get_by_id = AsyncMock(return_value=repository)

    mock_wiki_repo = AsyncMock()
    mock_wiki_repo.get_latest_structure = AsyncMock(return_value=wiki_structure)
    mock_wiki_repo.get_pages_for_structure = AsyncMock(return_value=wiki_pages or [])
    mock_wiki_repo.create_structure = AsyncMock(return_value=wiki_structure)
    mock_wiki_repo.create_pages = AsyncMock(return_value=[])
    mock_wiki_repo.create_chunks = AsyncMock(return_value=[])
    mock_wiki_repo.duplicate_pages = AsyncMock(return_value=[])
    mock_wiki_repo.get_baseline_sha = AsyncMock(return_value=BASELINE_SHA)

    mock_session = AsyncMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    # Make session context manager work
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # Patch the repos to be constructed from session
    mock_session_factory = MagicMock()
    mock_session_factory.return_value = mock_session

    return mock_session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, mock_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def prefect_harness():
    """Activate Prefect test harness for the duration of the test."""
    from prefect.testing.utilities import prefect_test_harness

    with prefect_test_harness():
        yield


# ---------------------------------------------------------------------------
# Tests — Full Generation Flow
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullGenerationHappyPath:
    """Full generation flow completes the entire pipeline successfully."""

    async def test_happy_path_completes_with_pr(self, prefect_harness):
        """Flow runs all steps and finishes with status COMPLETED and a PR URL."""
        repository = _make_repository()
        job = _make_job()
        wiki_structure = _make_wiki_structure()
        wiki_pages = [_make_wiki_page(structure_id=wiki_structure.id)]

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure, wiki_pages)
        )

        structure_result = _make_structure_result()
        page_results = [_make_page_result()]
        readme_result = _make_readme_result()
        scope_result = {
            "structure_result": structure_result,
            "page_results": page_results,
            "readme_result": readme_result,
            "wiki_structure_id": wiki_structure.id,
            "embedding_count": 5,
        }

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                return_value=scope_result,
            ),
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.full_generation.create_autodoc_pr",
                new_callable=AsyncMock,
                return_value="https://github.com/org/repo/pull/42",
            ) as mock_create_pr,
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ) as mock_metrics,
            patch(
                "src.flows.full_generation.archive_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.delete_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Job status should transition to RUNNING, then COMPLETED
        update_calls = mock_job_repo.update_status.call_args_list
        assert update_calls[0].args == (JOB_ID, "RUNNING")
        # Final status update should be COMPLETED
        final_call = update_calls[-1]
        assert final_call.args[1] == "COMPLETED"

        # PR should have been created
        mock_create_pr.assert_awaited_once()

        # Metrics should have been aggregated
        mock_metrics.assert_awaited_once()

        # Cleanup should have been called
        mock_cleanup.assert_awaited_once_with(repo_path=REPO_PATH)


@pytest.mark.integration
class TestFullGenerationDryRun:
    """Dry-run mode skips page generation, README, embeddings, and PR creation."""

    async def test_dry_run_skips_pr_and_sessions(self, prefect_harness):
        """With dry_run=True, no PR is created and sessions are not archived."""
        repository = _make_repository()
        job = _make_job(dry_run=True)
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        # Scope processing returns structure only (dry_run skips pages/readme)
        structure_result = _make_structure_result()
        scope_result = {
            "structure_result": structure_result,
            "page_results": [],
            "readme_result": None,
            "wiki_structure_id": wiki_structure.id,
            "embedding_count": 0,
        }

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                return_value=scope_result,
            ),
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                new_callable=AsyncMock,
            ) as mock_close_prs,
            patch(
                "src.flows.full_generation.create_autodoc_pr",
                new_callable=AsyncMock,
            ) as mock_create_pr,
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.5},
            ),
            patch(
                "src.flows.full_generation.archive_sessions",
                new_callable=AsyncMock,
            ) as mock_archive,
            patch(
                "src.flows.full_generation.delete_sessions",
                new_callable=AsyncMock,
            ) as mock_delete_sessions,
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=True,
            )

        # PR creation should be skipped entirely: no readme results -> no PR
        mock_create_pr.assert_not_awaited()
        # close_stale_autodoc_prs is also skipped because scope_readmes is empty
        mock_close_prs.assert_not_awaited()
        # Session archival should be skipped
        mock_archive.assert_not_awaited()
        mock_delete_sessions.assert_not_awaited()

        # Job should still reach COMPLETED
        final_call = mock_job_repo.update_status.call_args_list[-1]
        assert final_call.args[1] == "COMPLETED"


@pytest.mark.integration
class TestFullGenerationErrorHandling:
    """When a task fails, the flow marks the job FAILED and cleans up."""

    async def test_clone_failure_marks_job_failed(self, prefect_harness):
        """If clone_repository raises, the job is marked FAILED and cleanup runs."""
        repository = _make_repository()
        job = _make_job()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository)
        )

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Clone failed: network error"),
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Job should be marked FAILED
        failed_calls = [
            c for c in mock_job_repo.update_status.call_args_list
            if len(c.args) >= 2 and c.args[1] == "FAILED"
        ]
        assert len(failed_calls) >= 1
        failed_call = failed_calls[0]
        assert "Clone failed" in failed_call.kwargs.get("error_message", "")

        # Cleanup should NOT run since repo_path was never set (clone failed)
        mock_cleanup.assert_not_awaited()

    async def test_scope_processing_failure_marks_job_failed_if_quality_below_floor(
        self, prefect_harness
    ):
        """When scope processing returns results with below_minimum_floor, job is FAILED."""
        repository = _make_repository()
        job = _make_job()
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        # Structure result with below_minimum_floor=True
        structure_result = _make_structure_result(below_floor=True)
        scope_result = {
            "structure_result": structure_result,
            "page_results": [],
            "readme_result": None,
            "wiki_structure_id": wiki_structure.id,
            "embedding_count": 0,
        }

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                return_value=scope_result,
            ),
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 3.0},
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Job should be marked FAILED with quality gate message
        failed_calls = [
            c for c in mock_job_repo.update_status.call_args_list
            if len(c.args) >= 2 and c.args[1] == "FAILED"
        ]
        assert len(failed_calls) >= 1
        error_msg = failed_calls[0].kwargs.get("error_message", "")
        assert "Quality gate failed" in error_msg

        # Cleanup should still run
        mock_cleanup.assert_awaited_once_with(repo_path=REPO_PATH)


@pytest.mark.integration
class TestFullGenerationCallbackDelivery:
    """Callback delivery on completion and failure."""

    async def test_callback_delivered_on_completion(self, prefect_harness):
        """When callback_url is set, deliver_callback is called with COMPLETED status."""
        callback_url = "https://example.com/webhook"
        repository = _make_repository()
        job = _make_job(callback_url=callback_url)
        wiki_structure = _make_wiki_structure()
        wiki_pages = [_make_wiki_page(structure_id=wiki_structure.id)]

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure, wiki_pages)
        )

        scope_result = {
            "structure_result": _make_structure_result(),
            "page_results": [_make_page_result()],
            "readme_result": _make_readme_result(),
            "wiki_structure_id": wiki_structure.id,
            "embedding_count": 5,
        }

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                return_value=scope_result,
            ),
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.full_generation.create_autodoc_pr",
                new_callable=AsyncMock,
                return_value="https://github.com/org/repo/pull/42",
            ),
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ),
            patch(
                "src.flows.full_generation.archive_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.delete_sessions",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # deliver_callback should have been called
        mock_deliver.assert_awaited_once()
        call_kwargs = mock_deliver.call_args.kwargs
        assert call_kwargs["job_id"] == JOB_ID
        assert call_kwargs["status"] == "COMPLETED"
        assert call_kwargs["callback_url"] == callback_url
        assert call_kwargs["repository_id"] == REPO_ID
        assert call_kwargs["branch"] == BRANCH

    async def test_callback_delivered_on_error(self, prefect_harness):
        """When callback_url is set and flow fails, deliver_callback is called with FAILED."""
        callback_url = "https://example.com/webhook"
        repository = _make_repository()
        job = _make_job(callback_url=callback_url)

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository)
        )

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Network failure"),
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        mock_deliver.assert_awaited_once()
        call_kwargs = mock_deliver.call_args.kwargs
        assert call_kwargs["status"] == "FAILED"
        assert call_kwargs["callback_url"] == callback_url
        assert "Network failure" in call_kwargs["error_message"]

    async def test_no_callback_when_url_not_set(self, prefect_harness):
        """When callback_url is None, deliver_callback is never called."""
        repository = _make_repository()
        job = _make_job(callback_url=None)
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        scope_result = {
            "structure_result": _make_structure_result(),
            "page_results": [],
            "readme_result": None,
            "wiki_structure_id": wiki_structure.id,
            "embedding_count": 0,
        }

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                return_value=scope_result,
            ),
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.5},
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        mock_deliver.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests — Incremental Update Flow
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestIncrementalNoChanges:
    """Incremental flow short-circuits when there are no changed files."""

    async def test_no_changes_short_circuit(self, prefect_harness):
        """Empty diff from compare_commits completes immediately with no_changes=True."""
        repository = _make_repository()
        job = _make_job(mode="incremental")
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(return_value=[])
        mock_provider.clone_repository = AsyncMock(return_value=(REPO_PATH, COMMIT_SHA))

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.discover_autodoc_configs",
                new_callable=AsyncMock,
            ) as mock_discover,
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Job should be COMPLETED
        completed_calls = [
            c for c in mock_job_repo.update_status.call_args_list
            if len(c.args) >= 2 and c.args[1] == "COMPLETED"
        ]
        assert len(completed_calls) >= 1

        # quality_report should have no_changes=True
        assert job.quality_report is not None
        assert job.quality_report.get("no_changes") is True

        # Discovery should NOT run (short-circuited before discovery)
        mock_discover.assert_not_awaited()

        # Cleanup should still run
        mock_cleanup.assert_awaited_once_with(repo_path=REPO_PATH)

    async def test_no_changes_delivers_callback(self, prefect_harness):
        """When callback_url is set and no changes detected, callback is delivered."""
        callback_url = "https://example.com/hook"
        repository = _make_repository()
        job = _make_job(mode="incremental", callback_url=callback_url)
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(return_value=[])

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ) as mock_deliver,
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        mock_deliver.assert_awaited_once()
        call_kwargs = mock_deliver.call_args.kwargs
        assert call_kwargs["status"] == "COMPLETED"
        assert call_kwargs["callback_url"] == callback_url


@pytest.mark.integration
class TestIncrementalWithChanges:
    """Incremental flow processes changed files and regenerates affected pages."""

    async def test_incremental_with_changes_completes(self, prefect_harness):
        """Changed files trigger scope processing and PR creation."""
        repository = _make_repository()
        job = _make_job(mode="incremental")
        wiki_structure = _make_wiki_structure()
        wiki_pages = [_make_wiki_page(structure_id=wiki_structure.id)]

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure, wiki_pages)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(
            return_value=["src/core.py", "src/utils.py"],
        )

        # _process_incremental_scope is called internally, so we mock
        # the helper functions it depends on
        readme_result = _make_readme_result()
        page_result = _make_page_result()

        # Mock _process_incremental_scope indirectly by mocking the
        # functions it calls. Since _process_incremental_scope is defined in
        # the same module, we patch it directly.
        incremental_scope_result = {
            "structure_result": None,
            "page_results": [page_result],
            "readme_result": readme_result,
            "regenerated_page_keys": ["core-overview"],
        }

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.incremental_update._process_incremental_scope",
                new_callable=AsyncMock,
                return_value=incremental_scope_result,
            ) as mock_process_scope,
            patch(
                "src.flows.incremental_update.close_stale_autodoc_prs",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.incremental_update.create_autodoc_pr",
                new_callable=AsyncMock,
                return_value="https://github.com/org/repo/pull/43",
            ) as mock_create_pr,
            patch(
                "src.flows.incremental_update.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ) as mock_metrics,
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # _process_incremental_scope should have been called with the changed files
        mock_process_scope.assert_awaited_once()
        scope_kwargs = mock_process_scope.call_args.kwargs
        assert scope_kwargs["changed_files_set"] == {"src/core.py", "src/utils.py"}

        # PR should have been created
        mock_create_pr.assert_awaited_once()

        # Metrics should have been aggregated
        mock_metrics.assert_awaited_once()

        # Final status should be COMPLETED
        completed_calls = [
            c for c in mock_job_repo.update_status.call_args_list
            if len(c.args) >= 2 and c.args[1] == "COMPLETED"
        ]
        assert len(completed_calls) >= 1

    async def test_incremental_structural_changes_detected(self, prefect_harness):
        """When __init__.py changes, needs_structure_reextraction is True."""
        repository = _make_repository()
        job = _make_job(mode="incremental")
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(
            return_value=["src/__init__.py", "src/new_module.py"],
        )

        incremental_scope_result = {
            "structure_result": _make_structure_result(),
            "page_results": [],
            "readme_result": _make_readme_result(),
            "regenerated_page_keys": [],
        }

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.incremental_update._process_incremental_scope",
                new_callable=AsyncMock,
                return_value=incremental_scope_result,
            ) as mock_process_scope,
            patch(
                "src.flows.incremental_update.close_stale_autodoc_prs",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.incremental_update.create_autodoc_pr",
                new_callable=AsyncMock,
                return_value="https://github.com/org/repo/pull/44",
            ),
            patch(
                "src.flows.incremental_update.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ),
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # needs_structure_reextraction should be True due to __init__.py
        scope_kwargs = mock_process_scope.call_args.kwargs
        assert scope_kwargs["needs_structure_reextraction"] is True


@pytest.mark.integration
class TestIncrementalDryRun:
    """Incremental dry_run mode skips PR, page generation, and sessions."""

    async def test_incremental_dry_run(self, prefect_harness):
        """With dry_run=True on incremental flow, no PR is created."""
        repository = _make_repository()
        job = _make_job(mode="incremental", dry_run=True)
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(
            return_value=["src/core.py"],
        )

        incremental_scope_result = {
            "structure_result": None,
            "page_results": [],
            "readme_result": None,
            "regenerated_page_keys": [],
        }

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=[_make_config()],
            ),
            patch(
                "src.flows.incremental_update._process_incremental_scope",
                new_callable=AsyncMock,
                return_value=incremental_scope_result,
            ),
            patch(
                "src.flows.incremental_update.close_stale_autodoc_prs",
                new_callable=AsyncMock,
            ) as mock_close_prs,
            patch(
                "src.flows.incremental_update.create_autodoc_pr",
                new_callable=AsyncMock,
            ) as mock_create_pr,
            patch(
                "src.flows.incremental_update.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ),
            patch(
                "src.flows.incremental_update.archive_sessions",
                new_callable=AsyncMock,
            ) as mock_archive,
            patch(
                "src.flows.incremental_update.delete_sessions",
                new_callable=AsyncMock,
            ) as mock_delete_sessions,
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=True,
            )

        # PR should be skipped (no readme results -> no scope_readmes)
        mock_create_pr.assert_not_awaited()
        mock_close_prs.assert_not_awaited()
        # Session archival should be skipped
        mock_archive.assert_not_awaited()
        mock_delete_sessions.assert_not_awaited()


@pytest.mark.integration
class TestIncrementalErrorHandling:
    """Incremental flow handles errors gracefully."""

    async def test_no_baseline_sha_marks_failed(self, prefect_harness):
        """When no prior wiki structures exist, the flow raises PermanentError -> FAILED."""
        repository = _make_repository()
        job = _make_job(mode="incremental")

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository)
        )
        # No baseline SHA available
        mock_wiki_repo.get_baseline_sha = AsyncMock(return_value=None)

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Job should be FAILED with a message about no prior structures
        failed_calls = [
            c for c in mock_job_repo.update_status.call_args_list
            if len(c.args) >= 2 and c.args[1] == "FAILED"
        ]
        assert len(failed_calls) >= 1
        error_msg = failed_calls[0].kwargs.get("error_message", "")
        assert "No existing wiki structures" in error_msg or "PermanentError" in error_msg

    async def test_provider_compare_failure_marks_failed(self, prefect_harness):
        """If the provider compare_commits call fails, job is FAILED."""
        repository = _make_repository()
        job = _make_job(mode="incremental")
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(
            side_effect=RuntimeError("Provider API error"),
        )

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Job should be FAILED
        failed_calls = [
            c for c in mock_job_repo.update_status.call_args_list
            if len(c.args) >= 2 and c.args[1] == "FAILED"
        ]
        assert len(failed_calls) >= 1
        error_msg = failed_calls[0].kwargs.get("error_message", "")
        assert "Provider API error" in error_msg

        # Cleanup should still run (repo was cloned before failure)
        mock_cleanup.assert_awaited_once_with(repo_path=REPO_PATH)


# ---------------------------------------------------------------------------
# Tests — Structural change detection helper
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDetectStructuralChanges:
    """Tests for the _detect_structural_changes helper function."""

    def test_init_py_is_structural(self):
        from src.flows.incremental_update import _detect_structural_changes

        assert _detect_structural_changes(["src/models/__init__.py"]) is True

    def test_autodoc_yaml_is_structural(self):
        from src.flows.incremental_update import _detect_structural_changes

        assert _detect_structural_changes(["packages/auth/.autodoc.yaml"]) is True

    def test_pyproject_toml_is_structural(self):
        from src.flows.incremental_update import _detect_structural_changes

        assert _detect_structural_changes(["pyproject.toml"]) is True

    def test_regular_py_file_not_structural(self):
        from src.flows.incremental_update import _detect_structural_changes

        assert _detect_structural_changes(["src/utils.py", "src/core.py"]) is False

    def test_mixed_files_structural_if_any_match(self):
        from src.flows.incremental_update import _detect_structural_changes

        assert _detect_structural_changes(
            ["src/utils.py", "src/newpkg/__init__.py"]
        ) is True

    def test_empty_list(self):
        from src.flows.incremental_update import _detect_structural_changes

        assert _detect_structural_changes([]) is False


# ---------------------------------------------------------------------------
# Tests — Pages needing regeneration helper
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPagesNeedingRegeneration:
    """Tests for the _pages_needing_regeneration helper function."""

    def test_partitions_correctly(self):
        from src.flows.incremental_update import _pages_needing_regeneration

        page_specs = [
            PageSpec(
                page_key="core",
                title="Core",
                description="Core module",
                importance="high",
                page_type="overview",
                source_files=["src/core.py"],
            ),
            PageSpec(
                page_key="utils",
                title="Utils",
                description="Utility module",
                importance="medium",
                page_type="module",
                source_files=["src/utils.py"],
            ),
            PageSpec(
                page_key="config",
                title="Config",
                description="Configuration",
                importance="low",
                page_type="module",
                source_files=["src/config.py"],
            ),
        ]

        affected, unchanged = _pages_needing_regeneration(
            page_specs, {"src/core.py", "src/config.py"}
        )

        assert len(affected) == 2
        affected_keys = {s.page_key for s in affected}
        assert affected_keys == {"core", "config"}

        assert len(unchanged) == 1
        assert unchanged[0].page_key == "utils"

    def test_no_overlap_returns_all_unchanged(self):
        from src.flows.incremental_update import _pages_needing_regeneration

        page_specs = [
            PageSpec(
                page_key="core",
                title="Core",
                description="",
                importance="high",
                page_type="overview",
                source_files=["src/core.py"],
            ),
        ]

        affected, unchanged = _pages_needing_regeneration(
            page_specs, {"src/unrelated.py"}
        )

        assert len(affected) == 0
        assert len(unchanged) == 1

    def test_all_overlap_returns_all_affected(self):
        from src.flows.incremental_update import _pages_needing_regeneration

        page_specs = [
            PageSpec(
                page_key="core",
                title="Core",
                description="",
                importance="high",
                page_type="overview",
                source_files=["src/core.py"],
            ),
        ]

        affected, unchanged = _pages_needing_regeneration(
            page_specs, {"src/core.py"}
        )

        assert len(affected) == 1
        assert len(unchanged) == 0


# ---------------------------------------------------------------------------
# Tests — Cleanup always runs
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCleanupAlwaysRuns:
    """Workspace cleanup runs even when the flow fails."""

    async def test_full_generation_cleans_up_on_exception(self, prefect_harness):
        """Cleanup runs in the finally block even when an exception occurs after cloning."""
        repository = _make_repository()
        job = _make_job()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository)
        )

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Config discovery crashed"),
            ),
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # Cleanup should have been called with the repo_path
        mock_cleanup.assert_awaited_once_with(repo_path=REPO_PATH)

    async def test_incremental_cleans_up_on_exception(self, prefect_harness):
        """Incremental flow cleanup runs even after provider compare failure."""
        repository = _make_repository()
        job = _make_job(mode="incremental")
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        mock_provider = AsyncMock()
        mock_provider.compare_commits = AsyncMock(
            side_effect=RuntimeError("Compare API broke"),
        )

        with (
            patch("src.flows.incremental_update.get_session_factory", return_value=session_factory),
            patch("src.flows.incremental_update.JobRepo", return_value=mock_job_repo),
            patch("src.flows.incremental_update.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.incremental_update.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.incremental_update.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.incremental_update.get_provider",
                return_value=mock_provider,
            ),
            patch(
                "src.flows.incremental_update.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
            patch(
                "src.flows.incremental_update.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.incremental_update import incremental_update_flow

            await incremental_update_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        mock_cleanup.assert_awaited_once_with(repo_path=REPO_PATH)


# ---------------------------------------------------------------------------
# Tests — Multiple scopes
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestMultipleScopeProcessing:
    """Full generation with multiple autodoc configs (monorepo)."""

    async def test_multiple_scopes_processed_in_parallel(self, prefect_harness):
        """Multiple configs are processed, results from all scopes aggregated."""
        repository = _make_repository()
        job = _make_job()
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        configs = [
            _make_config(scope_path="."),
            _make_config(scope_path="packages/auth"),
        ]

        scope_result_root = {
            "structure_result": _make_structure_result(),
            "page_results": [_make_page_result("root-overview")],
            "readme_result": _make_readme_result(),
            "wiki_structure_id": uuid.uuid4(),
            "embedding_count": 3,
        }
        scope_result_auth = {
            "structure_result": _make_structure_result(),
            "page_results": [_make_page_result("auth-overview")],
            "readme_result": _make_readme_result(),
            "wiki_structure_id": uuid.uuid4(),
            "embedding_count": 2,
        }

        call_count = 0

        async def _scope_processing_side_effect(**kwargs):
            nonlocal call_count
            result = scope_result_root if call_count == 0 else scope_result_auth
            call_count += 1
            return result

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=configs,
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                side_effect=_scope_processing_side_effect,
            ) as mock_scope_flow,
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.full_generation.create_autodoc_pr",
                new_callable=AsyncMock,
                return_value="https://github.com/org/repo/pull/45",
            ) as mock_create_pr,
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ) as mock_metrics,
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # scope_processing_flow should have been called for each config
        assert mock_scope_flow.await_count == 2

        # PR should be created with scope_readmes from both scopes
        mock_create_pr.assert_awaited_once()
        pr_kwargs = mock_create_pr.call_args.kwargs
        assert len(pr_kwargs["scope_readmes"]) == 2

        # Metrics should receive page results from both scopes
        mock_metrics.assert_awaited_once()
        metrics_kwargs = mock_metrics.call_args.kwargs
        assert len(metrics_kwargs["page_results"]) == 2

    async def test_one_scope_failure_does_not_block_others(self, prefect_harness):
        """If one scope raises an exception, the other scope's results are still used."""
        repository = _make_repository()
        job = _make_job()
        wiki_structure = _make_wiki_structure()

        session_factory, mock_job_repo, mock_repo_repo, mock_wiki_repo, _mock_session = (
            _build_mock_session_factory(job, repository, wiki_structure)
        )

        configs = [
            _make_config(scope_path="."),
            _make_config(scope_path="packages/broken"),
        ]

        scope_result_ok = {
            "structure_result": _make_structure_result(),
            "page_results": [_make_page_result()],
            "readme_result": _make_readme_result(),
            "wiki_structure_id": uuid.uuid4(),
            "embedding_count": 3,
        }

        call_count = 0

        async def _scope_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Scope processing crashed")
            return scope_result_ok

        with (
            patch("src.flows.full_generation.get_session_factory", return_value=session_factory),
            patch("src.flows.full_generation.JobRepo", return_value=mock_job_repo),
            patch("src.flows.full_generation.RepositoryRepo", return_value=mock_repo_repo),
            patch("src.flows.full_generation.WikiRepo", return_value=mock_wiki_repo),
            patch(
                "src.flows.full_generation.clone_repository",
                new_callable=AsyncMock,
                return_value=(REPO_PATH, COMMIT_SHA),
            ),
            patch(
                "src.flows.full_generation.discover_autodoc_configs",
                new_callable=AsyncMock,
                return_value=configs,
            ),
            patch(
                "src.flows.full_generation.scope_processing_flow",
                new_callable=AsyncMock,
                side_effect=_scope_side_effect,
            ),
            patch(
                "src.flows.full_generation.close_stale_autodoc_prs",
                new_callable=AsyncMock,
                return_value=0,
            ),
            patch(
                "src.flows.full_generation.create_autodoc_pr",
                new_callable=AsyncMock,
                return_value="https://github.com/org/repo/pull/46",
            ) as mock_create_pr,
            patch(
                "src.flows.full_generation.aggregate_job_metrics",
                new_callable=AsyncMock,
                return_value={"overall_score": 8.0},
            ) as mock_metrics,
            patch(
                "src.flows.full_generation.cleanup_workspace",
                new_callable=AsyncMock,
            ),
            patch(
                "src.flows.full_generation.deliver_callback",
                new_callable=AsyncMock,
            ),
        ):
            from src.flows.full_generation import full_generation_flow

            await full_generation_flow(
                repository_id=REPO_ID,
                job_id=JOB_ID,
                branch=BRANCH,
                dry_run=False,
            )

        # PR should be created with only the successful scope's README
        mock_create_pr.assert_awaited_once()
        pr_kwargs = mock_create_pr.call_args.kwargs
        assert len(pr_kwargs["scope_readmes"]) == 1

        # Metrics should still aggregate the successful scope's results
        mock_metrics.assert_awaited_once()
        metrics_kwargs = mock_metrics.call_args.kwargs
        assert len(metrics_kwargs["page_results"]) == 1
