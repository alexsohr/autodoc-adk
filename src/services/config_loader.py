from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from src.errors import PermanentError

logger = logging.getLogger(__name__)

# Known keys for unknown-key detection
_KNOWN_KEYS = {
    "version",
    "include",
    "exclude",
    "style",
    "custom_instructions",
    "readme",
    "pull_request",
}
_KNOWN_STYLE_KEYS = {"audience", "tone", "detail_level"}
_KNOWN_README_KEYS = {"output_path", "max_length", "include_toc", "include_badges"}
_KNOWN_PR_KEYS = {"auto_merge", "reviewers"}

_VALID_DETAIL_LEVELS = ("minimal", "standard", "comprehensive")


@dataclass
class StyleConfig:
    """Style settings for generated documentation."""

    audience: str = "developer"
    tone: str = "technical"
    detail_level: str = "standard"  # "minimal", "standard", "comprehensive"


@dataclass
class ReadmeConfig:
    """README generation settings."""

    output_path: str = "README.md"
    max_length: int | None = None  # null = unlimited, integer = word cap
    include_toc: bool = True
    include_badges: bool = False


@dataclass
class PullRequestConfig:
    """Pull request creation settings."""

    auto_merge: bool = False
    reviewers: list[str] = field(default_factory=list)


@dataclass
class AutodocConfig:
    """Parsed .autodoc.yaml configuration."""

    scope_path: str = "."  # set by caller based on config file location
    version: str = "1"
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    style: StyleConfig = field(default_factory=StyleConfig)
    custom_instructions: str = ""
    readme: ReadmeConfig = field(default_factory=ReadmeConfig)
    pull_request: PullRequestConfig = field(default_factory=PullRequestConfig)


def _warn_unknown_keys(
    raw: dict,
    known: set[str],
    prefix: str,
    config_path: Path,
) -> None:
    """Log warnings for any keys in *raw* that are not in *known*."""
    for key in raw:
        if key not in known:
            logger.warning(
                "Unknown key '%s%s' in %s (ignoring)",
                prefix,
                key,
                config_path,
            )


def _parse_style(raw: dict, config_path: Path) -> StyleConfig:
    """Parse and validate the ``style`` section."""
    if not isinstance(raw, dict):
        raise PermanentError(
            f"'style' must be a mapping, got {type(raw).__name__}"
        )
    _warn_unknown_keys(raw, _KNOWN_STYLE_KEYS, "style.", config_path)

    style = StyleConfig()
    if "audience" in raw:
        style.audience = str(raw["audience"])
    if "tone" in raw:
        style.tone = str(raw["tone"])
    if "detail_level" in raw:
        val = str(raw["detail_level"])
        if val not in _VALID_DETAIL_LEVELS:
            raise PermanentError(
                f"style.detail_level must be one of {_VALID_DETAIL_LEVELS}, got '{val}'"
            )
        style.detail_level = val
    return style


def _parse_readme(raw: dict, config_path: Path) -> ReadmeConfig:
    """Parse and validate the ``readme`` section."""
    if not isinstance(raw, dict):
        raise PermanentError(
            f"'readme' must be a mapping, got {type(raw).__name__}"
        )
    _warn_unknown_keys(raw, _KNOWN_README_KEYS, "readme.", config_path)

    readme = ReadmeConfig()
    if "output_path" in raw:
        readme.output_path = str(raw["output_path"])
    if "max_length" in raw:
        val = raw["max_length"]
        if val is not None:
            if not isinstance(val, int) or isinstance(val, bool):
                raise PermanentError(
                    f"readme.max_length must be null or integer, got {type(val).__name__}"
                )
            if val <= 0:
                raise PermanentError(
                    f"readme.max_length must be positive, got {val}"
                )
        readme.max_length = val
    if "include_toc" in raw:
        readme.include_toc = bool(raw["include_toc"])
    if "include_badges" in raw:
        readme.include_badges = bool(raw["include_badges"])
    return readme


