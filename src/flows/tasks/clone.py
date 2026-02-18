from __future__ import annotations

import logging
import tempfile

from prefect import task

from src.flows.schemas import CloneInput
from src.providers.base import get_provider

logger = logging.getLogger(__name__)


@task(name="clone_repository", retries=2, retry_delay_seconds=10)
async def clone_repository(clone_input: CloneInput, branch: str) -> tuple[str, str]:
    """Clone a repository to a temporary directory.

    Args:
        clone_input: Serializable repository info for cloning.
        branch: Branch to clone.

    Returns:
        Tuple of (repo_path, commit_sha).
    """
    provider = get_provider(clone_input.provider)
    dest_dir = tempfile.mkdtemp(prefix="autodoc_")

    repo_path, commit_sha = await provider.clone_repository(
        url=clone_input.url,
        branch=branch,
        access_token=clone_input.access_token,
        dest_dir=dest_dir,
    )

    logger.info(
        "Cloned %s branch=%s to %s (sha=%s)",
        clone_input.url,
        branch,
        repo_path,
        commit_sha[:8],
    )
    return repo_path, commit_sha
