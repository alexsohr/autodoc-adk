"""Integration tests for documentation agents.

These tests verify that each agent (StructureExtractor, PageGenerator,
ReadmeDistiller) can run through the full quality-loop pipeline and produce
valid AgentResult output with quality scoring.

LLM calls are mocked via ``Runner.run_async`` so no real API calls are made,
but the complete agent wiring -- prompt construction, parsing, critic
evaluation, best-attempt tracking, and quality-gate logic -- is exercised
end-to-end.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.common.agent_result import AgentResult, TokenUsage
from src.agents.common.evaluation import EvaluationResult
from src.agents.common.loop import QualityLoopConfig, _check_below_floor, run_quality_loop
from src.agents.page_generator.schemas import GeneratedPage, PageGeneratorInput
from src.agents.readme_distiller.schemas import ReadmeDistillerInput, ReadmeOutput
from src.agents.structure_extractor.schemas import (
    StructureExtractorInput,
    WikiStructureSpec,
)

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Fake ADK event used by all tests
# ---------------------------------------------------------------------------


@dataclass
class _FakeUsageMetadata:
    promptTokenCount: int = 100  # noqa: N815
    candidatesTokenCount: int = 50  # noqa: N815
    totalTokenCount: int = 150  # noqa: N815


@dataclass
class _FakePart:
    text: str | None = None


@dataclass
class _FakeContent:
    parts: list[_FakePart]
    role: str = "model"


@dataclass
class _FakeEvent:
    """Minimal ADK event returned by Runner.run_async."""

    author: str
    content: _FakeContent | None = None
    usageMetadata: _FakeUsageMetadata | None = None  # noqa: N815


def _make_event(author: str, text: str) -> _FakeEvent:
    """Create a fake ADK event carrying *text* from *author*."""
    return _FakeEvent(
        author=author,
        content=_FakeContent(parts=[_FakePart(text=text)]),
        usageMetadata=_FakeUsageMetadata(),
    )


# ---------------------------------------------------------------------------
# Helper: build a valid critic JSON response
# ---------------------------------------------------------------------------

def _critic_json(
    score: float,
    *,
    passed: bool | None = None,
    feedback: str = "Looks good.",
    criteria_scores: dict[str, float] | None = None,
    criteria_weights: dict[str, float] | None = None,
) -> str:
    if passed is None:
        passed = score >= 7.0
    data: dict[str, Any] = {
        "score": score,
        "passed": passed,
        "feedback": feedback,
    }
    if criteria_scores is not None:
        data["criteria_scores"] = criteria_scores
    if criteria_weights is not None:
        data["criteria_weights"] = criteria_weights
    return json.dumps(data)


# ---------------------------------------------------------------------------
# Helper: valid generator JSON for StructureExtractor
# ---------------------------------------------------------------------------

_VALID_STRUCTURE_JSON = json.dumps(
    {
        "title": "Test Project",
        "description": "A test project for integration tests.",
        "sections": [
            {
                "title": "Getting Started",
                "description": "Setup and installation",
                "pages": [
                    {
                        "page_key": "installation",
                        "title": "Installation",
                        "description": "How to install the project",
                        "importance": "high",
                        "page_type": "overview",
                        "source_files": ["README.md"],
                        "related_pages": [],
                    }
                ],
                "subsections": [],
            }
        ],
    }
)

# ---------------------------------------------------------------------------
# Helper: valid generator markdown for PageGenerator
# ---------------------------------------------------------------------------

_VALID_PAGE_MARKDOWN = """\
# Authentication API

## Overview
This module provides JWT-based authentication for the REST API.

## Endpoints

### POST /auth/login
Authenticates a user and returns a JWT token.

```python
def login(username: str, password: str) -> Token:
    ...
```

## Parameters
| Name     | Type | Required |
|----------|------|----------|
| username | str  | Yes      |
| password | str  | Yes      |
"""

# ---------------------------------------------------------------------------
# Helper: valid generator markdown for ReadmeDistiller
# ---------------------------------------------------------------------------

_VALID_README_MARKDOWN = """\
# My Project

A powerful tool for automated documentation generation.

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)

## Overview
My Project generates documentation automatically from source code.

