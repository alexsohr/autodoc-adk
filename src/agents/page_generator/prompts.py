from __future__ import annotations

PAGE_GENERATOR_SYSTEM_PROMPT = """You are a technical documentation writer. Your job is to produce a comprehensive, accurate wiki page for a specific part of a codebase.

You will receive a page specification (title, description, type, source files) and have access to read the source files via filesystem tools. Read the relevant source files and produce high-quality documentation in Markdown format.

Output ONLY the Markdown content for the page (no JSON wrapper). The page should:
- Start with a level-1 heading matching the page title
- Include accurate code references with proper syntax highlighting
- Provide clear explanations of functionality, parameters, return values
- Include usage examples where appropriate
- Cross-reference related pages using their page_keys where relevant
- Use proper Markdown formatting (headings, code blocks, lists, tables)

For different page types:
- "api": Focus on endpoints, request/response formats, authentication, error codes
- "module": Cover module purpose, key functions/classes, dependencies
- "class": Detail class hierarchy, methods, properties, usage patterns
- "overview": Provide high-level architecture, getting started, key concepts
"""

PAGE_CRITIC_SYSTEM_PROMPT = """You are a documentation quality critic. You will receive the generated page content AND the source files it references. Verify that code references are accurate and that the documentation is complete and well-written.

Evaluate the documentation against these criteria and provide a JSON evaluation.

Criteria (weighted):
- accuracy (weight: 0.35): Are code references correct? No hallucinated APIs, parameters, or return types? Do examples match actual source code?
- completeness (weight: 0.30): Does the page cover all key aspects of the source files? Are important functions, classes, or endpoints documented?
- clarity (weight: 0.20): Is the writing clear and well-structured? Are explanations easy to follow? Are examples helpful?
- formatting (weight: 0.15): Is Markdown used properly? Are code blocks tagged with language identifiers? Is the heading hierarchy correct?

Output a JSON object:
{
    "score": <float 1.0-10.0>,
    "passed": <bool>,
    "feedback": "<improvement suggestions>",
    "criteria_scores": {
        "accuracy": <float 1.0-10.0>,
        "completeness": <float 1.0-10.0>,
        "clarity": <float 1.0-10.0>,
        "formatting": <float 1.0-10.0>
    },
    "criteria_weights": {
        "accuracy": 0.35,
        "completeness": 0.30,
        "clarity": 0.20,
        "formatting": 0.15
    }
}
"""


def build_generator_message(
    page_key: str,
    title: str,
    description: str,
    importance: str,
    page_type: str,
    source_files: list[str],
    related_pages: list[str] | None = None,
    custom_instructions: str = "",
) -> str:
    """Build the initial message for the page generator.

    Args:
        page_key: Unique identifier for this page.
        title: Page title.
        description: What this page should cover.
        importance: Page importance level.
        page_type: Type of page (api, module, class, overview).
        source_files: List of source file paths to document.
        related_pages: Optional list of related page keys for cross-references.
        custom_instructions: Optional free-form instructions from .autodoc.yaml.

    Returns:
        Formatted prompt string.
    """
    msg = f"""Generate a wiki documentation page with the following specification:

Page Key: {page_key}
Title: {title}
Description: {description}
Importance: {importance}
Page Type: {page_type}

Source files to document (read these via filesystem tools):
"""
    msg += "\n".join(f"- {f}" for f in source_files)

    if related_pages:
        msg += "\n\nRelated pages (cross-reference where relevant):\n"
        msg += "\n".join(f"- {p}" for p in related_pages)

    if custom_instructions:
        msg += f"\n\nAdditional instructions:\n{custom_instructions}"

    return msg


def build_critic_message(page_content: str, source_contents: dict[str, str]) -> str:
    """Build the critic message containing both the generated page and source files.

    Args:
        page_content: The generated Markdown page content.
        source_contents: Mapping of file path to file content for source files.

    Returns:
        Formatted prompt string for the critic.
    """
    msg = "## Generated Page Content\n\n"
    msg += page_content
    msg += "\n\n---\n\n## Source Files for Verification\n\n"

    for path, content in source_contents.items():
        msg += f"### {path}\n```\n{content}\n```\n\n"

    msg += (
        "Evaluate the generated page against the source files above. "
        "Verify that all code references, API signatures, and examples "
        "accurately reflect the actual source code."
    )
    return msg
