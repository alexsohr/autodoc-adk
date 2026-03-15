from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.config.settings import get_settings

# Module-level encoder; tiktoken caches internally, but we avoid repeated
# lookups by keeping a reference.
_encoder = tiktoken.get_encoding("cl100k_base")

# Regex for fenced code blocks (``` with optional language tag).
_FENCED_CODE_RE = re.compile(r"^```", re.MULTILINE)

# Headers to split on (levels 1-4).
_HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


def _count_tokens(text: str) -> int:
    """Return the token count for *text* using cl100k_base."""
    return len(_encoder.encode(text))


def _contains_code_block(text: str) -> bool:
    """Return True if *text* contains at least one fenced code block delimiter pair."""
    fences = _FENCED_CODE_RE.findall(text)
    # A complete code block requires an even number of fences (>= 2).
    # A single fence means the block is unclosed (still counts as containing code).
    return len(fences) >= 1


# ---------------------------------------------------------------------------
# ChunkResult
# ---------------------------------------------------------------------------

@dataclass
class ChunkResult:
    """A single chunk produced by :func:`chunk_markdown`."""

    content: str
    heading_path: list[str] = field(default_factory=list)
    heading_level: int = 0
    token_count: int = 0
    start_char: int = 0
    end_char: int = 0
    has_code: bool = False
    section_content: str = ""


# ---------------------------------------------------------------------------
# Code-block protection
# ---------------------------------------------------------------------------

def _protect_code_blocks(content: str) -> tuple[str, list[str]]:
    """Replace fenced code blocks with unique placeholders.

    This prevents the markdown header splitter from splitting on ``#``
    characters inside fenced code blocks.
    """
    blocks: list[str] = []
    fences = list(_FENCED_CODE_RE.finditer(content))
    if not fences:
        return content, blocks

    # Pair up fence markers (open, close).
    pairs: list[tuple[int, int]] = []
    i = 0
    while i < len(fences) - 1:
        open_start = fences[i].start()
        close_match = fences[i + 1]
        close_line_end = content.find("\n", close_match.start())
        close_end = close_line_end + 1 if close_line_end != -1 else len(content)
        pairs.append((open_start, close_end))
        i += 2

    # Handle unclosed fence — treat everything from it to EOF as code.
    if len(fences) % 2 == 1:
        pairs.append((fences[-1].start(), len(content)))

    # Build result with placeholders.
    result_parts: list[str] = []
    last_end = 0
    for idx, (start, end) in enumerate(pairs):
        result_parts.append(content[last_end:start])
        blocks.append(content[start:end])
        result_parts.append(f"<<CODE_BLOCK_{idx}>>")
        last_end = end
    result_parts.append(content[last_end:])

    return "".join(result_parts), blocks


def _restore_code_blocks(text: str, blocks: list[str]) -> str:
    """Replace placeholders with original code blocks."""
    result = text
    for idx, block in enumerate(blocks):
        result = result.replace(f"<<CODE_BLOCK_{idx}>>", block)
    return result


# ---------------------------------------------------------------------------
# Merge small chunks
# ---------------------------------------------------------------------------

