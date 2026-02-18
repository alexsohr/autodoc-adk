"""Startup reconciliation of stale RUNNING jobs against Prefect flow run states."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repos.job_repo import JobRepo

logger = logging.getLogger(__name__)


async def reconcile_stale_jobs(session: AsyncSession) -> None:
    """Reconcile jobs stuck in RUNNING status against Prefect flow run states.

    For each RUNNING job, checks the corresponding Prefect flow run.  If the
    flow run has reached a terminal state (or no flow run ID was recorded),
    the job is transitioned to FAILED with an explanatory error message.

    This function is intended to be called once during application startup.
    """
    repo = JobRepo(session)
    running_jobs = await repo.get_running_jobs()

    if not running_jobs:
        logger.info("No stale RUNNING jobs to reconcile")
        return

    logger.info("Reconciling %d RUNNING job(s) against Prefect", len(running_jobs))

    from prefect.client.orchestration import get_client

    async with get_client() as client:
        for job in running_jobs:
            if job.prefect_flow_run_id is None:
                await repo.update_status(
                    job.id,
                    "FAILED",
                    error_message="Stale job reconciled on startup: no flow run ID",
                )
                logger.warning(
                    "Reconciled job %s -> FAILED (no flow run ID)", job.id
                )
                continue

            try:
                flow_run_id = uuid.UUID(job.prefect_flow_run_id)
                flow_run = await client.read_flow_run(flow_run_id)
            except Exception:
                logger.exception(
                    "Failed to read Prefect flow run %s for job %s",
                    job.prefect_flow_run_id,
                    job.id,
                )
                await repo.update_status(
                    job.id,
                    "FAILED",
                    error_message="Stale job reconciled on startup",
                )
                logger.warning(
                    "Reconciled job %s -> FAILED (could not read flow run)",
                    job.id,
                )
                continue

            if flow_run.state is not None and flow_run.state.is_final():
                await repo.update_status(
                    job.id,
                    "FAILED",
                    error_message="Stale job reconciled on startup",
                )
                logger.warning(
                    "Reconciled job %s -> FAILED (Prefect state: %s)",
                    job.id,
                    flow_run.state.name,
                )
            else:
                state_name = flow_run.state.name if flow_run.state else "unknown"
                logger.info(
                    "Job %s still active in Prefect (state: %s), skipping",
                    job.id,
                    state_name,
                )
