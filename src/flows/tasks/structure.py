from __future__ import annotations

import logging
import uuid
from dataclasses import asdict

from prefect import task

from src.agents.structure_extractor import (
    StructureExtractor,
    StructureExtractorInput,
    WikiStructureSpec,
)
from src.config.settings import get_settings
from src.flows.schemas import StructureTaskResult, TokenUsageResult
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


def _structure_spec_to_sections_json(spec: WikiStructureSpec) -> list[dict]:
    """Convert WikiStructureSpec.sections to JSON-serializable structure for DB storage."""
    return [asdict(s) for s in spec.sections]


@task(name="extract_structure", timeout_seconds=600)
async def extract_structure(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    scope_path: str,
    commit_sha: str,
    file_list: list[str],
    repo_path: str,
    config: AutodocConfig,
    readme_content: str = "",
) -> StructureTaskResult:
    """Run StructureExtractor agent and save result to database.

    Creates a DatabaseSessionService session (user_id=job_id), runs
    StructureExtractor with file list and config, saves WikiStructure
    to DB via WikiRepo (enforce version retention).

    All parameters are JSON-serializable for cross-process execution.

    Returns:
        StructureTaskResult with structure output and quality metadata.
    """
    settings = get_settings()

    # Create ADK DatabaseSessionService
    db_url = settings.DATABASE_URL

    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    session_id = f"structure-{job_id}-{scope_path}-{uuid.uuid4().hex[:8]}"

    agent = StructureExtractor()
    input_data = StructureExtractorInput(
        file_list=file_list,
        repo_path=repo_path,
        readme_content=readme_content,
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

    sections_json = None
    if result.output is not None:
        sections_json = _structure_spec_to_sections_json(result.output)

        # Save to database with own session
        from src.database.engine import get_session_factory
        from src.database.repos.wiki_repo import WikiRepo

        session_factory = get_session_factory()
        async with session_factory() as session:
            wiki_repo = WikiRepo(session)
            await wiki_repo.create_structure(
                repository_id=repository_id,
                job_id=job_id,
                branch=branch,
                scope_path=scope_path,
                title=result.output.title,
                description=result.output.description,
                sections=sections_json,
                commit_sha=commit_sha,
            )
            await session.commit()

        logger.info(
            "Saved wiki structure for %s/%s (score=%.2f, attempts=%d)",
            branch,
            scope_path,
            result.final_score,
            result.attempts,
        )

    return StructureTaskResult(
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
        output_title=result.output.title if result.output else None,
        output_description=result.output.description if result.output else None,
        sections_json=sections_json,
    )
