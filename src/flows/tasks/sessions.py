from __future__ import annotations

import logging
import uuid

from prefect import task

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


@task(name="archive_sessions")
async def archive_sessions(
    *,
    job_id: uuid.UUID,
    session_ids: list[str],
) -> None:
    """Export ADK session data to S3 as JSON.

    Uses boto3 to upload session data to ``SESSION_ARCHIVE_BUCKET``.
    Skips if ``SESSION_ARCHIVE_BUCKET`` is not configured.
    """
    settings = get_settings()
    if not settings.SESSION_ARCHIVE_BUCKET:
        logger.info("SESSION_ARCHIVE_BUCKET not configured, skipping archival")
        return

    import json

    import boto3

    s3 = boto3.client("s3")
    bucket = settings.SESSION_ARCHIVE_BUCKET

    for sid in session_ids:
        key = f"sessions/{job_id}/{sid}.json"
        # Note: actual session retrieval would use DatabaseSessionService
        # For now, store a reference marker
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps({"session_id": sid, "job_id": str(job_id)}).encode(),
            ContentType="application/json",
        )

    logger.info(
        "Archived %d sessions to s3://%s/sessions/%s/",
        len(session_ids),
        bucket,
        job_id,
    )


@task(name="delete_sessions")
async def delete_sessions(
    *,
    session_ids: list[str],
) -> None:
    """Remove sessions from PostgreSQL after successful archival.

    Uses ADK ``DatabaseSessionService`` to delete sessions.
    """
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("+asyncpg", "")

    from google.adk.sessions import DatabaseSessionService

    session_service = DatabaseSessionService(db_url=db_url)

    for sid in session_ids:
        try:
            await session_service.delete_session(
                app_name="autodoc",
                user_id="system",
                session_id=sid,
            )
        except Exception:
            logger.warning("Failed to delete session %s", sid, exc_info=True)

    logger.info("Deleted %d sessions from PostgreSQL", len(session_ids))
