from __future__ import annotations

import logging
import os
import uuid

from prefect import flow, task
from prefect.futures import wait
from prefect.task_runners import ThreadPoolTaskRunner
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.agents.page_generator import (
    PageGenerator,
    PageGeneratorInput,
)
from src.agents.structure_extractor.schemas import PageSpec, SectionSpec
from src.config.settings import get_settings
from src.database.models.wiki_page import WikiPage
from src.database.repos.wiki_repo import WikiRepo
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


@task(
    name="generate_single_page",
    task_run_name="page-{page_spec.page_key}",
    timeout_seconds=600,
)
async def generate_single_page(
    *,
    job_id: uuid.UUID,
    wiki_structure_id: uuid.UUID,
    page_spec: PageSpec,
    repo_path: str,
    config: AutodocConfig,
) -> PageTaskResult:
    """Generate a single wiki page and persist it to the database.

    Each task creates its own DatabaseSessionService because
    ThreadPoolTaskRunner runs tasks on separate threads with their own
    event loops.
    """
    settings = get_settings()
    db_url = settings.DATABASE_URL

    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

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

    result = await agent.run(
        input_data=input_data,
        session_service=session_service,
        session_id=session_id,
    )

    # Save page to DB atomically with a per-task engine.
    # ThreadPoolTaskRunner runs each task on a separate thread with its own
    # event loop, so the module-level singleton engine (bound to the parent
    # flow's loop) cannot be reused here.
    if result.output is not None:
        engine = create_async_engine(settings.DATABASE_URL, pool_size=1, max_overflow=0)
        try:
            factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with factory() as session:
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
        finally:
            await engine.dispose()

        logger.info(
            "Generated page '%s' (score=%.2f, attempts=%d)",
            page_spec.page_key,
            result.final_score,
            result.attempts,
        )

    return PageTaskResult(
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
    )


_PAGE_CONCURRENCY = int(os.environ.get("PAGE_GENERATION_CONCURRENCY", "3"))


@flow(
    name="generate_pages",
    timeout_seconds=1800,
    task_runner=ThreadPoolTaskRunner(max_workers=_PAGE_CONCURRENCY),
)
async def generate_pages(
    *,
    job_id: uuid.UUID,
    wiki_structure_id: uuid.UUID,
    structure_result: StructureTaskResult,
    repo_path: str,
    config: AutodocConfig,
) -> list[PageTaskResult]:
    """Fan-out page generation across concurrent tasks.

    Submits one ``generate_single_page`` task per page spec, waits for
    all futures, and collects results.  Failed pages are logged and
    skipped (partial results persist).

    Returns:
        List of PageTaskResult for pages that succeeded.
    """
    page_specs = _reconstruct_page_specs(structure_result.sections_json or [])

    if not page_specs:
        return []

    # Fan out
    futures = []
    for page_spec in page_specs:
        future = generate_single_page.submit(
            job_id=job_id,
            wiki_structure_id=wiki_structure_id,
            page_spec=page_spec,
            repo_path=repo_path,
            config=config,
        )
        futures.append((page_spec.page_key, future))

    # Fan in
    wait([f for _, f in futures])

    results: list[PageTaskResult] = []
    failures: list[str] = []
    for page_key, future in futures:
        try:
            results.append(future.result(raise_on_failure=True))
        except Exception:
            logger.exception("Failed to generate page '%s'", page_key)
            failures.append(page_key)
            continue

    if not results and failures:
        raise RuntimeError(
            f"All {len(failures)} page generation tasks failed: {', '.join(failures)}"
        )

    if failures:
        logger.warning(
            "%d/%d page tasks failed: %s",
            len(failures),
            len(futures),
            ", ".join(failures),
        )

    return results
