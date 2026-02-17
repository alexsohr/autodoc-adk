from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.common.agent_result import AgentResult
from src.agents.page_generator import (
    GeneratedPage,
    PageGenerator,
    PageGeneratorInput,
)
from src.agents.structure_extractor.schemas import PageSpec, SectionSpec, WikiStructureSpec
from src.config.settings import get_settings
from src.database.models.wiki_page import WikiPage
from src.database.repos.wiki_repo import WikiRepo
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


def _collect_page_specs(sections: list[SectionSpec]) -> list[PageSpec]:
    """Recursively collect all PageSpecs from nested sections."""
    pages: list[PageSpec] = []
    for section in sections:
        pages.extend(section.pages)
        pages.extend(_collect_page_specs(section.subsections))
    return pages


@task(name="generate_pages", timeout_seconds=1800)
async def generate_pages(
    *,
    job_id: uuid.UUID,
    wiki_structure_id: uuid.UUID,
    structure_spec: WikiStructureSpec,
    repo_path: str,
    config: AutodocConfig,
    wiki_repo: WikiRepo,
) -> list[AgentResult[GeneratedPage]]:
    """Generate wiki pages for all page specs in the structure.

    Iterates page specs from WikiStructureSpec, runs PageGenerator agent
    for each page. Each WikiPage is saved atomically (partial results
    persist on failure).

    Args:
        job_id: Job UUID (used as session user_id).
        wiki_structure_id: WikiStructure UUID to link pages to.
        structure_spec: The wiki structure spec with page definitions.
        repo_path: Path to cloned repository.
        config: AutodocConfig for this scope.
        wiki_repo: WikiRepo instance for DB operations.

    Returns:
        List of AgentResults, one per page.
    """
    settings = get_settings()

    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    page_specs = _collect_page_specs(structure_spec.sections)
    results: list[AgentResult[GeneratedPage]] = []

    for page_spec in page_specs:
        session_id = f"page-{job_id}-{page_spec.page_key}-{uuid.uuid4().hex[:8]}"

        agent = PageGenerator()
        input_data = PageGeneratorInput(
            page_key=page_spec.page_key,
            title=page_spec.title,
            description=page_spec.description,
            importance=page_spec.importance,
            page_type=page_spec.page_type,
            source_files=page_spec.source_files,
            repo_path=repo_path,
            related_pages=page_spec.related_pages,
            custom_instructions=config.custom_instructions,
        )

        try:
            result = await agent.run(
                input_data=input_data,
                session_service=session_service,
                session_id=session_id,
            )

            # Save page to DB atomically
            if result.output is not None:
                wiki_page = WikiPage(
                    wiki_structure_id=wiki_structure_id,
                    page_key=result.output.page_key,
                    title=result.output.title,
                    description=page_spec.description,
                    importance=page_spec.importance,
                    page_type=page_spec.page_type,
                    source_files=page_spec.source_files,
                    related_pages=page_spec.related_pages,
                    content=result.output.content,
                    quality_score=result.final_score,
                )
                await wiki_repo.create_pages([wiki_page])
                logger.info(
                    "Generated page '%s' (score=%.2f, attempts=%d)",
                    page_spec.page_key,
                    result.final_score,
                    result.attempts,
                )

            results.append(result)
        except Exception:
            logger.exception("Failed to generate page '%s'", page_spec.page_key)
            # Continue with remaining pages — partial results persist
            continue

    return results
