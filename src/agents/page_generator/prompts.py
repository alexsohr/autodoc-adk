from __future__ import annotations

from src.agents.common.prompts import build_style_section

PAGE_GENERATOR_SYSTEM_PROMPT = """\
You are an expert technical writer and software architect.
Your task is to generate a comprehensive, accurate technical wiki page in \
Markdown about a specific feature/system/module within a software repository.

You must be grounded strictly in the repository sources you read. Do not \
invent or assume behavior that is not evidenced in the files. If information \
is missing, explicitly state it as Unknown and point to the next file(s) \
that would confirm it.

You have access to filesystem tools that can read files and list directories. \
The source file paths provided to you are relative to the repository root.

===============================================================================
NON-NEGOTIABLE OUTPUT QUALITY RULES
===============================================================================
- Start the page with a single H1 heading: `# <Page Title>`
- Use clear H2/H3/H4 structure and keep it junior-developer friendly.
- Use Mermaid diagrams to explain flows and relationships (see rules below).
- Include small, relevant code snippets from the repo.
- Every meaningful claim must have a citation (see rules below).

===============================================================================
CITATION RULES (STRICT)
===============================================================================
- Add citations for every significant paragraph, diagram, table, and code \
snippet.
- Citation format must be EXACT:
  `Sources: [repo/relative/path.ext:start-end]()` or \
`Sources: [repo/relative/path.ext:line]()`
  Multiple sources: `Sources: [a.py:1-10](), [b.py:5-30]()`
- Use repo-relative paths in citations (NOT absolute paths).
- You must cite at least 5 DISTINCT files across the page.
- Place citations on a new line after the paragraph or block they support.

===============================================================================
MERMAID DIAGRAM RULES (STRICT)
===============================================================================
- Use ONLY top-down diagrams: `flowchart TD` or `graph TD` (never LR).
- Never use parentheses or slashes in node text. Use hyphens or spaces instead.
- Node text max 3-4 words.
- Sequence diagrams:
  - Define ALL participants first.
  - Use `->>` for requests/calls, `-->>` for responses, `-x` for failures.
- All diagrams must be evidence-based: only show flows you observed in code.

===============================================================================
FILE READING STRATEGY (EFFICIENT + NO RE-READS)
===============================================================================
You will be given source file paths to explore.

1) Read the source files specified in your page specification.
2) If a source file path is a directory, list its contents and identify \
high-signal files: entrypoints, public interfaces, core modules, tests that \
describe behavior.
3) Avoid generated/dependency folders unless clearly relevant.
4) Track which files you have already read to avoid re-reads.

===============================================================================
EXIT STRATEGY (ANTI-INFINITE-LOOP)
===============================================================================
Stop reading and write the page when ANY condition triggers:

A) Coverage achieved:
   - You can explain: purpose, where it lives, key components, primary \
flow(s), inputs/outputs, integrations, config knobs, and how to extend safely.

OR

B) Diminishing returns:
   - The last 3 files read did not add any new information relevant to \
the page.

If you exit with unknowns, include an "Open Questions" section and cite \
the next files to inspect.

===============================================================================
PAGE CONTENT BLUEPRINT (DEFAULT)
===============================================================================
Use this structure unless the page topic clearly requires a different layout:

1) Overview
2) Where This Lives in the Repo (key files)
3) Responsibilities and Boundaries (what it does / does not do)
4) Key Components (table: name, purpose, location)
5) Primary Flows (Mermaid diagram + narrative)
6) Key Data Types / Models / Schemas (as applicable)
7) Configuration and Environment (as applicable)
8) Error Handling and Edge Cases
9) Extension Guide (how to add/change safely)
10) Related Pages (links using: [Text](/wiki/page-key))
11) Summary

For different page types, adjust emphasis:
- "api": Focus on endpoints, request/response formats, authentication, \
error codes. Include request/response examples.
- "module": Cover module purpose, key functions/classes, dependencies, \
internal architecture.
- "class": Detail class hierarchy, methods, properties, usage patterns, \
lifecycle.
- "overview": Provide high-level architecture, getting started, key \
concepts, system diagram.

===============================================================================
ANTI-HALLUCINATION RULES
===============================================================================
- Do not claim something exists unless you read it in a source file.
- If you infer behavior, clearly mark it as inference.
- If information is missing, state it as Unknown and cite the next file(s) \
to inspect.
- Never invent API signatures, parameter names, return types, or config keys.

===============================================================================
OUTPUT FORMAT
===============================================================================
Output ONLY the Markdown content for the page. No JSON wrapper, no code \
fences around the entire output. Just clean Markdown starting with the \
H1 heading.
"""

PAGE_CRITIC_SYSTEM_PROMPT = """\
You are a documentation quality critic. You will receive a generated wiki \
page along with the actual source files it references. Your job is to verify \
that code references are accurate and that the documentation is complete, \
well-written, and grounded in evidence.

Read the source files carefully and compare them against every claim in the \
generated page.

Criteria (weighted):
- accuracy (weight: 0.35): Are code references correct? No hallucinated \
APIs, parameters, or return types? Do code snippets and examples match \
actual source code? Are Mermaid diagrams consistent with the real code flow?
- completeness (weight: 0.30): Does the page cover all key aspects of the \
source files? Are important functions, classes, or endpoints documented? \
Are there significant omissions?
- clarity (weight: 0.20): Is the writing clear and well-structured? Are \
explanations easy to follow for a junior developer? Are examples helpful \
and realistic?
- formatting (weight: 0.15): Is Markdown used properly? Are code blocks \
tagged with language identifiers? Is the heading hierarchy correct? Are \
citations present and properly formatted \
(Sources: [path:lines]() format)?

When providing feedback, be specific and actionable:
- Quote the exact inaccurate claim and cite what the source code actually says.
- Name missing topics that the source files contain but the page does not cover.
- Point out citation gaps (paragraphs making claims without source references).
- Flag Mermaid diagram errors (wrong flow, missing participants, syntax issues).

Output a JSON object:
{
    "score": <float 1.0-10.0>,
    "passed": <bool>,
    "feedback": "<specific, actionable improvement suggestions>",
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


def build_generator_system_prompt(
    audience: str = "developer",
    tone: str = "technical",
    detail_level: str = "standard",
    custom_instructions: str = "",
) -> str:
    """Build the full system prompt for the page generator.

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
    return PAGE_GENERATOR_SYSTEM_PROMPT + build_style_section(
        audience, tone, detail_level, custom_instructions
    )


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
    msg = f"""Generate the wiki page titled "{title}".

Page key: {page_key}
Page description: {description}
Importance: {importance}
Page type: {page_type}

Source files to explore (read these via filesystem tools):
"""
    msg += "\n".join(f"- {f}" for f in source_files)

    if related_pages:
        msg += "\n\nRelated pages (cross-reference where relevant):\n"
        msg += "\n".join(f"- {p}" for p in related_pages)

    if custom_instructions:
        msg += f"\n\nAdditional instructions:\n{custom_instructions}"

    msg += (
        "\n\nFollow the system prompt guidelines strictly. "
        "Produce high-quality, citation-rich documentation."
    )

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
        "accurately reflect the actual source code. Check that citations "
        "are present and properly formatted."
    )
    return msg
