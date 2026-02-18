from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PageSpec:
    """Specification for a single wiki page."""

    page_key: str  # e.g. "api-authentication"
    title: str
    description: str
    importance: str  # "high", "medium", "low"
    page_type: str  # "api", "module", "class", "overview"
    source_files: list[str] = field(default_factory=list)
    related_pages: list[str] = field(default_factory=list)


@dataclass
class SectionSpec:
    """A section in the wiki structure containing pages and subsections."""

    title: str
    description: str = ""
    pages: list[PageSpec] = field(default_factory=list)
    subsections: list[SectionSpec] = field(default_factory=list)


@dataclass
class WikiStructureSpec:
    """Complete wiki structure specification output by StructureExtractor."""

    title: str
    description: str
    sections: list[SectionSpec] = field(default_factory=list)


@dataclass
class StructureExtractorInput:
    """Input data for the StructureExtractor agent."""

    file_list: list[str]
    repo_path: str
    readme_content: str = ""
    custom_instructions: str = ""
    style_audience: str = "developer"
    style_tone: str = "technical"
    style_detail_level: str = "standard"
