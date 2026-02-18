from __future__ import annotations

import json
import logging
import os
from typing import Any

from google.adk.agents import LlmAgent

from src.agents.base import BaseAgent
from src.agents.common.agent_result import AgentResult
from src.agents.common.evaluation import EvaluationResult
from src.agents.common.loop import QualityLoopConfig, run_quality_loop
from src.agents.common.mcp_tools import create_filesystem_toolset
from src.agents.page_generator.prompts import (
    PAGE_CRITIC_SYSTEM_PROMPT,
    build_generator_message,
    build_generator_system_prompt,
)
from src.agents.page_generator.schemas import (
    GeneratedPage,
    PageGeneratorInput,
)
from src.config.models import get_model
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _parse_page_output(raw: str) -> GeneratedPage:
    """Parse generator's raw markdown output into a GeneratedPage.

    The generator outputs raw Markdown content (not JSON). The page_key,
    title, and source_files are injected by the caller via a closure or
    set after parsing. Here we use a sentinel approach: the function is
    replaced by a factory in the agent's run method.
    """
    # This standalone version is never called directly; the agent builds
    # a closure that captures the input metadata. See _make_parse_output.
    raise NotImplementedError("Use _make_parse_output to create a bound parser")


def _make_parse_output(input_data: PageGeneratorInput):
    """Create a parse_output closure that captures page metadata."""

    def _parse(raw: str) -> GeneratedPage:
        content = raw.strip()
        return GeneratedPage(
            page_key=input_data.page_key,
            title=input_data.title,
            content=content,
            source_files=list(input_data.source_files),
        )

    return _parse


def _parse_evaluation(raw: str) -> EvaluationResult:
    """Parse critic's raw JSON into EvaluationResult."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    data = json.loads(text)
    return EvaluationResult(
        score=float(data["score"]),
        passed=bool(data.get("passed", False)),
        feedback=data.get("feedback", ""),
        criteria_scores=data.get("criteria_scores", {}),
        criteria_weights=data.get("criteria_weights", {}),
    )


def _read_source_files(repo_path: str, source_files: list[str]) -> dict[str, str]:
    """Read source file contents from disk for the critic's verification.

    Args:
        repo_path: Absolute path to the cloned repository.
        source_files: List of relative file paths within the repository.

    Returns:
        Mapping of file path to file content. Files that cannot be read
        are included with an error placeholder.
    """
    contents: dict[str, str] = {}
    for rel_path in source_files:
        abs_path = os.path.join(repo_path, rel_path)
        try:
            with open(abs_path, encoding="utf-8", errors="replace") as f:
                contents[rel_path] = f.read()
        except OSError:
            logger.warning("Could not read source file: %s", abs_path)
            contents[rel_path] = f"[ERROR: Could not read file {rel_path}]"
    return contents


class PageGenerator(BaseAgent[GeneratedPage]):
    """Generates a wiki page from source files using Generator + Critic loop.

    The Generator reads source files via MCP filesystem tools and produces
    Markdown documentation. The Critic receives both the generated page
    and the actual source file contents to verify accuracy.
    """

    async def run(
        self,
        input_data: Any,
        session_service: Any,
        session_id: str,
    ) -> AgentResult[GeneratedPage]:
        assert isinstance(input_data, PageGeneratorInput)
        settings = get_settings()

        # Create MCP tools for filesystem access
        toolset, exit_stack = await create_filesystem_toolset(input_data.repo_path)

        try:
            generator = LlmAgent(
                name="page_generator",
                model=get_model(settings.get_agent_model("page_generator")),
                instruction=build_generator_system_prompt(
                    audience=input_data.style_audience,
                    tone=input_data.style_tone,
                    detail_level=input_data.style_detail_level,
                    custom_instructions=input_data.custom_instructions,
                ),
                tools=[toolset],
            )

            # Read source files for the critic's verification context.
            # The critic does NOT get MCP tools - it receives source content
            # directly in its prompt to verify accuracy.
            source_contents = _read_source_files(
                input_data.repo_path, input_data.source_files
            )

            config = QualityLoopConfig(
                quality_threshold=settings.QUALITY_THRESHOLD,
                max_attempts=settings.MAX_AGENT_ATTEMPTS,
                criterion_floors={
                    "accuracy": settings.PAGE_ACCURACY_CRITERION_FLOOR,
                },
            )

            # Inject source file contents into the critic's system prompt so it
            # can verify accuracy of code references without needing MCP tools.
            source_context_block = _format_source_context(source_contents)
            critic = LlmAgent(
                name="page_critic",
                model=get_model(settings.get_agent_model("page_critic")),
                instruction=PAGE_CRITIC_SYSTEM_PROMPT + "\n\n" + source_context_block,
            )

            result = await run_quality_loop(
                generator=generator,
                critic=critic,
                config=config,
                session_service=session_service,
                session_id=session_id,
                user_id=session_id,
                app_name="autodoc-page-generator",
                initial_message=build_generator_message(
                    page_key=input_data.page_key,
                    title=input_data.title,
                    description=input_data.description,
                    importance=input_data.importance,
                    page_type=input_data.page_type,
                    source_files=input_data.source_files,
                    related_pages=input_data.related_pages,
                    custom_instructions=input_data.custom_instructions,
                ),
                parse_output=_make_parse_output(input_data),
                parse_evaluation=_parse_evaluation,
            )

            return result
        finally:
            await exit_stack.aclose()


def _format_source_context(source_contents: dict[str, str]) -> str:
    """Format source file contents for inclusion in the critic's system prompt.

    Args:
        source_contents: Mapping of file path to file content.

    Returns:
        Formatted string block with all source files.
    """
    parts = ["## Source Files for Verification\n"]
    for path, content in source_contents.items():
        parts.append(f"### {path}\n```\n{content}\n```\n")
    return "\n".join(parts)
