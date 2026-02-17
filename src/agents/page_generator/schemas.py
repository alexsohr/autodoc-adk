from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GeneratedPage:
    """A single generated wiki page."""

    page_key: str
    title: str
    content: str  # markdown
    source_files: list[str] = field(default_factory=list)


@dataclass
class PageGeneratorInput:
    """Input data for the PageGenerator agent."""

    page_key: str
    title: str
    description: str
    importance: str  # "high", "medium", "low"
    page_type: str  # "api", "module", "class", "overview"
    source_files: list[str]
    repo_path: str
    related_pages: list[str] = field(default_factory=list)
    custom_instructions: str = ""
