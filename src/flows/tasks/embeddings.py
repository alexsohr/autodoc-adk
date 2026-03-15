from __future__ import annotations

import logging
import uuid

from prefect import task

from src.config.settings import get_settings
from src.database.models.page_chunk import PageChunk
from src.services.chunking import ChunkResult, chunk_markdown_from_settings
from src.services.context_enrichment import generate_chunk_contexts
from src.services.embedding import generate_embeddings as embed_texts

logger = logging.getLogger(__name__)


def _breadcrumb_context(page_title: str, heading_path: list[str]) -> str:
    """Build a cheap breadcrumb-style context for non-split chunks."""
    heading_joined = " > ".join(heading_path) if heading_path else "Root"
    return f"From {page_title}, section: {heading_joined}."


@task(name="generate_embeddings", retries=2, retry_delay_seconds=10, timeout_seconds=1200)
async def generate_embeddings_task(
    *,
    wiki_structure_id: uuid.UUID,
) -> int:
    """Generate embeddings for all pages in a wiki structure.

    Pipeline:
      Stage 1: Chunk all pages
      Stage 2: Generate context prefixes per chunk (contextual enrichment)
      Stage 3: Embed enriched content (context_prefix + content)
      Stage 4: Build PageChunk records
      Stage 5: Persist to DB

    Creates its own DB session internally for cross-process execution.

    Returns the total number of chunks created.
    """
    from src.database.engine import get_session_factory
    from src.database.repos.wiki_repo import WikiRepo

    settings = get_settings()
    session_factory = get_session_factory()
    async with session_factory() as session:
        wiki_repo = WikiRepo(session)

        pages = await wiki_repo.get_pages_for_structure(wiki_structure_id)
        if not pages:
            logger.info("No pages found for structure %s — skipping embeddings", wiki_structure_id)
            return 0

        # Stage 1: Chunk all pages
        all_chunks: list[tuple[uuid.UUID, int, ChunkResult]] = []
        for page in pages:
            page_chunks = chunk_markdown_from_settings(page.content)
            for idx, chunk in enumerate(page_chunks):
                all_chunks.append((page.id, idx, chunk))

        total_chunks = len(all_chunks)
        logger.info(
            "Chunking %d pages for structure %s — generated %d chunks",
            len(pages),
            wiki_structure_id,
            total_chunks,
        )

        if total_chunks == 0:
            logger.info("No chunks produced — skipping embedding and DB insert")
            return 0

        # Stage 2: Generate context prefixes
        contexts: list[str | None] = [None] * total_chunks

        if settings.CONTEXT_ENABLED:
            logger.info("Generating context prefixes for %d chunks", total_chunks)

            # Build a mapping from global index to (page, chunk)
            page_title_map: dict[uuid.UUID, str] = {p.id: p.title for p in pages}

            # Group chunks by (page_id, section_content) to identify sections
            section_groups: dict[tuple[uuid.UUID, str], list[tuple[int, ChunkResult]]] = {}
            for global_idx, (page_id, _chunk_idx, chunk) in enumerate(all_chunks):
                key = (page_id, chunk.section_content)
                section_groups.setdefault(key, []).append((global_idx, chunk))

            for (page_id, _section_content), section_chunks in section_groups.items():
                page_title = page_title_map[page_id]

                if len(section_chunks) == 1:
                    # Section was not split — cheap breadcrumb context
                    global_idx, chunk = section_chunks[0]
                    contexts[global_idx] = _breadcrumb_context(page_title, chunk.heading_path)
                else:
                    # Section was recursively split — LLM-generated context
                    chunk_texts = [c.content for _, c in section_chunks]
                    heading_paths = [c.heading_path for _, c in section_chunks]

                    generated = await generate_chunk_contexts(
                        chunks=chunk_texts,
                        section_content=_section_content,
                        page_title=page_title,
                        heading_paths=heading_paths,
                    )

                    for (global_idx, _), ctx in zip(section_chunks, generated, strict=True):
                        contexts[global_idx] = ctx

            context_count = sum(1 for c in contexts if c is not None)
            logger.info(
                "Generated %d/%d context prefixes for structure %s",
                context_count,
                total_chunks,
                wiki_structure_id,
            )

        # Stage 3: Embed enriched content (context_prefix + content)
        chunk_texts = []
        for i, (_, _, chunk) in enumerate(all_chunks):
            ctx = contexts[i]
            if ctx:
                chunk_texts.append(f"{ctx} {chunk.content}")
            else:
                chunk_texts.append(chunk.content)

        logger.info("Embedding %d chunks for structure %s", total_chunks, wiki_structure_id)
        vectors = await embed_texts(chunk_texts)

        # Stage 4: Build PageChunk ORM objects
        chunk_records: list[PageChunk] = []
        for (page_id, chunk_index, chunk_result), embedding, context_prefix in zip(
            all_chunks, vectors, contexts, strict=True
        ):
            record = PageChunk(
                wiki_page_id=page_id,
                chunk_index=chunk_index,
                content=chunk_result.content,
                context_prefix=context_prefix,
                content_embedding=embedding,
                heading_path=chunk_result.heading_path,
                heading_level=chunk_result.heading_level,
                token_count=chunk_result.token_count,
                start_char=chunk_result.start_char,
                end_char=chunk_result.end_char,
                has_code=chunk_result.has_code,
            )
            chunk_records.append(record)

        # Stage 5: Persist to DB
        await wiki_repo.create_chunks(chunk_records)
        await session.commit()

        logger.info(
            "Saved %d chunks to DB for structure %s",
            total_chunks,
            wiki_structure_id,
        )

    return total_chunks
