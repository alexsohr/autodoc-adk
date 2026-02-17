from __future__ import annotations

import logging
from pathlib import Path

from prefect import task

from src.services.config_loader import AutodocConfig, load_autodoc_config

logger = logging.getLogger(__name__)


@task(name="discover_autodoc_configs")
async def discover_autodoc_configs(repo_path: str) -> list[AutodocConfig]:
    """Look for .autodoc.yaml in repo root and return configs.

    For Phase 3 (single scope), only checks root. Phase 6 (US5) extends
    this to recursively find all .autodoc.yaml files for monorepo support.

    Args:
        repo_path: Path to cloned repository.

    Returns:
        List with single AutodocConfig (scope_path=".").
    """
    config_path = Path(repo_path) / ".autodoc.yaml"
    config = load_autodoc_config(config_path, scope_path=".")

    logger.info(
        "Discovered config at %s (scope=%s, include=%d patterns, exclude=%d patterns)",
        config_path if config_path.exists() else "defaults",
        config.scope_path,
        len(config.include),
        len(config.exclude),
    )

    return [config]
