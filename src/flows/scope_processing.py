from __future__ import annotations

import logging
import uuid

from prefect import flow

from src.agents.common.agent_result import AgentResult
from src.agents.readme_distiller.schemas import ReadmeOutput
from src.agents.structure_extractor.schemas import WikiStructureSpec
from src.database.repos.wiki_repo import WikiRepo
from src.flows.tasks.pages import generate_pages
from src.flows.tasks.readme import distill_readme
from src.flows.tasks.structure import extract_structure
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


@flow(name="scope_processing", timeout_seconds=3600)
async def scope_processing_flow(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    scope_path: str,
    commit_sha: str,
    repo_path: str,
    config: AutodocConfig,
    wiki_repo: WikiRepo,
    dry_run: bool = False,
) -> dict:
    """Process a single documentation scope.

    Pipeline: extract_structure -> (if not dry_run: generate_pages -> distill_readme)

    If structure quality gate fails (below_minimum_floor), raises QualityError
    to skip page generation.

    Args:
        repository_id: Repository UUID.
        job_id: Job UUID.
        branch: Target branch.
        scope_path: Documentation scope path (e.g. ".").
        commit_sha: Current commit SHA.
        repo_path: Path to cloned repository.
        config: AutodocConfig for this scope.
        wiki_repo: WikiRepo instance.
        dry_run: If True, only extract structure (skip pages + readme).

    Returns:
        Dict with structure_result, page_results, readme_result, wiki_structure_id.
    """
    from src.errors import QualityError
    from src.flows.tasks.scan import scan_file_tree

    # Scan file tree for this scope
    file_list = await scan_file_tree(repo_path=repo_path, config=config)

    # Extract structure
    structure_result: AgentResult[WikiStructureSpec] = await extract_structure(
        repository_id=repository_id,
        job_id=job_id,
        branch=branch,
        scope_path=scope_path,
        commit_sha=commit_sha,
        file_list=file_list,
        repo_path=repo_path,
        config=config,
        wiki_repo=wiki_repo,
    )

    # Check structure quality gate
    if structure_result.below_minimum_floor:
        raise QualityError(
            f"Structure extraction below minimum floor for scope '{scope_path}' "
            f"(score={structure_result.final_score})"
        )

    # Get the wiki_structure_id from the database
    wiki_structure = await wiki_repo.get_latest_structure(
        repository_id=repository_id,
        branch=branch,
        scope_path=scope_path,
    )
    wiki_structure_id = wiki_structure.id if wiki_structure else None

    page_results: list[AgentResult] = []
    readme_result: AgentResult[ReadmeOutput] | None = None

    if not dry_run and structure_result.output is not None and wiki_structure_id is not None:
        # Generate pages
        page_results = await generate_pages(
            job_id=job_id,
            wiki_structure_id=wiki_structure_id,
            structure_spec=structure_result.output,
            repo_path=repo_path,
            config=config,
            wiki_repo=wiki_repo,
        )

        # Get generated wiki pages from DB for readme distillation
        # (need the ORM objects with content, not just AgentResults)
        import sqlalchemy as sa

        from src.database.models.wiki_page import WikiPage

        stmt = sa.select(WikiPage).where(
            WikiPage.wiki_structure_id == wiki_structure_id
        )
        result = await wiki_repo._session.execute(stmt)
        wiki_pages = list(result.scalars().all())

        # Distill README
        readme_result = await distill_readme(
            job_id=job_id,
            structure_spec=structure_result.output,
            wiki_pages=wiki_pages,
            config=config,
        )

    return {
        "structure_result": structure_result,
        "page_results": page_results,
        "readme_result": readme_result,
        "wiki_structure_id": wiki_structure_id,
    }
