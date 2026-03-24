from __future__ import annotations

import hashlib
import math
import shutil
import tempfile
from unittest.mock import AsyncMock

from src.agents.common.agent_result import AgentResult, TokenUsage
from src.agents.common.evaluation import EvaluationResult
from src.agents.page_generator.schemas import GeneratedPage
from src.agents.readme_distiller.schemas import ReadmeOutput
from src.agents.structure_extractor.schemas import PageSpec, SectionSpec, WikiStructureSpec
from src.errors import PermanentError, TransientError

# ---------------------------------------------------------------------------
# 1. Structure extractor stub
# ---------------------------------------------------------------------------


def make_structure_stub(score: float = 8.2, below_floor: bool = False) -> AsyncMock:
    """Return an AsyncMock whose return_value is an AgentResult[WikiStructureSpec]."""
    structure = WikiStructureSpec(
        title="Sample Project Documentation",
        description="Documentation for the sample project",
        sections=[
            SectionSpec(
                title="Core Modules",
                description="Core modules of the project",
                pages=[
                    PageSpec(
                        page_key="core-module",
                        title="Core Module",
                        description="Documentation for the core module",
                        importance="high",
                        page_type="module",
                        source_files=["src/core.py"],
                        related_pages=["utils-module"],
                    ),
                    PageSpec(
                        page_key="utils-module",
                        title="Utility Functions",
                        description="Documentation for utility functions",
                        importance="medium",
                        page_type="module",
                        source_files=["src/utils.py"],
                        related_pages=["core-module"],
                    ),
                ],
            ),
            SectionSpec(
                title="Project Overview",
                description="High-level project overview",
                pages=[
                    PageSpec(
                        page_key="project-overview",
                        title="Project Overview",
                        description="Overview of the project",
                        importance="low",
                        page_type="overview",
                        source_files=["README.md", "pyproject.toml"],
                    ),
                ],
            ),
        ],
    )

    evaluation = EvaluationResult(
        score=score,
        passed=score >= 7.0,
        feedback="Structure looks good. Covers all major modules.",
        criteria_scores={"completeness": score, "organization": score + 0.3, "accuracy": score - 0.1},
        criteria_weights={"completeness": 0.4, "organization": 0.3, "accuracy": 0.3},
    )

    result: AgentResult[WikiStructureSpec] = AgentResult(
        output=structure,
        attempts=1,
        final_score=score,
        passed_quality_gate=score >= 7.0,
        below_minimum_floor=below_floor,
        evaluation_history=[evaluation],
        token_usage=TokenUsage(input_tokens=1500, output_tokens=800, total_tokens=2300, calls=2),
    )

    mock = AsyncMock(return_value=result)
    return mock


# ---------------------------------------------------------------------------
# 2. Page generator stub
# ---------------------------------------------------------------------------


def make_page_stub() -> AsyncMock:
    """Return an AsyncMock with a side_effect that generates pages based on input."""

    async def _side_effect(*args: object, **kwargs: object) -> AgentResult[GeneratedPage]:
        # Extract input_data from args or kwargs
        input_data = kwargs.get("input_data") or (args[0] if args else None)

        # Extract page details from the input
        page_key: str = getattr(input_data, "page_key", "unknown")
        title: str = getattr(input_data, "title", "Unknown Page")
        source_files: list[str] = getattr(input_data, "source_files", [])

        source_files_list = "\n".join(f"- `{f}`" for f in source_files) if source_files else "- None"

        content = (
            f"# {title}\n\n"
            f"Documentation for {page_key}.\n\n"
            f"## Source Files\n\n"
            f"{source_files_list}\n\n"
            f"## Details\n\n"
            f"This page covers the core functionality.\n\n"
            f"```python\n"
            f"# Example code\n"
            f"pass\n"
            f"```\n"
        )

        page = GeneratedPage(
            page_key=page_key,
            title=title,
            content=content,
            source_files=list(source_files),
        )

        evaluation = EvaluationResult(
            score=8.0,
            passed=True,
            feedback="Page content is accurate and well-structured.",
            criteria_scores={"accuracy": 8.2, "completeness": 7.8, "clarity": 8.0},
            criteria_weights={"accuracy": 0.35, "completeness": 0.35, "clarity": 0.3},
        )

        return AgentResult(
            output=page,
            attempts=1,
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            evaluation_history=[evaluation],
            token_usage=TokenUsage(input_tokens=1200, output_tokens=600, total_tokens=1800, calls=2),
        )

    mock = AsyncMock(side_effect=_side_effect)
    return mock


# ---------------------------------------------------------------------------
# 3. README distiller stub
# ---------------------------------------------------------------------------


