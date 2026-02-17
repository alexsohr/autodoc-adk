from __future__ import annotations


def build_style_section(
    audience: str = "developer",
    tone: str = "technical",
    detail_level: str = "standard",
    custom_instructions: str = "",
) -> str:
    """Build the style and instructions section for system prompts.

    This section is appended to generator system prompts to inject
    documentation style preferences and custom instructions from
    ``.autodoc.yaml``.

    Args:
        audience: Target audience for the documentation.
        tone: Writing tone (e.g. "technical", "casual", "formal").
        detail_level: One of "minimal", "standard", "comprehensive".
        custom_instructions: Free-form instructions from .autodoc.yaml.

    Returns:
        Formatted string to append to a system prompt.
    """
    parts: list[str] = []

    parts.append("\n\n## Documentation Style")
    parts.append(f"- Target audience: {audience}")
    parts.append(f"- Writing tone: {tone}")
    parts.append(f"- Detail level: {detail_level}")

    if detail_level == "minimal":
        parts.append("- Keep explanations brief and focus on essentials only")
    elif detail_level == "comprehensive":
        parts.append("- Provide thorough explanations with examples and edge cases")

    if custom_instructions:
        parts.append(f"\n## Custom Instructions\n{custom_instructions}")

    return "\n".join(parts)
