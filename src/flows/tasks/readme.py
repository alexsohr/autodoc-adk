from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.common.agent_result import AgentResult
from src.agents.readme_distiller import (
    ReadmeDistiller,
    ReadmeDistillerInput,
    ReadmeOutput,
)
from src.agents.structure_extractor.schemas import WikiStructureSpec
from src.config.settings import get_settings
from src.database.models.wiki_page import WikiPage
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


@task(name="distill_readme", timeout_seconds=600)
async def distill_readme(
    *,
    job_id: uuid.UUID,
    structure_spec: WikiStructureSpec,
    wiki_pages: list[WikiPage],
    config: AutodocConfig,
) -> AgentResult[ReadmeOutput]:
    """Distill wiki pages into a README.

    Loads generated wiki pages into session state, runs ReadmeDistiller
    agent, returns AgentResult[ReadmeOutput] with README markdown.

    Args:
        job_id: Job UUID (used as session user_id).
        structure_spec: The wiki structure spec (for project title/description).
        wiki_pages: List of generated WikiPage ORM objects.
        config: AutodocConfig with readme settings.

    Returns:
        AgentResult[ReadmeOutput] with generated README content.
    """
    settings = get_settings()

    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    session_id = f"readme-{job_id}-{uuid.uuid4().hex[:8]}"

    # Prepare wiki page data for the agent
    pages_data = [
        {
            "page_key": page.page_key,
            "title": page.title,
            "description": page.description,
            "content": page.content,
        }
        for page in wiki_pages
    ]

    agent = ReadmeDistiller()
    input_data = ReadmeDistillerInput(
        wiki_pages=pages_data,
        project_title=structure_spec.title,
        project_description=structure_spec.description,
        custom_instructions=config.custom_instructions,
        max_length=config.readme.max_length,
        include_toc=config.readme.include_toc,
        include_badges=config.readme.include_badges,
    )

    result = await agent.run(
        input_data=input_data,
        session_service=session_service,
        session_id=session_id,
    )

    logger.info(
        "Distilled README (score=%.2f, attempts=%d, length=%d chars)",
        result.final_score,
        result.attempts,
        len(result.output.content) if result.output else 0,
    )

    return result
