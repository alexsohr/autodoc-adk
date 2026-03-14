"""Startup reconciliation of stale PENDING/RUNNING jobs against Prefect flow run states."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repos.job_repo import JobRepo

logger = logging.getLogger(__name__)

# PENDING jobs older than this are considered stale even without a Prefect flow run ID.
# This catches the case where the flow crashes before committing the RUNNING status.
_PENDING_STALENESS_THRESHOLD = timedelta(minutes=30)


async def reconcile_stale_jobs(session: AsyncSession) -> None:
    """Reconcile jobs stuck in PENDING or RUNNING status against Prefect flow run states.

    Handles two scenarios:
    1. RUNNING jobs whose Prefect flow run has crashed or completed without
       updating the application-level job status.
    2. PENDING jobs that have been waiting longer than the staleness threshold,
       indicating the Prefect flow either crashed before transitioning the job
       to RUNNING, or was never submitted.

    For each stale job, the status is transitioned to FAILED with an explanatory
    error message.

    This function is intended to be called once during application startup.
    """
    repo = JobRepo(session)
    active_jobs = await repo.get_active_jobs()

    if not active_jobs:
        logger.info("No stale PENDING/RUNNING jobs to reconcile")
        return

    logger.info("Reconciling %d active job(s) against Prefect", len(active_jobs))

    now = datetime.now(timezone.utc)
    from prefect.client.orchestration import get_client

    async with get_client() as client:
        for job in active_jobs:
            # For PENDING jobs without a flow run ID, check age
            if job.prefect_flow_run_id is None:
                if job.status == "PENDING":
                    age = now - job.created_at.replace(tzinfo=timezone.utc)
                    if age < _PENDING_STALENESS_THRESHOLD:
                        logger.info(
                            "Job %s is PENDING but only %s old, skipping",
                            job.id,
                            age,
                        )
                        continue
                await repo.update_status(
                    job.id,
                    "FAILED",
                    error_message=(
                        f"Stale {job.status} job reconciled on startup: "
                        "no Prefect flow run ID recorded"
                    ),
                )
                logger.warning(
                    "Reconciled job %s (%s) -> FAILED (no flow run ID)",
                    job.id,
                    job.status,
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
                    error_message=(
                        f"Stale {job.status} job reconciled on startup: "
                        "could not read Prefect flow run"
                    ),
                )
                logger.warning(
                    "Reconciled job %s (%s) -> FAILED (could not read flow run)",
                    job.id,
                    job.status,
                )
                continue

            if flow_run.state is not None and flow_run.state.is_final():
                await repo.update_status(
                    job.id,
                    "FAILED",
                    error_message=(
                        f"Stale {job.status} job reconciled on startup: "
                        f"Prefect flow run was {flow_run.state.name}"
                    ),
                )
                logger.warning(
                    "Reconciled job %s (%s) -> FAILED (Prefect state: %s)",
                    job.id,
                    job.status,
                    flow_run.state.name,
                )
            else:
                state_name = flow_run.state.name if flow_run.state else "unknown"
                logger.info(
                    "Job %s (%s) still active in Prefect (state: %s), skipping",
                    job.id,
                    job.status,
                    state_name,
                )
