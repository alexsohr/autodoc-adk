from __future__ import annotations

import logging
import tempfile

from prefect import task

from src.database.models.repository import Repository
from src.providers.base import get_provider

logger = logging.getLogger(__name__)


@task(name="clone_repository", retries=2, retry_delay_seconds=10)
async def clone_repository(repository: Repository, branch: str) -> tuple[str, str]:
    """Clone a repository to a temporary directory.

    Args:
        repository: The Repository ORM object.
        branch: Branch to clone.

    Returns:
        Tuple of (repo_path, commit_sha).
    """
    provider = get_provider(repository.provider)
    dest_dir = tempfile.mkdtemp(prefix="autodoc_")

    repo_path, commit_sha = await provider.clone_repository(
        url=repository.url,
        branch=branch,
        access_token=repository.access_token,
        dest_dir=dest_dir,
    )

    logger.info(
        "Cloned %s branch=%s to %s (sha=%s)",
        repository.url,
        branch,
        repo_path,
        commit_sha[:8],
    )
    return repo_path, commit_sha
