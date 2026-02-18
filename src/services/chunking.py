from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken

from src.config.settings import get_settings

# Module-level encoder; tiktoken caches internally, but we avoid repeated
# lookups by keeping a reference.
_encoder = tiktoken.get_encoding("cl100k_base")

# Regex for fenced code blocks (``` with optional language tag).
_FENCED_CODE_RE = re.compile(r"^```", re.MULTILINE)

# Heading line regex (ATX-style: 1-6 leading '#' characters).
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)", re.MULTILINE)


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


# ---------------------------------------------------------------------------
# Stage 1 helpers — heading-aware splitting
# ---------------------------------------------------------------------------

@dataclass
class _Section:
    """Internal representation of a heading-delimited section."""

    content: str
    heading_path: list[str]
    heading_level: int
    start_char: int


def _split_by_headings(content: str) -> list[_Section]:
    """Split *content* into sections delimited by ATX headings.

    Fenced code blocks are treated as opaque — headings inside them are
    ignored.  Tables are never split because they don't contain heading
    markers.
    """
    sections: list[_Section] = []

    # First, identify regions that are inside fenced code blocks so we can
    # skip heading matches within them.
    code_regions: list[tuple[int, int]] = []
    fence_iter = _FENCED_CODE_RE.finditer(content)
    fences = list(fence_iter)
    i = 0
    while i < len(fences) - 1:
        open_fence = fences[i]
        close_fence = fences[i + 1]
        code_regions.append((open_fence.start(), close_fence.end()))
        i += 2

    # If there's a trailing unclosed fence, treat everything from it to EOF
    # as a code region (so we never split inside it).
    if len(fences) % 2 == 1:
        code_regions.append((fences[-1].start(), len(content)))

    def _inside_code(pos: int) -> bool:
        return any(start <= pos < end for start, end in code_regions)

    # Collect heading positions that are NOT inside code blocks.
    heading_positions: list[tuple[int, int, str]] = []  # (match_start, level, title)
    for m in _HEADING_RE.finditer(content):
        if not _inside_code(m.start()):
            level = len(m.group(1))
            title = m.group(2).strip()
            heading_positions.append((m.start(), level, title))

    if not heading_positions:
        # No headings — everything is preamble.
        return [
            _Section(
                content=content,
                heading_path=[],
                heading_level=0,
                start_char=0,
            )
        ]

    # Build heading_path stack: a mapping from level to the current heading
    # title at that level.  When a new heading is encountered, we set it and
    # clear all deeper levels.
    heading_stack: dict[int, str] = {}

    def _build_heading_path(level: int, title: str) -> list[str]:
        heading_stack[level] = title
        # Remove deeper levels.
        for deeper in list(heading_stack):
            if deeper > level:
                del heading_stack[deeper]
        return [heading_stack[lv] for lv in sorted(heading_stack)]

    # Preamble (content before first heading).
    first_pos = heading_positions[0][0]
    if first_pos > 0:
        preamble = content[:first_pos]
        if preamble.strip():
            sections.append(
                _Section(
                    content=preamble,
                    heading_path=[],
                    heading_level=0,
                    start_char=0,
                )
            )

    # Each heading starts a new section that runs until the next heading.
    for idx, (pos, level, title) in enumerate(heading_positions):
        end = heading_positions[idx + 1][0] if idx + 1 < len(heading_positions) else len(content)

        section_content = content[pos:end]
        path = _build_heading_path(level, title)

        sections.append(
            _Section(
                content=section_content,
                heading_path=list(path),
                heading_level=level,
                start_char=pos,
            )
        )

    return sections


# ---------------------------------------------------------------------------
# Stage 2 — recursive splitting of oversized sections
# ---------------------------------------------------------------------------

_RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", " "]


