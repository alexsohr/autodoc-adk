from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

import httpx
from prefect import task

logger = logging.getLogger(__name__)

_BACKOFF_BASE = 2
_MAX_RETRIES = 3
_TIMEOUT_SECONDS = 30


@task(name="deliver_callback")
async def deliver_callback(
    *,
    job_id: uuid.UUID,
    status: str,
    repository_id: uuid.UUID,
    branch: str,
    callback_url: str,
    pull_request_url: str | None = None,
    quality_report: dict | None = None,
    token_usage: dict | None = None,
    error_message: str | None = None,
) -> None:
    """POST a webhook notification to the callback URL on job completion or failure.

    Retries up to 3 times with exponential backoff (2s, 4s, 8s) on transient
    failures (5xx, connection errors, timeouts). Permanent failures (4xx) are
    not retried. Callback delivery failure never raises -- it logs a warning
    and returns so it does not fail the parent job.

    Args:
        job_id: UUID of the completed/failed job.
        status: Final job status (e.g. "COMPLETED", "FAILED").
        repository_id: UUID of the target repository.
        branch: Branch that was documented.
        callback_url: URL to POST the webhook payload to.
        pull_request_url: URL of the created PR, if any.
        quality_report: Quality metrics dict from aggregate_job_metrics.
        token_usage: Token consumption dict.
        error_message: Error description if the job failed.
    """
    completed_at = datetime.now(tz=UTC)

    payload = {
        "job_id": str(job_id),
        "status": status,
        "repository_id": str(repository_id),
        "branch": branch,
        "pull_request_url": pull_request_url,
        "quality_report": quality_report,
        "token_usage": token_usage,
        "error_message": error_message,
        "completed_at": completed_at.isoformat(),
    }

    last_exception: Exception | None = None

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(callback_url, json=payload)

            if response.status_code < 400:
                logger.info(
                    "Callback delivered for job %s to %s (status %d)",
                    job_id,
                    callback_url,
                    response.status_code,
                )
                return

            # Client errors (4xx) are permanent -- do not retry
            if 400 <= response.status_code < 500:
                logger.warning(
                    "Callback permanently failed for job %s: %s returned %d",
                    job_id,
                    callback_url,
                    response.status_code,
                )
                return

            # Server errors (5xx) are transient -- retry
            last_exception = httpx.HTTPStatusError(
                f"Server error {response.status_code}",
                request=response.request,
                response=response,
            )
            logger.warning(
                "Callback attempt %d/%d failed for job %s: %s returned %d",
                attempt,
                _MAX_RETRIES,
                job_id,
                callback_url,
                response.status_code,
            )

        except (httpx.ConnectError, httpx.TimeoutException, httpx.ConnectTimeout) as exc:
            last_exception = exc
            logger.warning(
                "Callback attempt %d/%d failed for job %s: %s",
                attempt,
                _MAX_RETRIES,
                job_id,
                exc,
            )

        # Exponential backoff: base * 2^(attempt-1) => 2s, 4s, 8s
        if attempt < _MAX_RETRIES:
            delay = _BACKOFF_BASE * (2 ** (attempt - 1))
            await asyncio.sleep(delay)

    logger.warning(
        "Callback delivery failed after %d attempts for job %s to %s: %s",
        _MAX_RETRIES,
        job_id,
        callback_url,
        last_exception,
    )
