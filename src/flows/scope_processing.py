from __future__ import annotations

import asyncio
import logging
import os
import uuid

from prefect import flow

from src.database.engine import get_session_factory
from src.database.repos.wiki_repo import WikiRepo
from src.flows.schemas import ScopeProcessingResult, StructureTaskResult
from src.flows.tasks.embeddings import generate_embeddings_task
from src.flows.tasks.pages import generate_pages
from src.flows.tasks.readme import distill_readme
from src.flows.tasks.structure import extract_structure
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)

# Common README filenames in priority order
_README_CANDIDATES = [
    "README.md",
    "README.rst",
    "README.txt",
    "README",
    "readme.md",
    "Readme.md",
]


def read_readme(repo_path: str) -> str:
    """Read the repository README file if it exists.

    Tries common README filenames in priority order and returns the content
    of the first one found. Returns empty string if no README is found.

    Args:
        repo_path: Absolute path to the cloned repository.

    Returns:
        README content as a string, or empty string if not found.
    """
    for candidate in _README_CANDIDATES:
        readme_path = os.path.join(repo_path, candidate)
        try:
            with open(readme_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
            logger.info("Found README at %s", readme_path)
            return content
        except OSError:
            continue
    logger.info("No README found in %s", repo_path)
    return ""


@flow(name="scope_processing", timeout_seconds=3600)
async def scope_processing_flow(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    scope_path: str,
    commit_sha: str,
    repo_path: str | None = None,
    clone_input: dict | None = None,
    config: AutodocConfig | dict | None = None,
    dry_run: bool = False,
) -> ScopeProcessingResult:
    """Process a single documentation scope.

    Pipeline: extract_structure -> (if not dry_run: generate_pages -> (distill_readme || generate_embeddings))

    If structure quality gate fails (below_minimum_floor), raises QualityError
    to skip page generation.

    In K8s mode (clone_input provided, repo_path is None), clones the repo
    at the start of execution. In dev mode, repo_path is passed directly.

    Args:
        repository_id: Repository UUID.
        job_id: Job UUID.
        branch: Target branch.
        scope_path: Documentation scope path (e.g. ".").
        commit_sha: Current commit SHA.
        repo_path: Path to cloned repository (dev mode).
        clone_input: Dict with url, provider, access_token (K8s mode).
        config: AutodocConfig for this scope (or dict when deserialized from K8s).
        dry_run: If True, only extract structure (skip pages + readme).

    Returns:
        ScopeProcessingResult with structure_result, page_results, readme_result,
        wiki_structure_id, embedding_count.
    """
    from src.flows.schemas import CloneInput

    # If config was passed as a dict (from K8s run_deployment serialization),
    # reconstruct the AutodocConfig object
    if isinstance(config, dict):
        config = AutodocConfig(**config)

    # K8s mode: clone repo at start of execution
    cloned_here = False
    if repo_path is None and clone_input is not None:
        from src.flows.tasks.clone import clone_repository

        ci = CloneInput(**clone_input) if isinstance(clone_input, dict) else clone_input
        repo_path, _ = await clone_repository(clone_input=ci, branch=branch)
        cloned_here = True
    elif repo_path is None:
        raise ValueError("Either repo_path or clone_input must be provided")

    try:
        return await _scope_processing_impl(
            repository_id=repository_id,
            job_id=job_id,
            branch=branch,
            scope_path=scope_path,
            commit_sha=commit_sha,
            repo_path=repo_path,
            config=config,
            dry_run=dry_run,
        )
    finally:
        if cloned_here and repo_path:
            from src.flows.tasks.cleanup import cleanup_workspace
            await cleanup_workspace(repo_path=repo_path)


async def _scope_processing_impl(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    scope_path: str,
    commit_sha: str,
    repo_path: str,
    config: AutodocConfig,
    dry_run: bool,
) -> ScopeProcessingResult:
    """Inner implementation of scope processing."""
    from src.errors import QualityError
    from src.flows.schemas import PageTaskResult, ReadmeTaskResult
    from src.flows.tasks.scan import scan_file_tree

    # Scan file tree for this scope
    file_list = await scan_file_tree(repo_path=repo_path, config=config)

    # Read README for structure extraction context
    readme_content = read_readme(repo_path)

    # Extract structure
    structure_result: StructureTaskResult = await extract_structure(
        repository_id=repository_id,
        job_id=job_id,
        branch=branch,
        scope_path=scope_path,
        commit_sha=commit_sha,
        file_list=file_list,
        repo_path=repo_path,
        config=config,
        readme_content=readme_content,
    )

    # Check structure quality gate
    if structure_result.below_minimum_floor:
        raise QualityError(
            f"Structure extraction below minimum floor for scope '{scope_path}' "
            f"(score={structure_result.final_score})"
        )

    # Get the wiki_structure_id from the database
    session_factory = get_session_factory()
    async with session_factory() as session:
        wiki_repo = WikiRepo(session)
        wiki_structure = await wiki_repo.get_latest_structure(
            repository_id=repository_id,
            branch=branch,
            scope_path=scope_path,
        )
    wiki_structure_id = wiki_structure.id if wiki_structure else None

    page_results: list[PageTaskResult] = []
    readme_result: ReadmeTaskResult | None = None
    embedding_count: int = 0

    if not dry_run and structure_result.sections_json is not None and wiki_structure_id is not None:
        # Generate pages
        page_results = await generate_pages(
            job_id=job_id,
            wiki_structure_id=wiki_structure_id,
            structure_result=structure_result,
            repo_path=repo_path,
            config=config,
        )

        # Get generated wiki pages from DB for readme distillation
        async with session_factory() as session:
            wiki_repo = WikiRepo(session)
            wiki_pages = await wiki_repo.get_pages_for_structure(wiki_structure_id)

        page_summaries = [
            {
                "page_key": p.page_key,
                "title": p.title,
                "description": p.description,
                "content": p.content,
            }
            for p in wiki_pages
        ]

        # Run README distillation and embedding generation in parallel
        readme_result, embedding_count = await asyncio.gather(
            distill_readme(
                job_id=job_id,
                structure_title=structure_result.output_title or "",
                structure_description=structure_result.output_description or "",
                page_summaries=page_summaries,
                config=config,
            ),
            generate_embeddings_task(
                wiki_structure_id=wiki_structure_id,
            ),
        )

    return ScopeProcessingResult(
        structure_result=structure_result,
        page_results=page_results,
        readme_result=readme_result,
        wiki_structure_id=wiki_structure_id,
        embedding_count=embedding_count,
    )
