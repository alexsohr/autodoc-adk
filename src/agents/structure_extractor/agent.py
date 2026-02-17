from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.agents import LlmAgent

from src.agents.base import BaseAgent
from src.agents.common.agent_result import AgentResult
from src.agents.common.evaluation import EvaluationResult
from src.agents.common.loop import QualityLoopConfig, run_quality_loop
from src.agents.common.mcp_tools import create_filesystem_toolset
from src.agents.structure_extractor.prompts import (
    STRUCTURE_CRITIC_SYSTEM_PROMPT,
    STRUCTURE_GENERATOR_SYSTEM_PROMPT,
    build_generator_message,
)
from src.agents.structure_extractor.schemas import (
    PageSpec,
    SectionSpec,
    StructureExtractorInput,
    WikiStructureSpec,
)
from src.config.models import get_model
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _parse_structure_output(raw: str) -> WikiStructureSpec:
    """Parse generator's raw JSON text into a WikiStructureSpec."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    data = json.loads(text)

    def _parse_section(s: dict) -> SectionSpec:
        pages = [PageSpec(**p) for p in s.get("pages", [])]
        subsections = [_parse_section(sub) for sub in s.get("subsections", [])]
        return SectionSpec(
            title=s["title"],
            description=s.get("description", ""),
            pages=pages,
            subsections=subsections,
        )

    sections = [_parse_section(s) for s in data.get("sections", [])]
    return WikiStructureSpec(
        title=data["title"],
        description=data["description"],
        sections=sections,
    )


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


class StructureExtractor(BaseAgent[WikiStructureSpec]):
    """Extracts wiki structure from a repository using Generator + Critic loop."""

    async def run(
        self,
        input_data: Any,
        session_service: Any,
        session_id: str,
    ) -> AgentResult[WikiStructureSpec]:
        assert isinstance(input_data, StructureExtractorInput)
        settings = get_settings()

        # Create MCP tools for filesystem access
        toolset, exit_stack = await create_filesystem_toolset(input_data.repo_path)

        try:
            generator = LlmAgent(
                name="structure_generator",
                model=get_model(settings.get_agent_model("structure_generator")),
                instruction=STRUCTURE_GENERATOR_SYSTEM_PROMPT,
                tools=[toolset],
            )

            critic = LlmAgent(
                name="structure_critic",
                model=get_model(settings.get_agent_model("structure_critic")),
                instruction=STRUCTURE_CRITIC_SYSTEM_PROMPT,
            )

            config = QualityLoopConfig(
                quality_threshold=settings.QUALITY_THRESHOLD,
                max_attempts=settings.MAX_AGENT_ATTEMPTS,
                criterion_floors={
                    "coverage": settings.STRUCTURE_COVERAGE_CRITERION_FLOOR,
                },
            )

            result = await run_quality_loop(
                generator=generator,
                critic=critic,
                config=config,
                session_service=session_service,
                session_id=session_id,
                user_id=session_id,
                app_name="autodoc-structure-extractor",
                initial_message=build_generator_message(
                    input_data.file_list,
                    input_data.custom_instructions,
                ),
                parse_output=_parse_structure_output,
                parse_evaluation=_parse_evaluation,
            )

            return result
        finally:
            await exit_stack.aclose()
