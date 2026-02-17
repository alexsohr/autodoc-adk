from __future__ import annotations

import logging
import uuid

from prefect import flow

from src.agents.common.agent_result import AgentResult
from src.agents.structure_extractor.schemas import WikiStructureSpec
from src.database.engine import get_session_factory
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.database.repos.wiki_repo import WikiRepo
from src.errors import PermanentError, QualityError
from src.flows.tasks.cleanup import cleanup_workspace
from src.flows.tasks.clone import clone_repository
from src.flows.tasks.discover import discover_autodoc_configs
from src.flows.tasks.metrics import aggregate_job_metrics
from src.flows.tasks.pages import _collect_page_specs, generate_pages
from src.flows.tasks.pr import close_stale_autodoc_prs, create_autodoc_pr
from src.flows.tasks.readme import distill_readme
from src.flows.tasks.scan import scan_file_tree
from src.flows.tasks.sessions import archive_sessions, delete_sessions
from src.flows.tasks.structure import extract_structure
from src.providers.base import get_provider

logger = logging.getLogger(__name__)


def _detect_structural_changes(changed_files: list[str]) -> bool:
    """Detect if changes require re-extracting the wiki structure.

    Structural changes include new/deleted directories, significant
    module-level additions, or changes to autodoc config files.
    """
    structural_indicators = {
        "__init__.py",
        ".autodoc.yaml",
        "setup.py",
        "setup.cfg",
        "pyproject.toml",
        "package.json",
        "cargo.toml",
        "go.mod",
    }
    for path in changed_files:
        filename = path.rsplit("/", 1)[-1].lower()
        if filename in structural_indicators:
            return True
    return False


def _pages_needing_regeneration(
    page_specs: list,
    changed_files: set[str],
) -> tuple[list, list]:
    """Partition page specs into those needing regeneration vs unchanged.

    Returns (affected_specs, unchanged_specs) based on source_file overlap.
    """
    affected = []
    unchanged = []
    for spec in page_specs:
        if any(sf in changed_files for sf in spec.source_files):
            affected.append(spec)
        else:
            unchanged.append(spec)
    return affected, unchanged


