from __future__ import annotations

import logging
import shutil
import tempfile
import time
from pathlib import Path

from prefect import flow, task

logger = logging.getLogger(__name__)


@task(name="cleanup_workspace")
async def cleanup_workspace(repo_path: str) -> None:
    """Delete temporary clone directory.

    In K8s production, workspace cleanup is handled by ephemeral pod volumes.
    This task provides explicit cleanup for local dev and as a safety net.

    Args:
        repo_path: Path to the temporary clone directory (autodoc_* prefix).
    """
    path = Path(repo_path)
    if not path.exists():
        logger.info("Workspace already cleaned up: %s", repo_path)
        return

    if not path.name.startswith("autodoc_"):
        logger.warning("Refusing to delete non-autodoc directory: %s", repo_path)
        return

    shutil.rmtree(repo_path, ignore_errors=True)
    logger.info("Cleaned up workspace: %s", repo_path)


@flow(name="cleanup_orphan_workspaces")
async def cleanup_orphan_workspaces() -> None:
    """Scan temp directory for stale autodoc_* workspaces and remove them.

    Removes directories matching the autodoc_* pattern that have not been
    modified in over 1 hour. This is primarily useful for local dev
    environments; in K8s production, ephemeral pod volumes handle cleanup
    automatically.
    """
    tmp_dir = Path(tempfile.gettempdir())
    max_age_seconds = 3600  # 1 hour

    candidates = list(tmp_dir.glob("autodoc_*"))
    if not candidates:
        logger.info("No orphan autodoc workspaces found in %s", tmp_dir)
        return

    now = time.time()
    cleaned = 0

    for candidate in candidates:
        if not candidate.is_dir():
            continue
        mtime = candidate.stat().st_mtime
        age = now - mtime
        if age > max_age_seconds:
            shutil.rmtree(candidate, ignore_errors=True)
            logger.info(
                "Removed orphan workspace: %s (age: %.0f seconds)",
                candidate,
                age,
            )
            cleaned += 1

    logger.info(
        "Orphan workspace cleanup complete: found %d candidates, cleaned %d",
        len(candidates),
        cleaned,
    )
