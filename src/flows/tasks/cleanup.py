from __future__ import annotations

import logging
import shutil
from pathlib import Path

from prefect import task

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
