from __future__ import annotations

import logging
import uuid
from dataclasses import asdict

from prefect import task

from src.agents.common.agent_result import AgentResult
from src.agents.structure_extractor import (
    StructureExtractor,
    StructureExtractorInput,
    WikiStructureSpec,
)
from src.config.settings import get_settings
from src.database.repos.wiki_repo import WikiRepo
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
    wiki_repo: WikiRepo,
    readme_content: str = "",
) -> AgentResult[WikiStructureSpec]:
    """Run StructureExtractor agent and save result to database.

    Creates a DatabaseSessionService session (user_id=job_id), runs
    StructureExtractor with file list and config, saves WikiStructure
    to DB via WikiRepo (enforce version retention).

    Args:
        repository_id: Repository UUID.
        job_id: Job UUID (used as session user_id).
        branch: Target branch.
        scope_path: Documentation scope path.
        commit_sha: Current commit SHA.
        file_list: List of repository file paths.
        repo_path: Path to cloned repository.
        config: AutodocConfig for this scope.
        wiki_repo: WikiRepo instance for DB operations.
        readme_content: Contents of the repository README, if available.

    Returns:
        AgentResult[WikiStructureSpec] with structure output and quality metadata.
    """
    settings = get_settings()

    # Create ADK DatabaseSessionService
    # Note: We need to use the sync database URL for ADK's session service
    db_url = settings.DATABASE_URL.replace("+asyncpg", "")

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

    # Save to database
    if result.output is not None:
        sections_json = _structure_spec_to_sections_json(result.output)
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
        logger.info(
            "Saved wiki structure for %s/%s (score=%.2f, attempts=%d)",
            branch,
            scope_path,
            result.final_score,
            result.attempts,
        )

    return result
