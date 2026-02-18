from __future__ import annotations

from src.agents.common.prompts import build_style_section

STRUCTURE_GENERATOR_SYSTEM_PROMPT = """You are a documentation structure architect. Your job is to analyze a code repository and design the optimal wiki documentation structure.

You will be given a list of files in the repository and have access to read them via filesystem tools. Analyze the codebase and produce a JSON wiki structure specification.

Output a JSON object with this schema:
{
    "title": "Project Title",
    "description": "Brief project description",
    "sections": [
        {
            "title": "Section Title",
            "description": "Section description",
            "pages": [
                {
                    "page_key": "unique-page-key",
                    "title": "Page Title",
                    "description": "What this page covers",
                    "importance": "high|medium|low",
                    "page_type": "api|module|class|overview",
                    "source_files": ["src/file1.py", "src/file2.py"],
                    "related_pages": ["other-page-key"]
                }
            ],
            "subsections": []
        }
    ]
}

Guidelines:
- Create a logical hierarchy of sections and pages
- Every source file should be covered by at least one page
- Use meaningful page_keys (lowercase, hyphenated)
- Mark overview pages as importance "high"
- Group related functionality together
- Keep page count reasonable (1 page per major component/module)
"""

STRUCTURE_CRITIC_SYSTEM_PROMPT = """You are a documentation structure critic. Evaluate the proposed wiki structure against these criteria and provide a JSON evaluation.

Criteria (weighted):
- coverage (weight: 0.35): Does the structure cover all important parts of the codebase? Are any significant modules/components missing?
- organization (weight: 0.30): Is the hierarchy logical? Are related topics grouped sensibly?
- granularity (weight: 0.20): Is the page count appropriate? Not too many (fragmented) or too few (monolithic)?
- clarity (weight: 0.15): Are titles and descriptions clear and informative?

Output a JSON object:
{
    "score": <float 1.0-10.0>,
    "passed": <bool>,
    "feedback": "<improvement suggestions>",
    "criteria_scores": {
        "coverage": <float 1.0-10.0>,
        "organization": <float 1.0-10.0>,
        "granularity": <float 1.0-10.0>,
        "clarity": <float 1.0-10.0>
    },
    "criteria_weights": {
        "coverage": 0.35,
        "organization": 0.30,
        "granularity": 0.20,
        "clarity": 0.15
    }
}
"""


def build_generator_system_prompt(
    audience: str = "developer",
    tone: str = "technical",
    detail_level: str = "standard",
    custom_instructions: str = "",
) -> str:
    """Build the full system prompt for the structure generator.

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
    return STRUCTURE_GENERATOR_SYSTEM_PROMPT + build_style_section(
        audience, tone, detail_level, custom_instructions
    )


def build_generator_message(file_list: list[str], custom_instructions: str = "") -> str:
    """Build the initial message for the structure generator.

    Args:
        file_list: List of file paths in the repository.
        custom_instructions: Optional free-form instructions from .autodoc.yaml.

    Returns:
        Formatted prompt string.
    """
    msg = "Analyze the following repository files and produce a wiki structure specification.\n\nFiles:\n"
    msg += "\n".join(f"- {f}" for f in file_list)
    if custom_instructions:
        msg += f"\n\nAdditional instructions:\n{custom_instructions}"
    return msg
