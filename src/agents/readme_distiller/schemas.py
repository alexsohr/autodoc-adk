from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReadmeOutput:
    """Generated README content."""

    content: str  # markdown README


@dataclass
class ReadmeDistillerInput:
    """Input data for the ReadmeDistiller agent."""

    wiki_pages: list[dict[str, str]]  # list of {page_key, title, description, content}
    project_title: str
    project_description: str
    custom_instructions: str = ""
    max_length: int | None = None  # word cap
    include_toc: bool = True
    include_badges: bool = False
    style_audience: str = "developer"
    style_tone: str = "technical"
    style_detail_level: str = "standard"