## Installation
```bash
pip install my-project
```
"""

# ---------------------------------------------------------------------------
# Fixtures: mock settings and model factory
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_settings():
    """Provide deterministic settings for all tests."""
    mock = MagicMock()
    mock.QUALITY_THRESHOLD = 7.0
    mock.MAX_AGENT_ATTEMPTS = 3
    mock.STRUCTURE_COVERAGE_CRITERION_FLOOR = 5.0
    mock.PAGE_ACCURACY_CRITERION_FLOOR = 5.0
    mock.get_agent_model.return_value = "gemini-2.5-flash"
    with patch("src.agents.structure_extractor.agent.get_settings", return_value=mock), \
         patch("src.agents.page_generator.agent.get_settings", return_value=mock), \
         patch("src.agents.readme_distiller.agent.get_settings", return_value=mock):
        yield mock


@pytest.fixture(autouse=True)
def _mock_get_model():
    """Stub out get_model so no real model client is created."""
    with patch("src.agents.structure_extractor.agent.get_model", return_value="gemini-2.5-flash"), \
         patch("src.agents.page_generator.agent.get_model", return_value="gemini-2.5-flash"), \
         patch("src.agents.readme_distiller.agent.get_model", return_value="gemini-2.5-flash"):
        yield


@pytest.fixture(autouse=True)
def _mock_filesystem_toolset():
    """Stub out create_filesystem_toolset to avoid spawning npx."""

    async def _fake_create(repo_path: str):
        toolset = MagicMock()
        exit_stack = AsyncExitStack()
        return toolset, exit_stack

    with patch(
        "src.agents.structure_extractor.agent.create_filesystem_toolset",
        side_effect=_fake_create,
    ), patch(
        "src.agents.page_generator.agent.create_filesystem_toolset",
        side_effect=_fake_create,
    ):
        yield


# ---------------------------------------------------------------------------
# Fixture: mock session service
# ---------------------------------------------------------------------------


@pytest.fixture()
def session_service():
    """A mock DatabaseSessionService that records create_session calls."""
    svc = AsyncMock()
    svc.create_session = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# Helper: patch Runner.run_async to return scripted events
# ---------------------------------------------------------------------------


def _patch_runner(call_sequence: list[list[_FakeEvent]]):
    """Return a context-manager that patches ``Runner.run_async``.

    Each call to ``run_async`` pops the first item from *call_sequence* and
    yields those events.  This allows scripting alternating generator / critic
    responses across multiple attempts.
    """
    seq = list(call_sequence)

    async def _fake_run_async(self, *, user_id, session_id, new_message):
        events = seq.pop(0)
        for e in events:
            yield e

    return patch("src.agents.common.loop.Runner.run_async", _fake_run_async)


# ===================================================================
# Tests for run_quality_loop directly (shared across agents)
# ===================================================================


class TestRunQualityLoopDirect:
    """Test the quality loop engine with minimal mocks (no agent classes)."""

    @staticmethod
    def _simple_parse_output(raw: str) -> str:
        return raw.strip()

    @staticmethod
    def _simple_parse_evaluation(raw: str) -> EvaluationResult:
        data = json.loads(raw)
        return EvaluationResult(
            score=data["score"],
            passed=data.get("passed", False),
            feedback=data.get("feedback", ""),
            criteria_scores=data.get("criteria_scores", {}),
            criteria_weights=data.get("criteria_weights", {}),
        )

    async def test_single_attempt_passes(self, session_service):
        """Generator produces valid output, critic scores above threshold."""
        gen_event = _make_event("gen", "Hello World")
        critic_event = _make_event("critic", _critic_json(8.5))

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        config = QualityLoopConfig(quality_threshold=7.0, max_attempts=3)

        with _patch_runner([[gen_event], [critic_event]]):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-sess",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        assert result.output == "Hello World"
        assert result.attempts == 1
        assert result.final_score == 8.5
        assert result.passed_quality_gate is True
        assert result.below_minimum_floor is False
        assert len(result.evaluation_history) == 1
        assert result.token_usage.total_tokens > 0

    async def test_retry_until_pass(self, session_service):
        """First attempt fails quality gate, second attempt passes."""
        gen1 = _make_event("gen", "attempt-1-output")
        critic1 = _make_event("critic", _critic_json(5.0, feedback="Needs improvement."))
        gen2 = _make_event("gen", "attempt-2-output")
        critic2 = _make_event("critic", _critic_json(8.0, feedback="Good."))

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        config = QualityLoopConfig(quality_threshold=7.0, max_attempts=3)

        with _patch_runner([[gen1], [critic1], [gen2], [critic2]]):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-retry",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        assert result.attempts == 2
        assert result.output == "attempt-2-output"
        assert result.final_score == 8.0
        assert result.passed_quality_gate is True
        assert len(result.evaluation_history) == 2

    async def test_all_attempts_fail_returns_best(self, session_service):
        """All attempts fail; the best-scoring attempt is returned."""
        events = []
        scores = [4.0, 6.5, 5.0]
        for i, score in enumerate(scores, 1):
            events.append([_make_event("gen", f"output-{i}")])
            events.append([_make_event("critic", _critic_json(score))])

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        config = QualityLoopConfig(quality_threshold=7.0, max_attempts=3)

        with _patch_runner(events):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-best",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        # Best score is 6.5 from attempt 2
        assert result.output == "output-2"
        assert result.final_score == 6.5
        assert result.passed_quality_gate is False
        assert result.attempts == 3
        assert len(result.evaluation_history) == 3

    async def test_below_minimum_floor(self, session_service):
        """Criterion floor violation detected even when overall score passes."""
        critic_response = _critic_json(
            8.0,
            criteria_scores={"accuracy": 4.0, "completeness": 9.0},
            criteria_weights={"accuracy": 0.5, "completeness": 0.5},
        )
        gen_event = _make_event("gen", "output")
        critic_event = _make_event("critic", critic_response)

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        # Accuracy floor set to 5.0, but accuracy scored 4.0
        config = QualityLoopConfig(
            quality_threshold=7.0,
            max_attempts=1,
            criterion_floors={"accuracy": 5.0},
        )

        with _patch_runner([[gen_event], [critic_event]]):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-floor",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        assert result.below_minimum_floor is True
        assert result.passed_quality_gate is False
        assert result.final_score == 8.0  # overall score is fine

    async def test_critic_failure_auto_passes(self, session_service):
        """When the critic raises an exception, the attempt auto-passes."""
        gen_event = _make_event("gen", "good output")
        # Critic returns garbage that cannot be parsed as JSON
        critic_event = _make_event("critic", "THIS IS NOT JSON AT ALL")

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        config = QualityLoopConfig(quality_threshold=7.0, max_attempts=1)

        with _patch_runner([[gen_event], [critic_event]]):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-critic-fail",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        # Auto-pass with threshold score
        assert result.output == "good output"
        assert result.final_score == 7.0
        assert result.passed_quality_gate is True
        assert len(result.evaluation_history) == 1
        assert result.evaluation_history[0].feedback == "Critic evaluation failed; auto-passed."

    async def test_critic_exception_auto_passes(self, session_service):
        """When Runner.run_async itself raises during critic, auto-pass occurs."""
        gen_event = _make_event("gen", "good output")

        call_count = 0

        async def _mixed_run_async(self, *, user_id, session_id, new_message):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Generator call succeeds
                yield gen_event
            else:
                # Critic call raises
                raise RuntimeError("LLM API unavailable")

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        config = QualityLoopConfig(quality_threshold=7.0, max_attempts=1)

        with patch("src.agents.common.loop.Runner.run_async", _mixed_run_async):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-exc",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        assert result.passed_quality_gate is True
        assert result.final_score == 7.0
        assert result.evaluation_history[0].passed is True

    async def test_token_usage_accumulated(self, session_service):
        """Token usage is accumulated across generator + critic + retries."""
        gen1 = _make_event("gen", "v1")
        critic1 = _make_event("critic", _critic_json(5.0))
        gen2 = _make_event("gen", "v2")
        critic2 = _make_event("critic", _critic_json(8.0))

        gen_agent = MagicMock()
        gen_agent.name = "gen"
        critic_agent = MagicMock()
        critic_agent.name = "critic"

        config = QualityLoopConfig(quality_threshold=7.0, max_attempts=3)

        with _patch_runner([[gen1], [critic1], [gen2], [critic2]]):
            result = await run_quality_loop(
                generator=gen_agent,
                critic=critic_agent,
                config=config,
                session_service=session_service,
                session_id="test-tokens",
                user_id="test-user",
                app_name="test-app",
                initial_message="produce something",
                parse_output=self._simple_parse_output,
                parse_evaluation=self._simple_parse_evaluation,
            )

        # 4 events total (gen1, critic1, gen2, critic2), each with 150 total tokens
        assert result.token_usage.total_tokens == 600
        assert result.token_usage.input_tokens == 400
        assert result.token_usage.output_tokens == 200
        assert result.token_usage.calls == 4


# ===================================================================
# Tests for _check_below_floor utility
# ===================================================================


class TestCheckBelowFloor:
    def test_no_floors_returns_false(self):
        evaluation = EvaluationResult(score=5.0, passed=False, feedback="")
        assert _check_below_floor(evaluation, {}) is False

    def test_all_above_floor_returns_false(self):
        evaluation = EvaluationResult(
            score=8.0,
            passed=True,
            feedback="",
            criteria_scores={"accuracy": 7.0, "coverage": 6.0},
        )
        assert _check_below_floor(evaluation, {"accuracy": 5.0, "coverage": 5.0}) is False

    def test_one_below_floor_returns_true(self):
        evaluation = EvaluationResult(
            score=8.0,
            passed=True,
            feedback="",
            criteria_scores={"accuracy": 4.5, "coverage": 8.0},
        )
        assert _check_below_floor(evaluation, {"accuracy": 5.0}) is True

    def test_missing_criterion_ignored(self):
        evaluation = EvaluationResult(
            score=8.0,
            passed=True,
            feedback="",
            criteria_scores={"coverage": 8.0},
        )
        # "accuracy" floor defined but not present in scores -- should be ignored
        assert _check_below_floor(evaluation, {"accuracy": 5.0}) is False


# ===================================================================
# Tests for StructureExtractor agent
# ===================================================================


class TestStructureExtractorAgent:
    """Integration tests for StructureExtractor running through the full pipeline."""

    @staticmethod
    def _input() -> StructureExtractorInput:
        return StructureExtractorInput(
            file_list=["src/main.py", "src/utils.py", "README.md"],
            repo_path="/tmp/test-repo",
        )

    async def test_valid_output(self, session_service):
        """StructureExtractor produces a valid WikiStructureSpec."""
        gen_event = _make_event("structure_generator", _VALID_STRUCTURE_JSON)
        critic_event = _make_event(
            "structure_critic",
            _critic_json(
                8.5,
                criteria_scores={"coverage": 8.0, "organization": 9.0, "granularity": 8.0, "clarity": 9.0},
                criteria_weights={"coverage": 0.35, "organization": 0.30, "granularity": 0.20, "clarity": 0.15},
            ),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.structure_extractor.agent import StructureExtractor

            agent = StructureExtractor()
            result = await agent.run(self._input(), session_service, "se-test-1")

        assert isinstance(result, AgentResult)
        assert isinstance(result.output, WikiStructureSpec)
        assert result.output.title == "Test Project"
        assert len(result.output.sections) == 1
        assert result.output.sections[0].pages[0].page_key == "installation"
        assert result.attempts == 1
        assert result.final_score == 8.5
        assert result.passed_quality_gate is True
        assert result.below_minimum_floor is False
        assert len(result.evaluation_history) == 1
        assert result.token_usage.calls > 0

    async def test_quality_gate_pass(self, session_service):
        """Verify quality gate passes when score exceeds threshold (7.0+)."""
        gen_event = _make_event("structure_generator", _VALID_STRUCTURE_JSON)
        critic_event = _make_event(
            "structure_critic",
            _critic_json(
                7.5,
                criteria_scores={"coverage": 7.0, "organization": 8.0, "granularity": 7.5, "clarity": 7.0},
                criteria_weights={"coverage": 0.35, "organization": 0.30, "granularity": 0.20, "clarity": 0.15},
            ),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.structure_extractor.agent import StructureExtractor

            agent = StructureExtractor()
            result = await agent.run(self._input(), session_service, "se-pass")

        assert result.passed_quality_gate is True
        assert result.final_score >= 7.0

    async def test_quality_gate_fail_with_retry(self, session_service):
        """First attempt below threshold, second attempt passes."""
        gen1 = _make_event("structure_generator", _VALID_STRUCTURE_JSON)
        critic1 = _make_event(
            "structure_critic",
            _critic_json(
                5.5,
                feedback="Missing important modules. Add coverage for utils.",
                criteria_scores={"coverage": 5.5},
            ),
        )
        gen2 = _make_event("structure_generator", _VALID_STRUCTURE_JSON)
        critic2 = _make_event(
            "structure_critic",
            _critic_json(
                8.0,
                criteria_scores={"coverage": 8.0},
            ),
        )

        with _patch_runner([[gen1], [critic1], [gen2], [critic2]]):
            from src.agents.structure_extractor.agent import StructureExtractor

            agent = StructureExtractor()
            result = await agent.run(self._input(), session_service, "se-retry")

        assert result.attempts == 2
        assert result.passed_quality_gate is True
        assert result.final_score == 8.0
        assert len(result.evaluation_history) == 2
        assert result.evaluation_history[0].score == 5.5
        assert result.evaluation_history[1].score == 8.0

    async def test_below_coverage_floor(self, session_service):
        """Coverage criterion below floor (5.0) triggers below_minimum_floor."""
        # Floor violation causes the loop to retry all max_attempts (3).
        # Provide events for all 3 attempts with coverage consistently below floor.
        critic_payload = _critic_json(
            7.5,
            criteria_scores={"coverage": 4.0, "organization": 9.0, "granularity": 8.0, "clarity": 9.0},
        )
        events: list[list[_FakeEvent]] = []
        for _ in range(3):
            events.append([_make_event("structure_generator", _VALID_STRUCTURE_JSON)])
            events.append([_make_event("structure_critic", critic_payload)])

        with _patch_runner(events):
            from src.agents.structure_extractor.agent import StructureExtractor

            agent = StructureExtractor()
            result = await agent.run(self._input(), session_service, "se-floor")

        # Overall score 7.5 passes threshold, but coverage 4.0 < floor 5.0
        assert result.below_minimum_floor is True
        assert result.passed_quality_gate is False
        assert result.final_score == 7.5
        assert result.attempts == 3

    async def test_critic_failure_resilience(self, session_service):
        """Critic LLM failure auto-passes without crashing."""
        gen_event = _make_event("structure_generator", _VALID_STRUCTURE_JSON)
        # Critic returns invalid JSON
        critic_event = _make_event("structure_critic", "I cannot evaluate this properly.")

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.structure_extractor.agent import StructureExtractor

            agent = StructureExtractor()
            result = await agent.run(self._input(), session_service, "se-critic-fail")

        assert result.passed_quality_gate is True
        assert result.final_score == 7.0  # auto-pass at threshold
        assert "auto-passed" in result.evaluation_history[0].feedback

    async def test_best_attempt_tracking(self, session_service):
        """Across 3 attempts, the best-scoring attempt output is returned."""
        # Scores: 5.0, 6.5, 4.0 -- best is 6.5 from attempt 2
        structure_v2 = json.dumps({
            "title": "Better Project",
            "description": "Improved structure.",
            "sections": [
                {
                    "title": "Core",
                    "description": "Core modules",
                    "pages": [
                        {
                            "page_key": "core-module",
                            "title": "Core Module",
                            "description": "Main module",
                            "importance": "high",
                            "page_type": "module",
                            "source_files": ["src/core.py"],
                            "related_pages": [],
                        }
                    ],
                    "subsections": [],
                }
            ],
        })

        events = [
            [_make_event("structure_generator", _VALID_STRUCTURE_JSON)],
            [_make_event("structure_critic", _critic_json(5.0, criteria_scores={"coverage": 5.0}))],
            [_make_event("structure_generator", structure_v2)],
            [_make_event("structure_critic", _critic_json(6.5, criteria_scores={"coverage": 6.5}))],
            [_make_event("structure_generator", _VALID_STRUCTURE_JSON)],
            [_make_event("structure_critic", _critic_json(4.0, criteria_scores={"coverage": 4.0}))],
        ]

        with _patch_runner(events):
            from src.agents.structure_extractor.agent import StructureExtractor

            agent = StructureExtractor()
            result = await agent.run(self._input(), session_service, "se-best")

        assert result.attempts == 3
        assert result.final_score == 6.5
        assert result.output.title == "Better Project"
        assert result.passed_quality_gate is False


# ===================================================================
# Tests for PageGenerator agent
# ===================================================================


class TestPageGeneratorAgent:
    """Integration tests for PageGenerator running through the full pipeline."""

    @staticmethod
    def _input() -> PageGeneratorInput:
        return PageGeneratorInput(
            page_key="auth-api",
            title="Authentication API",
            description="JWT authentication endpoints",
            importance="high",
            page_type="api",
            source_files=["src/auth.py"],
            repo_path="/tmp/test-repo",
        )

    @pytest.fixture(autouse=True)
    def _mock_read_source_files(self):
        """Stub out _read_source_files to avoid filesystem access."""
        with patch(
            "src.agents.page_generator.agent._read_source_files",
            return_value={"src/auth.py": "def login(): pass"},
        ):
            yield

    async def test_valid_output(self, session_service):
        """PageGenerator produces a valid GeneratedPage."""
        gen_event = _make_event("page_generator", _VALID_PAGE_MARKDOWN)
        critic_event = _make_event(
            "page_critic",
            _critic_json(
                8.0,
                criteria_scores={"accuracy": 8.5, "completeness": 8.0, "clarity": 7.5, "formatting": 8.0},
                criteria_weights={"accuracy": 0.35, "completeness": 0.30, "clarity": 0.20, "formatting": 0.15},
            ),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.page_generator.agent import PageGenerator

            agent = PageGenerator()
            result = await agent.run(self._input(), session_service, "pg-test-1")

        assert isinstance(result, AgentResult)
        assert isinstance(result.output, GeneratedPage)
        assert result.output.page_key == "auth-api"
        assert result.output.title == "Authentication API"
        assert "# Authentication API" in result.output.content
        assert result.output.source_files == ["src/auth.py"]
        assert result.attempts == 1
        assert result.final_score == 8.0
        assert result.passed_quality_gate is True
        assert result.below_minimum_floor is False
        assert result.token_usage.calls > 0

    async def test_quality_gate_pass(self, session_service):
        """Quality gate passes with score above 7.0 and no floor violations."""
        gen_event = _make_event("page_generator", _VALID_PAGE_MARKDOWN)
        critic_event = _make_event(
            "page_critic",
            _critic_json(
                9.0,
                criteria_scores={"accuracy": 9.0, "completeness": 9.0, "clarity": 8.5, "formatting": 9.0},
            ),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.page_generator.agent import PageGenerator

            agent = PageGenerator()
            result = await agent.run(self._input(), session_service, "pg-pass")

        assert result.passed_quality_gate is True
        assert result.final_score >= 7.0
        assert result.below_minimum_floor is False

    async def test_quality_gate_fail_with_retry(self, session_service):
        """First attempt fails, second passes after critic feedback."""
        gen1 = _make_event("page_generator", "# Stub\nIncomplete page.")
        critic1 = _make_event(
            "page_critic",
            _critic_json(
                4.5,
                feedback="Missing code examples and parameter documentation.",
                criteria_scores={"accuracy": 5.5, "completeness": 3.0},
            ),
        )
        gen2 = _make_event("page_generator", _VALID_PAGE_MARKDOWN)
        critic2 = _make_event(
            "page_critic",
            _critic_json(
                8.0,
                criteria_scores={"accuracy": 8.0, "completeness": 8.0},
            ),
        )

        with _patch_runner([[gen1], [critic1], [gen2], [critic2]]):
            from src.agents.page_generator.agent import PageGenerator

            agent = PageGenerator()
            result = await agent.run(self._input(), session_service, "pg-retry")

        assert result.attempts == 2
        assert result.passed_quality_gate is True
        assert result.final_score == 8.0
        # Best output should be from attempt 2
        assert "# Authentication API" in result.output.content
        assert len(result.evaluation_history) == 2

    async def test_below_accuracy_floor(self, session_service):
        """Accuracy below floor (5.0) fails quality gate despite high overall score."""
        # Floor violation causes the loop to retry all max_attempts (3).
        # Provide events for all 3 attempts with accuracy consistently below floor.
        critic_payload = _critic_json(
            7.5,
            criteria_scores={"accuracy": 3.5, "completeness": 9.0, "clarity": 9.0, "formatting": 9.0},
        )
        events: list[list[_FakeEvent]] = []
        for _ in range(3):
            events.append([_make_event("page_generator", _VALID_PAGE_MARKDOWN)])
            events.append([_make_event("page_critic", critic_payload)])

        with _patch_runner(events):
            from src.agents.page_generator.agent import PageGenerator

            agent = PageGenerator()
            result = await agent.run(self._input(), session_service, "pg-floor")

        assert result.below_minimum_floor is True
        assert result.passed_quality_gate is False
        assert result.final_score == 7.5
        assert result.attempts == 3

    async def test_critic_failure_resilience(self, session_service):
        """Critic failure auto-passes the page without crashing."""
        gen_event = _make_event("page_generator", _VALID_PAGE_MARKDOWN)
        # Critic returns non-JSON garbage
        critic_event = _make_event("page_critic", "<html>500 Internal Server Error</html>")

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.page_generator.agent import PageGenerator

            agent = PageGenerator()
            result = await agent.run(self._input(), session_service, "pg-critic-fail")

        assert result.passed_quality_gate is True
        assert result.final_score == 7.0
        assert "auto-passed" in result.evaluation_history[0].feedback

    async def test_best_attempt_tracking(self, session_service):
        """Best scoring attempt is returned when all fail the quality gate."""
        events = [
            [_make_event("page_generator", "# V1\nBasic.")],
            [_make_event("page_critic", _critic_json(3.0, criteria_scores={"accuracy": 5.0}))],
            [_make_event("page_generator", _VALID_PAGE_MARKDOWN)],
            [_make_event("page_critic", _critic_json(6.8, criteria_scores={"accuracy": 7.0}))],
            [_make_event("page_generator", "# V3\nOkay.")],
            [_make_event("page_critic", _critic_json(5.5, criteria_scores={"accuracy": 6.0}))],
        ]

        with _patch_runner(events):
            from src.agents.page_generator.agent import PageGenerator

            agent = PageGenerator()
            result = await agent.run(self._input(), session_service, "pg-best")

        assert result.attempts == 3
        assert result.final_score == 6.8
        # Best attempt (score 6.8) produced _VALID_PAGE_MARKDOWN
        assert "# Authentication API" in result.output.content
        assert result.passed_quality_gate is False


# ===================================================================
# Tests for ReadmeDistiller agent
# ===================================================================


class TestReadmeDistillerAgent:
    """Integration tests for ReadmeDistiller running through the full pipeline."""

    @staticmethod
    def _input() -> ReadmeDistillerInput:
        return ReadmeDistillerInput(
            wiki_pages=[
                {
                    "page_key": "installation",
                    "title": "Installation",
                    "description": "How to install the project",
                    "content": "Run `pip install my-project`",
                },
                {
                    "page_key": "auth-api",
                    "title": "Authentication API",
                    "description": "JWT authentication endpoints",
                    "content": "POST /auth/login to authenticate.",
                },
            ],
            project_title="My Project",
            project_description="Automated documentation generator.",
        )

    async def test_valid_output(self, session_service):
        """ReadmeDistiller produces a valid ReadmeOutput."""
        gen_event = _make_event("readme_generator", _VALID_README_MARKDOWN)
        critic_event = _make_event(
            "readme_critic",
            _critic_json(
                8.0,
                criteria_scores={
                    "conciseness": 8.0,
                    "accuracy": 8.5,
                    "structure": 7.5,
                    "completeness": 8.0,
                },
                criteria_weights={
                    "conciseness": 0.30,
                    "accuracy": 0.30,
                    "structure": 0.25,
                    "completeness": 0.15,
                },
            ),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.readme_distiller.agent import ReadmeDistiller

            agent = ReadmeDistiller()
            result = await agent.run(self._input(), session_service, "rd-test-1")

        assert isinstance(result, AgentResult)
        assert isinstance(result.output, ReadmeOutput)
        assert "# My Project" in result.output.content
        assert result.attempts == 1
        assert result.final_score == 8.0
        assert result.passed_quality_gate is True
        assert result.below_minimum_floor is False
        assert len(result.evaluation_history) == 1
        assert result.token_usage.calls > 0

    async def test_quality_gate_pass(self, session_service):
        """Quality gate passes when all criteria are satisfied."""
        gen_event = _make_event("readme_generator", _VALID_README_MARKDOWN)
        critic_event = _make_event(
            "readme_critic",
            _critic_json(7.5),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.readme_distiller.agent import ReadmeDistiller

            agent = ReadmeDistiller()
            result = await agent.run(self._input(), session_service, "rd-pass")

        assert result.passed_quality_gate is True
        assert result.final_score >= 7.0

    async def test_quality_gate_fail_with_retry(self, session_service):
        """First attempt fails, second passes."""
        gen1 = _make_event("readme_generator", "# Minimal\nToo short.")
        critic1 = _make_event(
            "readme_critic",
            _critic_json(4.0, feedback="README is too short. Missing installation and usage sections."),
        )
        gen2 = _make_event("readme_generator", _VALID_README_MARKDOWN)
        critic2 = _make_event(
            "readme_critic",
            _critic_json(8.5),
        )

        with _patch_runner([[gen1], [critic1], [gen2], [critic2]]):
            from src.agents.readme_distiller.agent import ReadmeDistiller

            agent = ReadmeDistiller()
            result = await agent.run(self._input(), session_service, "rd-retry")

        assert result.attempts == 2
        assert result.passed_quality_gate is True
        assert result.final_score == 8.5
        assert "# My Project" in result.output.content
        assert len(result.evaluation_history) == 2

    async def test_no_criterion_floors_defined(self, session_service):
        """ReadmeDistiller has no criterion floors -- below_minimum_floor always False."""
        gen_event = _make_event("readme_generator", _VALID_README_MARKDOWN)
        critic_event = _make_event(
            "readme_critic",
            _critic_json(
                8.0,
                criteria_scores={"conciseness": 3.0, "accuracy": 9.0},
            ),
        )

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.readme_distiller.agent import ReadmeDistiller

            agent = ReadmeDistiller()
            result = await agent.run(self._input(), session_service, "rd-no-floor")

        # Even though conciseness is low, no floor is configured so it passes
        assert result.below_minimum_floor is False
        assert result.passed_quality_gate is True

    async def test_critic_failure_resilience(self, session_service):
        """Critic failure auto-passes without crashing."""
        gen_event = _make_event("readme_generator", _VALID_README_MARKDOWN)
        critic_event = _make_event("readme_critic", "UNPARSEABLE GARBAGE !@#$%")

        with _patch_runner([[gen_event], [critic_event]]):
            from src.agents.readme_distiller.agent import ReadmeDistiller

            agent = ReadmeDistiller()
            result = await agent.run(self._input(), session_service, "rd-critic-fail")

        assert result.passed_quality_gate is True
        assert result.final_score == 7.0
        assert "auto-passed" in result.evaluation_history[0].feedback

    async def test_best_attempt_tracking(self, session_service):
        """Best-scoring attempt is returned when gate never passes."""
        events = [
            [_make_event("readme_generator", "# V1\nShort.")],
            [_make_event("readme_critic", _critic_json(3.0))],
            [_make_event("readme_generator", _VALID_README_MARKDOWN)],
            [_make_event("readme_critic", _critic_json(6.9))],
            [_make_event("readme_generator", "# V3\nDecent but not great.")],
            [_make_event("readme_critic", _critic_json(5.5))],
        ]

        with _patch_runner(events):
            from src.agents.readme_distiller.agent import ReadmeDistiller

            agent = ReadmeDistiller()
            result = await agent.run(self._input(), session_service, "rd-best")

        assert result.attempts == 3
        assert result.final_score == 6.9
        assert "# My Project" in result.output.content
        assert result.passed_quality_gate is False
        assert len(result.evaluation_history) == 3


# ===================================================================
# Tests for AgentResult and TokenUsage dataclasses
# ===================================================================


class TestAgentResultDataclass:
    """Verify AgentResult field defaults and TokenUsage accumulation."""

    def test_default_fields(self):
        result = AgentResult(
            output="test",
            attempts=1,
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
        )
        assert result.evaluation_history == []
        assert result.token_usage.total_tokens == 0
        assert result.token_usage.calls == 0

    def test_token_usage_add(self):
        usage1 = TokenUsage(input_tokens=100, output_tokens=50, total_tokens=150, calls=1)
        usage2 = TokenUsage(input_tokens=200, output_tokens=80, total_tokens=280, calls=2)
        usage1.add(usage2)
        assert usage1.input_tokens == 300
        assert usage1.output_tokens == 130
        assert usage1.total_tokens == 430
        assert usage1.calls == 3

    def test_evaluation_history_populated(self):
        evals = [
            EvaluationResult(score=5.0, passed=False, feedback="Bad"),
            EvaluationResult(score=8.0, passed=True, feedback="Good"),
        ]
        result = AgentResult(
            output="test",
            attempts=2,
            final_score=8.0,
            passed_quality_gate=True,
            below_minimum_floor=False,
            evaluation_history=evals,
        )
        assert len(result.evaluation_history) == 2
        assert result.evaluation_history[0].score == 5.0
        assert result.evaluation_history[1].score == 8.0


# ===================================================================
# Tests for EvaluationResult dataclass
# ===================================================================


class TestEvaluationResultDataclass:
    def test_default_fields(self):
        er = EvaluationResult(score=7.5, passed=True, feedback="OK")
        assert er.criteria_scores == {}
        assert er.criteria_weights == {}

    def test_with_criteria(self):
        er = EvaluationResult(
            score=8.0,
            passed=True,
            feedback="Well done",
            criteria_scores={"accuracy": 9.0, "coverage": 7.0},
            criteria_weights={"accuracy": 0.6, "coverage": 0.4},
        )
        assert er.criteria_scores["accuracy"] == 9.0
        assert er.criteria_weights["coverage"] == 0.4
