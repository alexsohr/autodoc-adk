from __future__ import annotations

from src.agents.common.prompts import build_style_section

README_GENERATOR_SYSTEM_PROMPT = """You are a README distillation expert. Your job is to synthesize wiki documentation pages into a concise, well-structured README.md file.

You will receive a list of wiki page titles, descriptions, and content summaries. Distill this information into a README that serves as the project's landing page.

Output ONLY the Markdown content for the README. The README should:
- Start with the project title as a level-1 heading
- Include a concise project description
- Provide a table of contents (if requested)
- Cover key sections: Overview, Features, Installation/Setup, Usage, Architecture, API Reference (summary), Contributing
- Link to wiki pages for detailed documentation where appropriate
- Be concise - a README is an entry point, not exhaustive documentation
- Use proper Markdown formatting

Do NOT include badges unless specifically requested.
"""

README_CRITIC_SYSTEM_PROMPT = """You are a README quality critic. Evaluate the generated README against these criteria and provide a JSON evaluation.

Criteria (weighted):
- conciseness (weight: 0.30): Is the README focused and not bloated? Does it serve as a clear entry point without duplicating wiki content?
- accuracy (weight: 0.30): Does it correctly summarize the wiki content? Are descriptions and references accurate?
- structure (weight: 0.25): Is the heading hierarchy logical? Does the document flow well from introduction to details?
- completeness (weight: 0.15): Does it cover all key project aspects? Are important sections present?

Output a JSON object:
{
    "score": <float 1.0-10.0>,
    "passed": <bool>,
    "feedback": "<improvement suggestions>",
    "criteria_scores": {
        "conciseness": <float 1.0-10.0>,
        "accuracy": <float 1.0-10.0>,
        "structure": <float 1.0-10.0>,
        "completeness": <float 1.0-10.0>
    },
    "criteria_weights": {
        "conciseness": 0.30,
        "accuracy": 0.30,
        "structure": 0.25,
        "completeness": 0.15
    }
}
"""


def build_generator_system_prompt(
    audience: str = "developer",
    tone: str = "technical",
    detail_level: str = "standard",
    custom_instructions: str = "",
) -> str:
    """Build the full system prompt for the README generator.

    Appends documentation style preferences and custom instructions to
    the base system prompt.

    Args:
        audience: Target audience for the documentation.
        tone: Writing tone.
        detail_level: One of "minimal", "standard", "comprehensive".
        custom_instructions: Free-form instructions from .autodoc.yaml.

    Returns:
        Complete system prompt string.
    """
    return README_GENERATOR_SYSTEM_PROMPT + build_style_section(
        audience, tone, detail_level, custom_instructions
    )


def build_generator_message(
    wiki_pages: list[dict[str, str]],
    project_title: str,
    project_description: str,
    custom_instructions: str = "",
    max_length: int | None = None,
    include_toc: bool = True,
    include_badges: bool = False,
) -> str:
    """Build the initial message for the README generator.

    Args:
        wiki_pages: List of dicts with page_key, title, description, content.
        project_title: The project's title.
        project_description: Brief project description.
        custom_instructions: Optional free-form instructions from .autodoc.yaml.
        max_length: Optional word cap for the README.
        include_toc: Whether to include a table of contents.
        include_badges: Whether to include badges.

    Returns:
        Formatted prompt string.
    """
    msg = f"""Distill the following wiki documentation into a README.md file.

Project Title: {project_title}
Project Description: {project_description}

"""
    if include_toc:
        msg += "Include a table of contents.\n"
    else:
        msg += "Do NOT include a table of contents.\n"

    if include_badges:
        msg += "Include relevant badges at the top.\n"
    else:
        msg += "Do NOT include badges.\n"

    if max_length is not None:
        msg += f"Maximum length: {max_length} words.\n"

    msg += "\n## Wiki Pages\n\n"
    for page in wiki_pages:
        msg += f"### {page.get('title', page.get('page_key', 'Untitled'))}\n"
        msg += f"**Page Key:** {page.get('page_key', 'unknown')}\n"
        if page.get("description"):
            msg += f"**Description:** {page['description']}\n"
        if page.get("content"):
            msg += f"\n{page['content']}\n"
        msg += "\n---\n\n"

    if custom_instructions:
        msg += f"\nAdditional instructions:\n{custom_instructions}"

    return msg