def make_readme_stub() -> AsyncMock:
    """Return an AsyncMock whose return_value is an AgentResult[ReadmeOutput]."""
    content = (
        "# Sample Project Documentation\n\n"
        "Welcome to the Sample Project.\n\n"
        "## Contents\n\n"
        "- [Core Module](docs/core-module.md) - Core functionality\n"
        "- [Utility Functions](docs/utils-module.md) - Helper utilities\n"
        "- [Project Overview](docs/project-overview.md) - High-level overview\n\n"
        "## Getting Started\n\n"
        "See the individual module pages for detailed documentation.\n"
    )

    evaluation = EvaluationResult(
        score=7.5,
        passed=True,
        feedback="README is concise and references all pages.",
        criteria_scores={"completeness": 7.6, "clarity": 7.4, "accuracy": 7.5},
        criteria_weights={"completeness": 0.4, "clarity": 0.3, "accuracy": 0.3},
    )

    result: AgentResult[ReadmeOutput] = AgentResult(
        output=ReadmeOutput(content=content),
        attempts=1,
        final_score=7.5,
        passed_quality_gate=True,
        below_minimum_floor=False,
        evaluation_history=[evaluation],
        token_usage=TokenUsage(input_tokens=1000, output_tokens=500, total_tokens=1500, calls=2),
    )

    mock = AsyncMock(return_value=result)
    return mock


# ---------------------------------------------------------------------------
# 4. Clone repository stub
# ---------------------------------------------------------------------------


def make_clone_stub(
    fixture_path: str,
    error: TransientError | PermanentError | None = None,
) -> AsyncMock:
    """Return an AsyncMock side_effect function for clone_repository.

    If *error* is provided, the first call raises it; subsequent calls succeed.
    On success, copies *fixture_path* to a temp directory and returns (temp_path, commit_sha).
    """
    call_count = 0

    async def _side_effect(*args: object, **kwargs: object) -> tuple[str, str]:
        nonlocal call_count
        call_count += 1

        if error is not None and call_count == 1:
            raise error

        temp_dir = tempfile.mkdtemp(prefix="autodoc_e2e_clone_")
        dest = shutil.copytree(fixture_path, temp_dir, dirs_exist_ok=True)
        return (dest, "abc123fake")

    return _side_effect


# ---------------------------------------------------------------------------
# 5. Embedding stub
# ---------------------------------------------------------------------------


def make_embedding_stub() -> AsyncMock:
    """Return an AsyncMock side_effect function for embedding generation.

    Produces deterministic 1024-dim unit vectors from text content using pure Python math.
    """

    async def _side_effect(
        texts: list[str],
        *,
        model: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
    ) -> list[list[float]]:
        dim = 1024
        result: list[list[float]] = []

        for text in texts:
            digest = hashlib.sha256(text.encode()).digest()
            num_seed_bytes = len(digest)  # 32

            # Build a raw vector by cycling through the hash bytes
            raw: list[float] = []
            for i in range(dim):
                byte_val = digest[i % num_seed_bytes]
                # Spread values around zero: map [0, 255] to [-1.0, 1.0]
                raw.append((byte_val / 127.5) - 1.0)

            # Normalize to unit vector
            magnitude = math.sqrt(sum(v * v for v in raw))
            vector = [v / magnitude for v in raw] if magnitude > 0 else raw

            result.append(vector)

        return result

    return _side_effect


# ---------------------------------------------------------------------------
# 6. PR stubs
# ---------------------------------------------------------------------------


def make_pr_stub() -> tuple[AsyncMock, AsyncMock]:
    """Return (close_stale_mock, create_pr_mock) for PR-related task stubs."""
    close_stale_mock = AsyncMock(return_value=0)
    create_pr_mock = AsyncMock(return_value="https://github.com/test/sample-project/pull/999")
    return close_stale_mock, create_pr_mock


# ---------------------------------------------------------------------------
# 7. Compare commits stub
# ---------------------------------------------------------------------------


def make_compare_commits_stub(changed_files: list[str] | None = None) -> AsyncMock:
    """Return an AsyncMock whose return_value is a list of changed file paths."""
    return AsyncMock(return_value=changed_files if changed_files is not None else [])


# ---------------------------------------------------------------------------
# 8. Callback stub
# ---------------------------------------------------------------------------


def make_callback_stub() -> AsyncMock:
    """Return a no-op AsyncMock that captures all invocation arguments for assertion."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# 9. GitHub push payload
# ---------------------------------------------------------------------------


def make_github_push_payload(repo_url: str, branch: str, sha: str) -> tuple[dict[str, object], dict[str, str]]:
    """Return (payload, headers) matching a GitHub push webhook event."""
    payload: dict[str, object] = {
        "ref": f"refs/heads/{branch}",
        "after": sha,
        "repository": {
            "clone_url": repo_url,
        },
    }
    headers: dict[str, str] = {
        "X-GitHub-Event": "push",
    }
    return payload, headers


# ---------------------------------------------------------------------------
# 10. Bitbucket push payload
# ---------------------------------------------------------------------------


def make_bitbucket_push_payload(repo_url: str, branch: str, sha: str) -> tuple[dict[str, object], dict[str, str]]:
    """Return (payload, headers) matching a Bitbucket push webhook event."""
    payload: dict[str, object] = {
        "push": {
            "changes": [
                {
                    "new": {
                        "name": branch,
                        "target": {
                            "hash": sha,
                        },
                    },
                },
            ],
        },
        "repository": {
            "links": {
                "html": {
                    "href": repo_url,
                },
            },
        },
    }
    headers: dict[str, str] = {
        "X-Event-Key": "repo:push",
    }
    return payload, headers
