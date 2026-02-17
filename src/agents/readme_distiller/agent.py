from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.agents import LlmAgent

from src.agents.base import BaseAgent
from src.agents.common.agent_result import AgentResult
from src.agents.common.evaluation import EvaluationResult
from src.agents.common.loop import QualityLoopConfig, run_quality_loop
from src.agents.readme_distiller.prompts import (
    README_CRITIC_SYSTEM_PROMPT,
    README_GENERATOR_SYSTEM_PROMPT,
    build_generator_message,
)
from src.agents.readme_distiller.schemas import (
    ReadmeDistillerInput,
    ReadmeOutput,
)
from src.config.models import get_model
from src.config.settings import get_settings

logger = logging.getLogger(__name__)


def _parse_readme_output(raw: str) -> ReadmeOutput:
    """Parse generator's raw markdown output into a ReadmeOutput."""
    content = raw.strip()
    return ReadmeOutput(content=content)


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


class ReadmeDistiller(BaseAgent[ReadmeOutput]):
    """Distills wiki pages into a README using Generator + Critic loop.

    Unlike StructureExtractor and PageGenerator, this agent does NOT use
    filesystem MCP tools. It works entirely from wiki page content passed
    in the input.
    """

    async def run(
        self,
        input_data: Any,
        session_service: Any,
        session_id: str,
    ) -> AgentResult[ReadmeOutput]:
        assert isinstance(input_data, ReadmeDistillerInput)
        settings = get_settings()

        generator = LlmAgent(
            name="readme_generator",
            model=get_model(settings.get_agent_model("readme_generator")),
            instruction=README_GENERATOR_SYSTEM_PROMPT,
        )

        critic = LlmAgent(
            name="readme_critic",
            model=get_model(settings.get_agent_model("readme_critic")),
            instruction=README_CRITIC_SYSTEM_PROMPT,
        )

        config = QualityLoopConfig(
            quality_threshold=settings.QUALITY_THRESHOLD,
            max_attempts=settings.MAX_AGENT_ATTEMPTS,
            criterion_floors={},
        )

        result = await run_quality_loop(
            generator=generator,
            critic=critic,
            config=config,
            session_service=session_service,
            session_id=session_id,
            user_id=session_id,
            app_name="autodoc-readme-distiller",
            initial_message=build_generator_message(
                wiki_pages=input_data.wiki_pages,
                project_title=input_data.project_title,
                project_description=input_data.project_description,
                custom_instructions=input_data.custom_instructions,
                max_length=input_data.max_length,
                include_toc=input_data.include_toc,
                include_badges=input_data.include_badges,
            ),
            parse_output=_parse_readme_output,
            parse_evaluation=_parse_evaluation,
        )

        return result
