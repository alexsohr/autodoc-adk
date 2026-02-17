from __future__ import annotations

import logging

import litellm

from src.config.settings import get_settings
from src.errors import TransientError

logger = logging.getLogger(__name__)


async def generate_embeddings(
    texts: list[str],
    *,
    model: str | None = None,
    dimensions: int | None = None,
    batch_size: int | None = None,
) -> list[list[float]]:
    """Batch-embed text chunks using a configurable embedding model.

    Texts are processed in batches of ``batch_size`` (default from
    ``EMBEDDING_BATCH_SIZE`` setting) to stay within provider rate / payload
    limits.

    Args:
        texts: The text chunks to embed.
        model: Embedding model identifier.  Falls back to
            ``EMBEDDING_MODEL`` from settings when *None*.
        dimensions: Output vector dimensionality.  Falls back to
            ``EMBEDDING_DIMENSIONS`` from settings when *None*.
        batch_size: Number of texts per API call.  Falls back to
            ``EMBEDDING_BATCH_SIZE`` from settings when *None*.

    Returns:
        A list of embedding vectors (each a ``list[float]``), one per input
        text, preserving input order.

    Raises:
        TransientError: On any litellm / provider API failure.
    """
    if not texts:
        return []

    settings = get_settings()
    model = model or settings.EMBEDDING_MODEL
    dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
    batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE

    embeddings: list[list[float]] = []
    total_batches = (len(texts) + batch_size - 1) // batch_size

    for batch_idx in range(total_batches):
        start = batch_idx * batch_size
        end = start + batch_size
        batch = texts[start:end]

        logger.debug(
            "Embedding batch %d/%d (%d texts)",
            batch_idx + 1,
            total_batches,
            len(batch),
        )

        try:
            response = await litellm.aembedding(
                model=model,
                input=batch,
                dimensions=dimensions,
            )
        except Exception as exc:
            raise TransientError(
                f"Embedding batch {batch_idx + 1}/{total_batches} failed: {exc}"
            ) from exc

        # litellm returns data sorted by index; sort explicitly to be safe.
        batch_embeddings = sorted(response.data, key=lambda d: d["index"])
        embeddings.extend(item["embedding"] for item in batch_embeddings)

    return embeddings


async def embed_query(
    query: str,
    *,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    """Embed a single text string (convenience wrapper for search queries).

    Args:
        query: The text to embed.
        model: Embedding model identifier (falls back to settings).
        dimensions: Output vector dimensionality (falls back to settings).

    Returns:
        A single embedding vector as ``list[float]``.

    Raises:
        TransientError: On any litellm / provider API failure.
    """
    vectors = await generate_embeddings(
        [query], model=model, dimensions=dimensions, batch_size=1
    )
    return vectors[0]