@flow(name="incremental_update", timeout_seconds=3600)
async def incremental_update_flow(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    dry_run: bool = False,
) -> None:
    """Incremental documentation update flow.

    Detects changed files since the last generation via provider compare API,
    then regenerates only affected pages. Unchanged pages are duplicated from
    the prior WikiStructure version.

    Pipeline:
    1. Update job PENDING -> RUNNING
    2. Get baseline SHA (min commit_sha across wiki_structures)
    3. Get current HEAD SHA from provider
    4. Compare commits to get changed files
    5. Short-circuit if no changes (mark COMPLETED, no_changes=true)
    6. Clone repository
    7. Detect structural changes
    8. If structural: re-extract structure; else: create new version from prior
    9. Regenerate only affected pages
    10. Duplicate unchanged pages to new structure version
    11. Distill README from all pages
    12. Close stale PRs + create PR (unless dry_run)
    13. Aggregate metrics
    14. Quality gate check
    15. Archive/delete sessions + cleanup

    Args:
        repository_id: Repository UUID.
        job_id: Job UUID.
        branch: Target branch.
        dry_run: If True, skip PR creation and session archival.
    """
    session_factory = get_session_factory()
    repo_path: str | None = None
    session_ids: list[str] = []

    try:
        async with session_factory() as session:
            job_repo = JobRepo(session)
            repo_repo = RepositoryRepo(session)
            wiki_repo = WikiRepo(session)

            # Step 1: PENDING -> RUNNING
            job = await job_repo.update_status(job_id, "RUNNING")
            if job is None:
                raise PermanentError(f"Job {job_id} not found")

            repository = await repo_repo.get_by_id(repository_id)
            if repository is None:
                raise PermanentError(f"Repository {repository_id} not found")

            # Step 2: Get baseline SHA
            baseline_sha = await wiki_repo.get_baseline_sha(
                repository_id=repository_id,
                branch=branch,
            )
            if baseline_sha is None:
                raise PermanentError(
                    "No existing wiki structures found for incremental update. "
                    "Run full generation first."
                )

            # Step 3: Clone to get current HEAD SHA
            repo_path, commit_sha = await clone_repository(
                repository=repository,
                branch=branch,
            )
            job.commit_sha = commit_sha
            await session.flush()

            # Step 4: Compare commits
            provider = get_provider(repository.provider)
            changed_files = await provider.compare_commits(
                url=repository.url,
                base_sha=baseline_sha,
                head_sha=commit_sha,
                access_token=repository.access_token,
            )

            logger.info(
                "Incremental diff: %d changed files (baseline=%s, head=%s)",
                len(changed_files),
                baseline_sha[:8],
                commit_sha[:8],
            )

            # Step 5: Short-circuit if no changes
            if not changed_files:
                logger.info("No changes detected, completing job with no_changes=true")
                job.quality_report = {
                    "overall_score": 0.0,
                    "quality_threshold": 0.0,
                    "passed": True,
                    "total_pages": 0,
                    "no_changes": True,
                }
                await job_repo.update_status(job_id, "COMPLETED")
                await session.commit()
                return

            changed_files_set = set(changed_files)

            # Step 6: Discover configs
            configs = await discover_autodoc_configs(repo_path=repo_path)
            config = configs[0]

            # Step 7: Detect structural changes
            needs_structure_reextraction = _detect_structural_changes(changed_files)

            # Get prior structure for this scope
            prior_structure = await wiki_repo.get_latest_structure(
                repository_id=repository_id,
                branch=branch,
                scope_path=config.scope_path,
            )
            if prior_structure is None:
                raise PermanentError(
                    f"No prior structure for scope '{config.scope_path}'. "
                    "Run full generation first."
                )

            # Get prior pages
            prior_pages = await wiki_repo.get_pages_for_structure(
                wiki_structure_id=prior_structure.id,
            )

            structure_result: AgentResult[WikiStructureSpec] | None = None
            page_results: list[AgentResult] = []
            readme_result = None
            regenerated_page_keys: list[str] = []

            if needs_structure_reextraction:
                # Step 8a: Full structure re-extraction
                logger.info("Structural changes detected, re-extracting structure")
                file_list = await scan_file_tree(
                    repo_path=repo_path, config=config,
                )

                structure_result = await extract_structure(
                    repository_id=repository_id,
                    job_id=job_id,
                    branch=branch,
                    scope_path=config.scope_path,
                    commit_sha=commit_sha,
                    file_list=file_list,
                    repo_path=repo_path,
                    config=config,
                    wiki_repo=wiki_repo,
                )

                if structure_result.below_minimum_floor:
                    raise QualityError(
                        f"Structure extraction below minimum floor "
                        f"(score={structure_result.final_score})"
                    )

                # Get the new structure from DB
                new_structure = await wiki_repo.get_latest_structure(
                    repository_id=repository_id,
                    branch=branch,
                    scope_path=config.scope_path,
                )

                if not dry_run and structure_result.output and new_structure:
                    new_page_specs = _collect_page_specs(
                        structure_result.output.sections,
                    )

                    # Determine which new pages overlap with changed files
                    affected_specs, unchanged_specs = _pages_needing_regeneration(
                        new_page_specs, changed_files_set,
                    )

                    # Generate affected pages
                    if affected_specs:
                        # Create a filtered WikiStructureSpec with only affected pages
                        from src.agents.structure_extractor.schemas import (
                            SectionSpec,
                        )

                        filtered_spec = WikiStructureSpec(
                            title=structure_result.output.title,
                            description=structure_result.output.description,
                            sections=[
                                SectionSpec(
                                    title="Regenerated",
                                    description="Pages regenerated in incremental update",
                                    pages=affected_specs,
                                    subsections=[],
                                ),
                            ],
                        )
                        page_results = await generate_pages(
                            job_id=job_id,
                            wiki_structure_id=new_structure.id,
                            structure_spec=filtered_spec,
                            repo_path=repo_path,
                            config=config,
                            wiki_repo=wiki_repo,
                        )
                        regenerated_page_keys = [
                            s.page_key for s in affected_specs
                        ]

                    # Duplicate unchanged pages from prior structure
                    unchanged_page_keys = {s.page_key for s in unchanged_specs}
                    pages_to_copy = [
                        p for p in prior_pages
                        if p.page_key in unchanged_page_keys
                    ]
                    if pages_to_copy:
                        await wiki_repo.duplicate_pages(
                            source_pages=pages_to_copy,
                            target_structure_id=new_structure.id,
                        )
            else:
                # Step 8b: No structural changes — create new version from prior
                logger.info(
                    "No structural changes, reusing prior structure with updated pages"
                )

                # Create new structure version with same sections
                new_structure = await wiki_repo.create_structure(
                    repository_id=repository_id,
                    job_id=job_id,
                    branch=branch,
                    scope_path=config.scope_path,
                    title=prior_structure.title,
                    description=prior_structure.description,
                    sections=prior_structure.sections,
                    commit_sha=commit_sha,
                )

                if not dry_run:
                    # Build page specs from prior structure's sections JSONB
                    from src.agents.structure_extractor.schemas import (
                        SectionSpec,
                    )

                    prior_page_specs = _build_page_specs_from_sections(
                        prior_structure.sections,
                    )

                    affected_specs, unchanged_specs = _pages_needing_regeneration(
                        prior_page_specs, changed_files_set,
                    )

                    # Generate affected pages
                    if affected_specs:
                        filtered_spec = WikiStructureSpec(
                            title=prior_structure.title,
                            description=prior_structure.description,
                            sections=[
                                SectionSpec(
                                    title="Regenerated",
                                    description="Pages regenerated in incremental update",
                                    pages=affected_specs,
                                    subsections=[],
                                ),
                            ],
                        )
                        page_results = await generate_pages(
                            job_id=job_id,
                            wiki_structure_id=new_structure.id,
                            structure_spec=filtered_spec,
                            repo_path=repo_path,
                            config=config,
                            wiki_repo=wiki_repo,
                        )
                        regenerated_page_keys = [
                            s.page_key for s in affected_specs
                        ]

                    # Duplicate unchanged pages
                    unchanged_page_keys = {s.page_key for s in unchanged_specs}
                    pages_to_copy = [
                        p for p in prior_pages
                        if p.page_key in unchanged_page_keys
                    ]
                    if pages_to_copy:
                        await wiki_repo.duplicate_pages(
                            source_pages=pages_to_copy,
                            target_structure_id=new_structure.id,
                        )

            # Step 11: Distill README from all pages (old + new)
            if not dry_run and new_structure:
                all_pages = await wiki_repo.get_pages_for_structure(
                    wiki_structure_id=new_structure.id,
                )

                if all_pages:
                    # Build a WikiStructureSpec for readme distillation
                    spec_for_readme = _build_structure_spec_from_db(
                        new_structure,
                    )
                    readme_result = await distill_readme(
                        job_id=job_id,
                        structure_spec=spec_for_readme,
                        wiki_pages=all_pages,
                        config=config,
                    )

            # Step 12: PR creation (skip if dry_run)
            pr_url: str | None = None
            if not dry_run and readme_result and readme_result.output:
                await close_stale_autodoc_prs(
                    repository=repository,
                    branch=branch,
                )
                pr_url = await create_autodoc_pr(
                    repository=repository,
                    branch=branch,
                    job_id=job_id,
                    readme_content=readme_result.output.content,
                    repo_path=repo_path,
                    config=config,
                )

            # Step 13: Aggregate metrics
            await aggregate_job_metrics(
                job_id=job_id,
                structure_result=structure_result,
                page_results=page_results,
                readme_result=readme_result,
                job_repo=job_repo,
            )

            # Add incremental-specific fields to quality_report
            job_refreshed = await job_repo.get_by_id(job_id)
            if job_refreshed and job_refreshed.quality_report:
                job_refreshed.quality_report["regenerated_pages"] = (
                    regenerated_page_keys
                )
                job_refreshed.quality_report["no_changes"] = False
                await session.flush()

            # Step 14: Quality gate
            any_below_floor = False
            if structure_result and structure_result.below_minimum_floor:
                any_below_floor = True
            if readme_result and readme_result.below_minimum_floor:
                any_below_floor = True
            for pr in page_results:
                if pr.below_minimum_floor:
                    any_below_floor = True
                    break

            if any_below_floor:
                await job_repo.update_status(
                    job_id,
                    "FAILED",
                    error_message="Quality gate failed: agent output below minimum floor",
                    pull_request_url=pr_url,
                )
            else:
                await job_repo.update_status(
                    job_id,
                    "COMPLETED",
                    pull_request_url=pr_url,
                )

            # Step 15: Session archival (skip on dry_run)
            if not dry_run and session_ids:
                await archive_sessions(job_id=job_id, session_ids=session_ids)
                await delete_sessions(session_ids=session_ids)

            await session.commit()

    except QualityError as exc:
        logger.warning("Quality gate failed for job %s: %s", job_id, exc)
        async with session_factory() as session:
            job_repo = JobRepo(session)
            await job_repo.update_status(
                job_id, "FAILED", error_message=str(exc),
            )
            await session.commit()
    except TimeoutError:
        logger.error("Flow timed out for job %s", job_id)
        try:
            async with session_factory() as session:
                job_repo = JobRepo(session)
                await job_repo.update_status(
                    job_id,
                    "FAILED",
                    error_message="Flow timed out after 3600 seconds",
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to update job status after timeout")
    except Exception as exc:
        logger.exception("Incremental update flow failed for job %s", job_id)
        try:
            async with session_factory() as session:
                job_repo = JobRepo(session)
                await job_repo.update_status(
                    job_id, "FAILED", error_message=f"Flow error: {exc}",
                )
                await session.commit()
        except Exception:
            logger.exception("Failed to update job status to FAILED")
    finally:
        if repo_path:
            await cleanup_workspace(repo_path=repo_path)


def _build_page_specs_from_sections(sections_jsonb: dict | list) -> list:
    """Build PageSpec list from the sections JSONB stored in WikiStructure.

    The JSONB is a list of section dicts with nested pages and subsections.
    """
    from src.agents.structure_extractor.schemas import PageSpec

    specs: list[PageSpec] = []
    items = sections_jsonb if isinstance(sections_jsonb, list) else [sections_jsonb]
    for section in items:
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
            specs.extend(
                _build_page_specs_from_sections([sub]),
            )
    return specs


def _build_structure_spec_from_db(
    structure,
) -> WikiStructureSpec:
    """Build a WikiStructureSpec from a WikiStructure ORM object.

    Reconstructs the dataclass from the stored JSONB sections.
    """
    from src.agents.structure_extractor.schemas import (
        PageSpec,
        SectionSpec,
    )

    def _build_section(data: dict) -> SectionSpec:
        pages = [
            PageSpec(
                page_key=p["page_key"],
                title=p["title"],
                description=p.get("description", ""),
                importance=p.get("importance", "medium"),
                page_type=p.get("page_type", "overview"),
                source_files=p.get("source_files", []),
                related_pages=p.get("related_pages", []),
            )
            for p in data.get("pages", [])
        ]
        subsections = [
            _build_section(sub) for sub in data.get("subsections", [])
        ]
        return SectionSpec(
            title=data["title"],
            description=data.get("description", ""),
            pages=pages,
            subsections=subsections,
        )

    raw_sections = structure.sections
    if isinstance(raw_sections, list):
        sections = [_build_section(s) for s in raw_sections]
    else:
        sections = [_build_section(raw_sections)]

    return WikiStructureSpec(
        title=structure.title,
        description=structure.description,
        sections=sections,
    )