def _parse_pull_request(raw: dict, config_path: Path) -> PullRequestConfig:
    """Parse and validate the ``pull_request`` section."""
    if not isinstance(raw, dict):
        raise PermanentError(
            f"'pull_request' must be a mapping, got {type(raw).__name__}"
        )
    _warn_unknown_keys(raw, _KNOWN_PR_KEYS, "pull_request.", config_path)

    pr = PullRequestConfig()
    if "auto_merge" in raw:
        pr.auto_merge = bool(raw["auto_merge"])
    if "reviewers" in raw:
        val = raw["reviewers"]
        if not isinstance(val, list):
            raise PermanentError(
                f"pull_request.reviewers must be a list, got {type(val).__name__}"
            )
        pr.reviewers = [str(v) for v in val]
    return pr


def load_autodoc_config(
    config_path: Path | str,
    scope_path: str = ".",
) -> AutodocConfig:
    """Load and validate an ``.autodoc.yaml`` file.

    Args:
        config_path: Path to the ``.autodoc.yaml`` file.
        scope_path: Relative path to use as ``scope_path`` (set by caller).

    Returns:
        Parsed :class:`AutodocConfig` with validated values.

    Raises:
        PermanentError: If the config file contains invalid YAML or values.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        logger.info("No .autodoc.yaml found at %s, using defaults", config_path)
        return AutodocConfig(scope_path=scope_path)

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise PermanentError(f"Invalid YAML in {config_path}: {exc}") from exc

    if raw is None:
        # Empty file
        return AutodocConfig(scope_path=scope_path)

    if not isinstance(raw, dict):
        raise PermanentError(
            f".autodoc.yaml must be a mapping, got {type(raw).__name__}"
        )

    # Warn on unknown top-level keys
    _warn_unknown_keys(raw, _KNOWN_KEYS, "", config_path)

    config = AutodocConfig(scope_path=scope_path)

    # version
    if "version" in raw:
        config.version = str(raw["version"])

    # include / exclude
    if "include" in raw:
        val = raw["include"]
        if not isinstance(val, list):
            raise PermanentError(
                f"'include' must be a list, got {type(val).__name__}"
            )
        config.include = [str(v) for v in val]

    if "exclude" in raw:
        val = raw["exclude"]
        if not isinstance(val, list):
            raise PermanentError(
                f"'exclude' must be a list, got {type(val).__name__}"
            )
        config.exclude = [str(v) for v in val]

    # custom_instructions
    if "custom_instructions" in raw:
        val = raw["custom_instructions"]
        if not isinstance(val, str):
            raise PermanentError(
                f"'custom_instructions' must be a string, got {type(val).__name__}"
            )
        config.custom_instructions = val

    # Nested sections
    if "style" in raw:
        config.style = _parse_style(raw["style"], config_path)

    if "readme" in raw:
        config.readme = _parse_readme(raw["readme"], config_path)

    if "pull_request" in raw:
        config.pull_request = _parse_pull_request(raw["pull_request"], config_path)

    return config


def apply_scope_overlap_exclusions(
    configs: list[AutodocConfig],
) -> list[AutodocConfig]:
    """Auto-exclude child scope directories from parent scopes.

    When a parent scope contains child scope directories (with their own
    ``.autodoc.yaml``), those directories are added to the parent's exclude
    list to prevent duplicate documentation.

    Args:
        configs: List of configs discovered across the repository.

    Returns:
        The same list of configs, mutated so that each parent's ``exclude``
        list contains the relative paths of its child scopes.
    """
    scope_paths = {c.scope_path for c in configs}

    for config in configs:
        parent = config.scope_path
        for other_path in sorted(scope_paths):
            if other_path == parent:
                continue
            # Check if other_path is a child of parent
            if parent == ".":
                # Root is parent of everything
                child_rel = other_path
            elif other_path.startswith(parent + "/"):
                child_rel = other_path
            else:
                continue

            if child_rel not in config.exclude:
                config.exclude.append(child_rel)
                logger.info(
                    "Auto-excluded child scope '%s' from parent scope '%s'",
                    child_rel,
                    parent,
                )

    return configs
