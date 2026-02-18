from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.page_generator import (
    PageGenerator,
    PageGeneratorInput,
)
from src.agents.structure_extractor.schemas import PageSpec, SectionSpec
from src.config.settings import get_settings
from src.database.models.wiki_page import WikiPage
from src.flows.schemas import PageTaskResult, StructureTaskResult, TokenUsageResult
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


def _collect_page_specs(sections: list[SectionSpec]) -> list[PageSpec]:
    """Recursively collect all PageSpecs from nested sections."""
    pages: list[PageSpec] = []
    for section in sections:
        pages.extend(section.pages)
        pages.extend(_collect_page_specs(section.subsections))
    return pages


def _reconstruct_page_specs(sections_json: list[dict]) -> list[PageSpec]:
    """Reconstruct PageSpec list from sections JSONB."""
    specs: list[PageSpec] = []
    for section in sections_json:
        for page in section.get("pages", []):
            specs.append(
                PageSpec(
                    page_key=page["page_key"],
                    title=page["title"],
                    description=page.get("description", ""),
                    importance=page.get("importance", "medium"),
                    page_type=page.get("page_type", "overview"),
                    source_files=page.get("source_files", []),
                    related_pages=page.get("related_pages", []),
                )
            )
        for sub in section.get("subsections", []):
            specs.extend(_reconstruct_page_specs([sub]))
    return specs


@task(name="generate_pages", timeout_seconds=1800)
async def generate_pages(
    *,
    job_id: uuid.UUID,
    wiki_structure_id: uuid.UUID,
    structure_result: StructureTaskResult,
    repo_path: str,
    config: AutodocConfig,
) -> list[PageTaskResult]:
    """Generate wiki pages for all page specs in the structure.

    Iterates page specs from sections JSON, runs PageGenerator agent
    for each page. Each WikiPage is saved atomically (partial results
    persist on failure).

    All parameters are JSON-serializable for cross-process execution.

    Returns:
        List of PageTaskResult with serializable page results.
    """
    settings = get_settings()

    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    page_specs = _reconstruct_page_specs(structure_result.sections_json or [])
    results: list[PageTaskResult] = []

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
            style_audience=config.style.audience,
            style_tone=config.style.tone,
            style_detail_level=config.style.detail_level,
        )

        try:
            result = await agent.run(
                input_data=input_data,
                session_service=session_service,
                session_id=session_id,
            )

            # Save page to DB atomically with own session
            if result.output is not None:
                from src.database.engine import get_session_factory
                from src.database.repos.wiki_repo import WikiRepo

                session_factory = get_session_factory()
                async with session_factory() as session:
                    wiki_repo = WikiRepo(session)
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
                    await session.commit()

                logger.info(
                    "Generated page '%s' (score=%.2f, attempts=%d)",
                    page_spec.page_key,
                    result.final_score,
                    result.attempts,
                )

            results.append(PageTaskResult(
                page_key=result.output.page_key if result.output else page_spec.page_key,
                final_score=result.final_score,
                passed_quality_gate=result.passed_quality_gate,
                below_minimum_floor=result.below_minimum_floor,
                attempts=result.attempts,
                token_usage=TokenUsageResult(
                    input_tokens=result.token_usage.input_tokens,
                    output_tokens=result.token_usage.output_tokens,
                    total_tokens=result.token_usage.total_tokens,
                    calls=result.token_usage.calls,
                ),
            ))
        except Exception:
            logger.exception("Failed to generate page '%s'", page_spec.page_key)
            # Continue with remaining pages — partial results persist
            continue

    return results
