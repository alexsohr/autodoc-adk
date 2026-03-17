from __future__ import annotations

import logging
import uuid

from prefect import task

from src.agents.readme_distiller import (
    ReadmeDistiller,
    ReadmeDistillerInput,
)
from src.config.settings import get_settings
from src.flows.schemas import ReadmeTaskResult, TokenUsageResult
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


@task(name="distill_readme", timeout_seconds=600)
async def distill_readme(
    *,
    job_id: uuid.UUID,
    structure_title: str,
    structure_description: str,
    page_summaries: list[dict],
    config: AutodocConfig,
) -> ReadmeTaskResult:
    """Distill wiki pages into a README.

    Accepts page summaries as dicts and a typed AutodocConfig
    for cross-process execution.

    Args:
        job_id: Job UUID (used as session user_id).
        structure_title: The wiki structure title.
        structure_description: The wiki structure description.
        page_summaries: List of dicts with keys: page_key, title, description, content.
        config: Typed AutodocConfig object.

    Returns:
        ReadmeTaskResult with README content and quality metadata.
    """
    settings = get_settings()

    db_url = settings.DATABASE_URL
    from src.services.session import SanitizedDatabaseSessionService

    session_service = SanitizedDatabaseSessionService(db_url=db_url)

    session_id = f"readme-{job_id}-{uuid.uuid4().hex[:8]}"

    agent = ReadmeDistiller()
    input_data = ReadmeDistillerInput(
        wiki_pages=page_summaries,
        project_title=structure_title,
        project_description=structure_description,
        custom_instructions=config.custom_instructions,
        max_length=config.readme.max_length,
        include_toc=config.readme.include_toc,
        include_badges=config.readme.include_badges,
        style_audience=config.style.audience,
        style_tone=config.style.tone,
        style_detail_level=config.style.detail_level,
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

    return ReadmeTaskResult(
        final_score=result.final_score,
        passed_quality_gate=result.passed_quality_gate,
        below_minimum_floor=result.below_minimum_floor,
        attempts=result.attempts,
        content=result.output.content if result.output else "",
        token_usage=TokenUsageResult(
            input_tokens=result.token_usage.input_tokens,
            output_tokens=result.token_usage.output_tokens,
            total_tokens=result.token_usage.total_tokens,
            calls=result.token_usage.calls,
        ),
    )