def _recursive_split(
    text: str,
    max_tokens: int,
    separators: list[str] | None = None,
) -> list[str]:
    """Recursively split *text* into pieces that each fit within *max_tokens*.

    Tries each separator in order; the first separator that produces a split
    is used.  If no separator works, the text is left as-is (a hard edge case
    where a single "word" exceeds *max_tokens*).

    This function does NOT apply overlap — that is handled by the caller.
    """
    if _count_tokens(text) <= max_tokens:
        return [text]

    if separators is None:
        separators = list(_RECURSIVE_SEPARATORS)

    if not separators:
        # Can't split further.
        return [text]

    sep = separators[0]
    remaining_separators = separators[1:]

    parts = text.split(sep)
    if len(parts) == 1:
        # This separator didn't help — try the next one.
        return _recursive_split(text, max_tokens, remaining_separators)

    # Greedily merge consecutive parts until adding the next would exceed
    # max_tokens.
    chunks: list[str] = []
    current = parts[0]
    for part in parts[1:]:
        candidate = current + sep + part
        if _count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            # Flush current.
            if current.strip():
                chunks.append(current)
            current = part

    if current.strip():
        chunks.append(current)

    # Any individual chunk that is still too large gets split with the next
    # separator.
    result: list[str] = []
    for chunk in chunks:
        if _count_tokens(chunk) <= max_tokens:
            result.append(chunk)
        else:
            result.extend(_recursive_split(chunk, max_tokens, remaining_separators))

    return result


def _apply_overlap(fragments: list[str], overlap_tokens: int) -> list[str]:
    """Return new fragments where each one (except the first) is prefixed with
    the trailing *overlap_tokens* worth of text from the previous fragment.

    Overlap is computed at the token level and decoded back to text to ensure
    accurate token counts.
    """
    if overlap_tokens <= 0 or len(fragments) <= 1:
        return fragments

    result: list[str] = [fragments[0]]
    for i in range(1, len(fragments)):
        prev_tokens = _encoder.encode(fragments[i - 1])
        overlap_toks = prev_tokens[-overlap_tokens:] if len(prev_tokens) > overlap_tokens else prev_tokens
        overlap_text = _encoder.decode(overlap_toks)
        result.append(overlap_text + fragments[i])
    return result


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

    **Stage 1** splits by ATX headings while preserving fenced code blocks and
    tables.  **Stage 2** recursively splits any section that exceeds
    *max_tokens* using paragraph / line / sentence / word boundaries, then
    applies *overlap_tokens* token overlap between consecutive sub-chunks and
    merges any sub-chunk smaller than *min_tokens* with its neighbour.

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

    sections = _split_by_headings(content)
    results: list[ChunkResult] = []

    for section in sections:
        section_tokens = _count_tokens(section.content)

        if section_tokens <= max_tokens:
            # Section fits in one chunk.
            results.append(
                ChunkResult(
                    content=section.content,
                    heading_path=section.heading_path,
                    heading_level=section.heading_level,
                    token_count=section_tokens,
                    start_char=section.start_char,
                    end_char=section.start_char + len(section.content),
                    has_code=_contains_code_block(section.content),
                )
            )
        else:
            # Stage 2: recursive split.
            fragments = _recursive_split(section.content, max_tokens)
            fragments = _apply_overlap(fragments, overlap_tokens)
            fragments = _merge_small_chunks(fragments, min_tokens)

            # Compute start_char/end_char for each sub-chunk.  Because overlap
            # text is prepended (duplicated from the previous chunk), the
            # "original" portion of each sub-chunk doesn't map cleanly to a
            # contiguous span.  We track a running cursor over the *original*
            # section content to approximate positions.
            cursor = section.start_char
            for frag in fragments:
                frag_tokens = _count_tokens(frag)
                # Find where this fragment (minus overlap prefix) starts in the
                # original content.  We search forward from cursor.
                # For the first fragment there is no overlap prefix.
                frag_start = content.find(frag, cursor)
                if frag_start == -1:
                    # Overlap-prefixed fragment won't be found verbatim.
                    # Fall back to using cursor.
                    frag_start = cursor
                frag_end = frag_start + len(frag)

                results.append(
                    ChunkResult(
                        content=frag,
                        heading_path=section.heading_path,
                        heading_level=section.heading_level,
                        token_count=frag_tokens,
                        start_char=frag_start,
                        end_char=frag_end,
                        has_code=_contains_code_block(frag),
                    )
                )
                cursor = frag_end

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
