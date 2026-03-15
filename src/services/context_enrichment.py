"""Contextual enrichment for chunk embeddings.

Generates short LLM-produced context snippets that are prepended to chunks
before embedding, improving search retrieval accuracy by 35-67% (per
Anthropic's contextual retrieval research).
"""

from __future__ import annotations

import asyncio
import logging

import litellm

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


async def generate_chunk_contexts(
    chunks: list[str],
    section_content: str,
    page_title: str,
    heading_paths: list[list[str]],
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    concurrency: int | None = None,
) -> list[str | None]:
    """Generate contextual enrichment snippets for a batch of chunks.

    Each chunk receives a short context (2-3 sentences) situating it within
    its parent section for improved search retrieval.

    Args:
        chunks: Chunk text strings (all from the same section).
        section_content: The full section text the chunks were split from.
        page_title: Title of the wiki page.
        heading_paths: Heading breadcrumb for each chunk.
        model: LLM model (falls back to ``CONTEXT_MODEL`` or ``DEFAULT_MODEL``).
        max_tokens: Max output tokens (falls back to ``CONTEXT_MAX_TOKENS``).
        concurrency: Parallel LLM calls (falls back to ``CONTEXT_CONCURRENCY``).

    Returns:
        A list of context strings, one per chunk.  ``None`` entries indicate
        the LLM call failed for that chunk (caller should fall back to
        embedding the raw content).
    """
    settings = get_settings()
    model = model or settings.CONTEXT_MODEL or settings.DEFAULT_MODEL
    max_tokens = max_tokens or settings.CONTEXT_MAX_TOKENS
    concurrency = concurrency or settings.CONTEXT_CONCURRENCY

    semaphore = asyncio.Semaphore(concurrency)

    async def _generate_one(chunk: str, heading_path: list[str]) -> str | None:
        heading_joined = " > ".join(heading_path) if heading_path else "Root"
        prompt = (
            f"<section>{section_content}</section>\n"
            f"Here is a chunk from this section:\n"
            f"<chunk>{chunk}</chunk>\n"
            f"Give a short succinct context (2-3 sentences) to situate this chunk "
            f"within the section for the purposes of improving search retrieval of the chunk.\n"
            f"Section path: {heading_joined}. Page: {page_title}.\n"
            f"Answer only with the context, nothing else."
        )

        async with semaphore:
            try:
                response = await litellm.acompletion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()
            except Exception:
                logger.warning(
                    "Context generation failed for chunk (page=%s, path=%s), "
                    "falling back to raw content",
                    page_title,
                    heading_joined,
                    exc_info=True,
                )
                return None

    tasks = [
        _generate_one(chunk, heading_path)
        for chunk, heading_path in zip(chunks, heading_paths, strict=True)
    ]

    return list(await asyncio.gather(*tasks))
