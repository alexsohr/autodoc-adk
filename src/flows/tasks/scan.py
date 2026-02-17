from __future__ import annotations

import logging
import os
from fnmatch import fnmatch
from pathlib import Path

from prefect import task

from src.config.settings import get_settings
from src.errors import PermanentError
from src.services.config_loader import AutodocConfig

logger = logging.getLogger(__name__)


@task(name="scan_file_tree")
async def scan_file_tree(repo_path: str, config: AutodocConfig) -> list[str]:
    """Walk cloned repo directory and return filtered file list.

    Enforces MAX_REPO_SIZE, MAX_TOTAL_FILES, MAX_FILE_SIZE limits.
    Applies include/exclude patterns from AutodocConfig.

    Args:
        repo_path: Path to cloned repository.
        config: AutodocConfig with include/exclude patterns.

    Returns:
        List of relative file paths.

    Raises:
        PermanentError: If repo exceeds size limits.
    """
    settings = get_settings()
    repo = Path(repo_path)

    all_files: list[str] = []
    total_size = 0

    for root, dirs, files in os.walk(repo_path):
        # Skip hidden dirs and common non-code dirs
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in {"node_modules", "__pycache__", ".git", "venv", ".venv"}
        ]

        for fname in files:
            if fname.startswith("."):
                continue
            fpath = Path(root) / fname

            try:
                fsize = fpath.stat().st_size
            except OSError:
                continue

            if fsize > settings.MAX_FILE_SIZE:
                logger.warning(
                    "Skipping oversized file: %s (%d bytes)", fpath, fsize
                )
                continue

            total_size += fsize
            if total_size > settings.MAX_REPO_SIZE:
                raise PermanentError(
                    f"Repository exceeds maximum size ({settings.MAX_REPO_SIZE} bytes)"
                )

            rel_path = str(fpath.relative_to(repo))
            all_files.append(rel_path)

            if len(all_files) > settings.MAX_TOTAL_FILES:
                raise PermanentError(
                    f"Repository exceeds maximum file count ({settings.MAX_TOTAL_FILES})"
                )

    # Apply include/exclude patterns
    filtered = _apply_patterns(all_files, config.include, config.exclude)

    before_count = len(all_files)
    after_count = len(filtered)
    if before_count > 0 and after_count / before_count < 0.1:
        logger.warning(
            "Include/exclude patterns pruned >90%% of files (%d -> %d)",
            before_count,
            after_count,
        )

    logger.info("Scanned %d files, %d after filtering", before_count, after_count)
    return filtered


def _matches_pattern(filepath: str, pattern: str) -> bool:
    """Check if a file path matches an include/exclude pattern.

    Patterns without glob characters (``*``, ``?``, ``[``) are treated as
    directory prefixes.  For example, ``"src"`` or ``"src/"`` matches all
    files whose relative path starts with ``src/``, but will **not** match
    unrelated paths like ``srclib/foo.py``.

    Patterns that contain glob characters are matched using
    :func:`fnmatch.fnmatch` semantics.
    """
    if not any(c in pattern for c in "*?["):
        # Directory prefix pattern — normalise away any trailing slash
        prefix = pattern.rstrip("/")
        return filepath == prefix or filepath.startswith(prefix + "/")
    return fnmatch(filepath, pattern)


def _apply_patterns(
    files: list[str],
    include: list[str],
    exclude: list[str],
) -> list[str]:
    """Apply include/exclude glob patterns to file list.

    Include semantics: empty = all files; non-empty = ONLY those paths.
    Exclude always subtracts from the included set.
    """
    result = (
        [f for f in files if any(_matches_pattern(f, p) for p in include)]
        if include
        else list(files)
    )

    if exclude:
        result = [f for f in result if not any(_matches_pattern(f, p) for p in exclude)]

    return result
