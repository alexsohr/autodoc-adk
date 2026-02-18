from __future__ import annotations

import logging
import os
from pathlib import Path

from prefect import task

from src.services.config_loader import (
    AutodocConfig,
    apply_scope_overlap_exclusions,
    load_autodoc_config,
)

logger = logging.getLogger(__name__)

# Directories to skip during recursive discovery
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".eggs",
        "dist",
        "build",
    }
)

_CONFIG_FILENAME = ".autodoc.yaml"


@task(name="discover_autodoc_configs")
async def discover_autodoc_configs(repo_path: str) -> list[AutodocConfig]:
    """Recursively discover all ``.autodoc.yaml`` files in a cloned repository.

    Walks the repository directory tree to find every ``.autodoc.yaml``
    config file. For each file found, a scope path is computed as the
    relative directory from the repo root (``"."`` for the root itself).
    After collecting all configs, scope overlap auto-exclusions are applied
    so that parent scopes do not duplicate child scope documentation.

    Hidden directories (starting with ``"."``) and common non-code
    directories (``node_modules``, ``__pycache__``, etc.) are skipped
    during traversal.

    If no ``.autodoc.yaml`` is found anywhere, a single default config
    with ``scope_path="."`` is returned.

    Args:
        repo_path: Absolute path to the cloned repository.

    Returns:
        List of :class:`AutodocConfig` instances, one per discovered
        scope, with overlap exclusions already applied.
    """
    root = Path(repo_path)
    configs: list[AutodocConfig] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune hidden directories and known non-code directories in-place
        # so os.walk does not descend into them.
        dirnames[:] = [
            d
            for d in dirnames
            if not d.startswith(".") and d not in _SKIP_DIRS
        ]

        if _CONFIG_FILENAME not in filenames:
            continue

        config_path = Path(dirpath) / _CONFIG_FILENAME
        rel_dir = Path(dirpath).relative_to(root)
        scope_path = "." if rel_dir == Path(".") else str(rel_dir)

        config = load_autodoc_config(config_path, scope_path=scope_path)
        configs.append(config)

    # If no config files found anywhere, return a single default config
    if not configs:
        logger.info(
            "No .autodoc.yaml found in %s, using default config (scope='.')",
            repo_path,
        )
        return [AutodocConfig(scope_path=".")]

    # Apply scope overlap auto-exclusions
    configs = apply_scope_overlap_exclusions(configs)

    scope_paths = [c.scope_path for c in configs]
    logger.info(
        "Discovered %d autodoc config(s) in %s: %s",
        len(configs),
        repo_path,
        scope_paths,
    )

    return configs
