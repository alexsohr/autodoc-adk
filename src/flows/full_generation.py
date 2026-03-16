from __future__ import annotations

import asyncio
import logging
import uuid

from prefect import flow

from src.database.engine import get_session_factory
from src.database.repos.job_repo import JobRepo
from src.database.repos.repository_repo import RepositoryRepo
from src.errors import PermanentError, QualityError
from src.flows.schemas import CloneInput, PrRepositoryInfo
from src.flows.scope_processing import scope_processing_flow
from src.flows.tasks.callback import deliver_callback
from src.flows.tasks.cleanup import cleanup_workspace
from src.flows.tasks.clone import clone_repository
from src.flows.tasks.discover import discover_autodoc_configs
from src.flows.tasks.metrics import aggregate_job_metrics
from src.flows.tasks.pr import ScopeReadme, close_stale_autodoc_prs, create_autodoc_pr

logger = logging.getLogger(__name__)


@flow(name="full_generation", timeout_seconds=3600)
async def full_generation_flow(
    *,
    repository_id: uuid.UUID,
    job_id: uuid.UUID,
    branch: str,
    dry_run: bool = False,
) -> None:
    """Full documentation generation flow.

    Pipeline:
    1. Update job PENDING -> RUNNING
    2. Clone repository
    3. Discover .autodoc.yaml configs
    4. Process all scopes in parallel (extract structure -> generate pages -> distill readme)
    5. Close stale PRs + create new PR with all scope READMEs (if not dry_run)
    6. Aggregate metrics across all scopes
    7. Check quality gate for final status
    8. Archive + delete sessions (if not dry_run)
    9. Cleanup workspace
    10. Update job to COMPLETED (or FAILED)

    Args:
        repository_id: Repository UUID (resolved before flow submission).
        job_id: Job UUID.
        branch: Target branch.
        dry_run: If True, skip PR creation and session archival.
    """
    session_factory = get_session_factory()
    repo_path: str | None = None
    callback_url: str | None = None

    try:
        # --- Session 1: Initialize job, clone, update commit_sha ---
        # Short-lived: commit and release the DB connection before scope
        # processing so child tasks are not starved of pool connections.
        async with session_factory() as session:
            job_repo = JobRepo(session)
            repo_repo = RepositoryRepo(session)

            # Step 1: Update job status to RUNNING
            job = await job_repo.update_status(job_id, "RUNNING")
            if job is None:
                raise PermanentError(f"Job {job_id} not found")

            # Look up repository
            repository = await repo_repo.get_by_id(repository_id)
            if repository is None:
                raise PermanentError(f"Repository {repository_id} not found")

            callback_url = job.callback_url

            # Step 2: Clone repository
            clone_input = CloneInput(
                url=repository.url,
                provider=repository.provider,
                access_token=repository.access_token,
            )
            repo_path, commit_sha = await clone_repository(
                clone_input=clone_input,
                branch=branch,
            )

            # Update commit SHA on job
            job.commit_sha = commit_sha
            await session.commit()

        # Extract repo info for PR creation (objects detached but readable
        # with expire_on_commit=False).
        repo_info = PrRepositoryInfo(
            url=repository.url,
            provider=repository.provider,
            name=repository.name,
            access_token=repository.access_token,
            public_branch=repository.public_branch,
        )

        # Step 3: Discover configs (no DB session needed)
        configs = await discover_autodoc_configs(repo_path=repo_path)

        # Step 4: Process all scopes in parallel
        # Run scope processing in-process within the orchestrator.
        # In K8s mode, the orchestrator runs as a K8s Job with the cloned
        # repo already available. Separate K8s Jobs per scope (via
        # run_deployment) would require result serialization infrastructure
        # that isn't provisioned yet — deferred to a future change.
        async def _process_scope(cfg):
            return await scope_processing_flow(
                repository_id=repository_id,
                job_id=job_id,
                branch=branch,
                scope_path=cfg.scope_path,
                commit_sha=commit_sha,
                repo_path=repo_path,
                config=cfg,
                dry_run=dry_run,
            )

        scope_results = await asyncio.gather(
            *[_process_scope(cfg) for cfg in configs],
            return_exceptions=True,
        )

        # Collect results across all scopes
        all_structure_results = []
        all_page_results = []
        all_readme_results = []
        scope_readmes: list[ScopeReadme] = []

        for i, result in enumerate(scope_results):
            if isinstance(result, Exception):
                logger.error(
                    "Scope '%s' failed: %s: %s",
                    configs[i].scope_path,
                    type(result).__name__,
                    result,
                    exc_info=result,
                )
                continue

            sr = result.structure_result
            pr_list = result.page_results
            rr = result.readme_result

            if sr:
                all_structure_results.append(sr)
            all_page_results.extend(pr_list)
            if rr:
                all_readme_results.append(rr)
                scope_readmes.append(
                    ScopeReadme(content=rr.content, config=configs[i])
                )

        # Check for total scope failure
        failed_scopes = sum(
            1 for r in scope_results if isinstance(r, Exception)
        )
        if failed_scopes == len(configs):
            raise PermanentError(
                f"All {failed_scopes} scope(s) failed during processing"
            )
        if failed_scopes > 0:
            logger.warning(
                "%d of %d scope(s) failed; continuing with partial results",
                failed_scopes,
                len(configs),
            )

        # Step 5: PR creation (skip if dry_run; uses provider API, not DB)
        pr_url: str | None = None
        if not dry_run and scope_readmes:
            await close_stale_autodoc_prs(
                repo_info=repo_info,
                branch=branch,
            )

            pr_url = await create_autodoc_pr(
                repo_info=repo_info,
                branch=branch,
                job_id=job_id,
                scope_readmes=scope_readmes,
                repo_path=repo_path,
            )

        # Step 6: Aggregate metrics across all scopes.
        # (Uses its own short-lived DB session internally.)
        # TODO: aggregate_job_metrics only accepts a single structure/readme
        # result. For monorepo (multiple scopes), only the first scope's
        # structure and readme scores appear in the quality report.
        # Follow-up: accept list[StructureTaskResult] and list[ReadmeTaskResult].
        structure_result = all_structure_results[0] if all_structure_results else None
        readme_result = all_readme_results[0] if all_readme_results else None

        await aggregate_job_metrics(
            job_id=job_id,
            structure_result=structure_result,
            page_results=all_page_results,
            readme_result=readme_result,
        )

        # Step 7: Check quality gate for final status (pure Python)
        any_below_floor = False
        for sr in all_structure_results:
            if sr.below_minimum_floor:
                any_below_floor = True
                break
        if not any_below_floor:
            for rr in all_readme_results:
                if rr.below_minimum_floor:
                    any_below_floor = True
                    break
        if not any_below_floor:
            for pr in all_page_results:
                if pr.below_minimum_floor:
                    any_below_floor = True
                    break

        if any_below_floor:
            final_status = "FAILED"
            error_msg = "Quality gate failed: agent output below minimum floor"
        else:
            final_status = "COMPLETED"
            error_msg = None

        # --- Session 2: Update final job status ---
        async with session_factory() as session:
            job_repo = JobRepo(session)
            job = await job_repo.update_status(
                job_id,
                final_status,
                error_message=error_msg,
                pull_request_url=pr_url,
            )
            await session.commit()

        # TODO: Session archival — session IDs are now created inside
        # tasks. Needs redesign to collect and archive them at flow level.

        # Step 10: Deliver callback (outside DB transaction)
        if callback_url:
            await deliver_callback(
                job_id=job_id,
                status=final_status,
                repository_id=repository_id,
                branch=branch,
                callback_url=callback_url,
                pull_request_url=pr_url,
                quality_report=job.quality_report if job else None,
                token_usage=job.token_usage if job else None,
                error_message=error_msg,
            )

    except QualityError as exc:
        logger.warning("Quality gate failed for job %s: %s", job_id, exc)
        error_msg = str(exc)
        async with session_factory() as session:
            job_repo = JobRepo(session)
            job = await job_repo.update_status(
                job_id,
                "FAILED",
                error_message=error_msg,
            )
            await session.commit()
        if job and job.callback_url:
            await deliver_callback(
                job_id=job_id,
                status="FAILED",
                repository_id=repository_id,
                branch=branch,
                callback_url=job.callback_url,
                error_message=error_msg,
            )
    except TimeoutError:
        logger.error("Flow timed out for job %s", job_id)
        error_msg = "Flow timed out after 3600 seconds"
        try:
            async with session_factory() as session:
                job_repo = JobRepo(session)
                job = await job_repo.update_status(
                    job_id,
                    "FAILED",
                    error_message=error_msg,
                )
                await session.commit()
            if job and job.callback_url:
                await deliver_callback(
                    job_id=job_id,
                    status="FAILED",
                    repository_id=repository_id,
                    branch=branch,
                    callback_url=job.callback_url,
                    error_message=error_msg,
                )
        except Exception:
            logger.exception("Failed to update job status to FAILED after timeout")
    except Exception as exc:
        logger.exception("Full generation flow failed for job %s", job_id)
        error_msg = f"Flow error: {exc}"
        try:
            async with session_factory() as session:
                job_repo = JobRepo(session)
                job = await job_repo.update_status(
                    job_id,
                    "FAILED",
                    error_message=error_msg,
                )
                await session.commit()
            if job and job.callback_url:
                await deliver_callback(
                    job_id=job_id,
                    status="FAILED",
                    repository_id=repository_id,
                    branch=branch,
                    callback_url=job.callback_url,
                    error_message=error_msg,
                )
        except Exception:
            logger.exception("Failed to update job status to FAILED")
    finally:
        # Step 9: Cleanup workspace
        if repo_path:
            await cleanup_workspace(repo_path=repo_path)
