from __future__ import annotations

import logging
import uuid

from prefect import task

from src.database.models.page_chunk import PageChunk
from src.database.repos.wiki_repo import WikiRepo
from src.services.chunking import ChunkResult, chunk_markdown_from_settings
from src.services.embedding import generate_embeddings as embed_texts

logger = logging.getLogger(__name__)


@task(name="generate_embeddings", retries=2, retry_delay_seconds=10, timeout_seconds=600)
async def generate_embeddings_task(
    *,
    wiki_structure_id: uuid.UUID,
    wiki_repo: WikiRepo,
) -> int:
    """Generate embeddings for all pages in a wiki structure.

    Loads all wiki pages for the given structure, chunks each page's
    markdown content, embeds all chunks in a single batch call, and
    persists the resulting PageChunk records to the database.

    Returns the total number of chunks created.
    """
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

    # Stage 2: Embed all chunk texts in one batch call
    chunk_texts = [chunk.content for _, _, chunk in all_chunks]
    logger.info("Embedding %d chunks for structure %s", total_chunks, wiki_structure_id)
    vectors = await embed_texts(chunk_texts)

    # Stage 3: Build PageChunk ORM objects
    chunk_records: list[PageChunk] = []
    for (page_id, chunk_index, chunk_result), embedding in zip(all_chunks, vectors, strict=True):
        record = PageChunk(
            wiki_page_id=page_id,
            chunk_index=chunk_index,
            content=chunk_result.content,
            content_embedding=embedding,
            heading_path=chunk_result.heading_path,
            heading_level=chunk_result.heading_level,
            token_count=chunk_result.token_count,
            start_char=chunk_result.start_char,
            end_char=chunk_result.end_char,
            has_code=chunk_result.has_code,
        )
        chunk_records.append(record)

    # Stage 4: Persist to DB
    await wiki_repo.create_chunks(chunk_records)
    logger.info(
        "Saved %d chunks to DB for structure %s",
        total_chunks,
        wiki_structure_id,
    )

    return total_chunks