def _merge_small_chunks(
    fragments: list[str],
    min_tokens: int,
) -> list[str]:
    """Merge fragments smaller than *min_tokens* with their nearest neighbour."""
    if not fragments:
        return fragments

    merged: list[str] = [fragments[0]]
    for frag in fragments[1:]:
        if _count_tokens(merged[-1]) < min_tokens:
            # Previous chunk is too small — merge this fragment into it.
            merged[-1] = merged[-1] + frag
        elif _count_tokens(frag) < min_tokens:
            # This fragment is too small — merge into previous.
            merged[-1] = merged[-1] + frag
        else:
            merged.append(frag)

    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_markdown(
    content: str,
    *,
    max_tokens: int = 512,
    overlap_tokens: int = 50,
    min_tokens: int = 50,
) -> list[ChunkResult]:
    """Split markdown *content* into semantically meaningful chunks.

    Uses a two-stage pipeline:

    1. **MarkdownHeaderTextSplitter** splits at ATX headings (``#``..``####``)
       with code-block protection to avoid splitting inside fenced code.
    2. **RecursiveCharacterTextSplitter** further splits any section that
       exceeds *max_tokens*, applying *overlap_tokens* overlap between
       consecutive sub-chunks.  Sub-chunks smaller than *min_tokens* are
       merged with their neighbour.

    Args:
        content: The full markdown page content.
        max_tokens: Maximum tokens per chunk (default 512).
        overlap_tokens: Token overlap between consecutive sub-chunks produced
            by recursive splitting (default 50).
        min_tokens: Minimum tokens for a chunk — smaller chunks are merged
            with a neighbour (default 50).

    Returns:
        A list of :class:`ChunkResult` instances ordered by their position in
        the original content.
    """
    if not content or not content.strip():
        return []

    # Stage 1: Protect code blocks from header splitting.
    protected, code_blocks = _protect_code_blocks(content)

    # Stage 2: Split by headers.
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=_HEADERS_TO_SPLIT_ON,
        strip_headers=False,
    )
    sections = header_splitter.split_text(protected)

    # Fallback: if the splitter produced nothing, treat entire content as one chunk.
    if not sections:
        restored = _restore_code_blocks(protected, code_blocks)
        return [
            ChunkResult(
                content=restored,
                token_count=_count_tokens(restored),
                start_char=0,
                end_char=len(content),
                has_code=_contains_code_block(restored),
                section_content=restored,
            )
        ]

    # Stage 3: Recursive split oversized sections + merge small chunks.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_tokens,
        chunk_overlap=overlap_tokens,
        length_function=_count_tokens,
        separators=["\n\n", "\n", ". ", " "],
    )

    results: list[ChunkResult] = []
    cursor = 0

    for section_doc in sections:
        section_text = section_doc.page_content
        metadata = section_doc.metadata

        # Build heading path from metadata.
        heading_path: list[str] = []
        heading_level = 0
        for key in ["h1", "h2", "h3", "h4"]:
            if key in metadata:
                heading_path.append(metadata[key])
                heading_level = int(key[1])

        # Restore code blocks for section content field.
        section_restored = _restore_code_blocks(section_text, code_blocks)

        # Split section if too large.
        if _count_tokens(section_text) > max_tokens:
            sub_texts = text_splitter.split_text(section_text)
            sub_texts = _merge_small_chunks(sub_texts, min_tokens)
        else:
            sub_texts = [section_text]

        # Build ChunkResult for each sub-text.
        for sub_text in sub_texts:
            restored = _restore_code_blocks(sub_text, code_blocks)

            # Find position in original content.
            found_pos = content.find(restored, cursor)
            if found_pos == -1:
                # Langchain may normalise whitespace (trailing spaces, etc.).
                # Try the first line stripped as an anchor.
                first_line = restored.split("\n", 1)[0].strip()
                if first_line:
                    found_pos = content.find(first_line, cursor)
            if found_pos == -1 or found_pos < cursor:
                found_pos = cursor
            start_char = found_pos
            end_char = start_char + len(restored)

            results.append(
                ChunkResult(
                    content=restored,
                    heading_path=list(heading_path),
                    heading_level=heading_level,
                    token_count=_count_tokens(restored),
                    start_char=start_char,
                    end_char=end_char,
                    has_code=_contains_code_block(restored),
                    section_content=section_restored,
                )
            )
            cursor = end_char

    return results


def chunk_markdown_from_settings(content: str) -> list[ChunkResult]:
    """Convenience wrapper that reads chunking parameters from application settings.

    Equivalent to calling :func:`chunk_markdown` with the values of
    ``CHUNK_MAX_TOKENS``, ``CHUNK_OVERLAP_TOKENS``, and ``CHUNK_MIN_TOKENS``
    from :func:`~src.config.settings.get_settings`.
    """
    settings = get_settings()
    return chunk_markdown(
        content,
        max_tokens=settings.CHUNK_MAX_TOKENS,
        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
        min_tokens=settings.CHUNK_MIN_TOKENS,
    )
