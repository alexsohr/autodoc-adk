"""Tests for the embedding service and the Prefect embeddings task."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.errors import TransientError
from src.services.chunking import ChunkResult
from src.services.embedding import embed_query, generate_embeddings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_litellm_response(embeddings: list[list[float]], *, start_index: int = 0):
    """Build a mock litellm aembedding response.

    ``response.data`` is a list of dicts with ``index`` and ``embedding`` keys,
    matching the real litellm response format used by the embedding service
    (dict-style access: ``d["index"]``, ``item["embedding"]``).
    """
    data = [
        {"index": start_index + i, "embedding": emb}
        for i, emb in enumerate(embeddings)
    ]
    resp = MagicMock()
    resp.data = data
    return resp


def _fake_settings(**overrides):
    """Return a mock Settings object with sensible defaults."""
    s = MagicMock()
    s.EMBEDDING_MODEL = overrides.get("EMBEDDING_MODEL", "text-embedding-3-large")
    s.EMBEDDING_DIMENSIONS = overrides.get("EMBEDDING_DIMENSIONS", 3072)
    s.EMBEDDING_BATCH_SIZE = overrides.get("EMBEDDING_BATCH_SIZE", 100)
    return s


# ═══════════════════════════════════════════════════════════════════════════
# Embedding service tests — src/services/embedding.py
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateEmbeddingsEmptyInput:
    """generate_embeddings([]) should return [] without calling litellm."""

    @patch("src.services.embedding.litellm")
    async def test_returns_empty_list(self, mock_litellm):
        result = await generate_embeddings([])
        assert result == []
        mock_litellm.aembedding.assert_not_called()


class TestGenerateEmbeddingsSingleBatch:
    """Texts that fit in one batch should issue exactly one aembedding call."""

    @patch("src.services.embedding.get_settings", return_value=_fake_settings(EMBEDDING_BATCH_SIZE=100))
    @patch("src.services.embedding.litellm")
    async def test_calls_aembedding_once(self, mock_litellm, _mock_settings):
        texts = ["hello", "world"]
        emb1 = [0.1, 0.2, 0.3]
        emb2 = [0.4, 0.5, 0.6]
        mock_litellm.aembedding = AsyncMock(
            return_value=_make_litellm_response([emb1, emb2])
        )

        result = await generate_embeddings(texts)

        assert result == [emb1, emb2]
        mock_litellm.aembedding.assert_awaited_once()


class TestGenerateEmbeddingsMultipleBatches:
    """When texts exceed batch_size, multiple aembedding calls should be made."""

    @patch("src.services.embedding.get_settings", return_value=_fake_settings(EMBEDDING_BATCH_SIZE=2))
    @patch("src.services.embedding.litellm")
    async def test_calls_aembedding_per_batch(self, mock_litellm, _mock_settings):
        texts = ["a", "b", "c", "d", "e"]

        batch_responses = [
            _make_litellm_response([[1.0, 2.0], [3.0, 4.0]]),           # batch 1: a, b
            _make_litellm_response([[5.0, 6.0], [7.0, 8.0]]),           # batch 2: c, d
            _make_litellm_response([[9.0, 10.0]]),                       # batch 3: e
        ]
        mock_litellm.aembedding = AsyncMock(side_effect=batch_responses)

        result = await generate_embeddings(texts)

        assert len(result) == 5
        assert mock_litellm.aembedding.await_count == 3
        assert result == [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0], [9.0, 10.0]]


class TestGenerateEmbeddingsPreservesOrder:
    """Embeddings should be returned in input order even if response data is shuffled."""

    @patch("src.services.embedding.get_settings", return_value=_fake_settings(EMBEDDING_BATCH_SIZE=100))
    @patch("src.services.embedding.litellm")
    async def test_sort_by_index(self, mock_litellm, _mock_settings):
        texts = ["first", "second", "third"]
        # Return data in reverse index order to test sort
        resp = MagicMock()
        resp.data = [
            {"index": 2, "embedding": [0.7, 0.8, 0.9]},
            {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            {"index": 1, "embedding": [0.4, 0.5, 0.6]},
        ]
        mock_litellm.aembedding = AsyncMock(return_value=resp)

        result = await generate_embeddings(texts)

        assert result == [
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9],
        ]


class TestEmbedQuery:
    """embed_query wraps generate_embeddings for a single text."""

    @patch("src.services.embedding.get_settings", return_value=_fake_settings())
    @patch("src.services.embedding.litellm")
    async def test_returns_single_vector(self, mock_litellm, _mock_settings):
        emb = [0.1, 0.2, 0.3]
        mock_litellm.aembedding = AsyncMock(
            return_value=_make_litellm_response([emb])
        )

        result = await embed_query("hello world")

        assert result == emb
        # Should call aembedding with a single-element list
        call_kwargs = mock_litellm.aembedding.call_args
        assert call_kwargs.kwargs["input"] == ["hello world"]


class TestGenerateEmbeddingsTransientError:
    """Litellm exceptions should be wrapped in TransientError."""

    @patch("src.services.embedding.get_settings", return_value=_fake_settings(EMBEDDING_BATCH_SIZE=100))
    @patch("src.services.embedding.litellm")
    async def test_wraps_exception_in_transient_error(self, mock_litellm, _mock_settings):
        mock_litellm.aembedding = AsyncMock(
            side_effect=RuntimeError("connection refused")
        )

        with pytest.raises(TransientError, match="failed"):
            await generate_embeddings(["some text"])

    @patch("src.services.embedding.get_settings", return_value=_fake_settings(EMBEDDING_BATCH_SIZE=100))
    @patch("src.services.embedding.litellm")
    async def test_original_exception_is_chained(self, mock_litellm, _mock_settings):
        original = RuntimeError("rate limit exceeded")
        mock_litellm.aembedding = AsyncMock(side_effect=original)

        with pytest.raises(TransientError) as exc_info:
            await generate_embeddings(["text"])

        assert exc_info.value.__cause__ is original


# ═══════════════════════════════════════════════════════════════════════════
# Prefect task tests — src/flows/tasks/embeddings.py
# ═══════════════════════════════════════════════════════════════════════════


def _make_mock_page(
    page_id: uuid.UUID | None = None,
    content: str = "# Test\n\nSome content",
) -> MagicMock:
    """Build a mock WikiPage-like object."""
    page = MagicMock()
    page.id = page_id or uuid.uuid4()
    page.content = content
    return page


def _make_chunk_result(
    content: str = "chunk text",
    heading_path: list[str] | None = None,
    heading_level: int = 1,
    token_count: int = 10,
    start_char: int = 0,
    end_char: int = 10,
    has_code: bool = False,
) -> ChunkResult:
    """Build a ChunkResult with configurable fields."""
    return ChunkResult(
        content=content,
        heading_path=heading_path or [],
        heading_level=heading_level,
        token_count=token_count,
        start_char=start_char,
        end_char=end_char,
        has_code=has_code,
    )


class TestGenerateEmbeddingsTaskNoPages:
    """When there are no pages for a structure, the task returns 0."""

    @patch("src.flows.tasks.embeddings.embed_texts", new_callable=AsyncMock)
    @patch("src.flows.tasks.embeddings.chunk_markdown_from_settings")
    async def test_returns_zero(self, mock_chunk, mock_embed):
        from src.flows.tasks.embeddings import generate_embeddings_task

        wiki_repo = AsyncMock()
        wiki_repo.get_pages_for_structure = AsyncMock(return_value=[])
        structure_id = uuid.uuid4()

        result = await generate_embeddings_task.fn(
            wiki_structure_id=structure_id,
            wiki_repo=wiki_repo,
        )

        assert result == 0
        mock_chunk.assert_not_called()
        mock_embed.assert_not_awaited()
        wiki_repo.create_chunks.assert_not_awaited()


class TestGenerateEmbeddingsTaskNormalFlow:
    """Normal flow: pages are chunked, embedded, and saved as PageChunk records."""

    @patch("src.flows.tasks.embeddings.embed_texts", new_callable=AsyncMock)
    @patch("src.flows.tasks.embeddings.chunk_markdown_from_settings")
    async def test_end_to_end(self, mock_chunk, mock_embed):
        from src.flows.tasks.embeddings import generate_embeddings_task

        page1_id = uuid.uuid4()
        page2_id = uuid.uuid4()
        page1 = _make_mock_page(page_id=page1_id, content="# Page 1\nContent 1")
        page2 = _make_mock_page(page_id=page2_id, content="# Page 2\nContent 2")

        chunk_a = _make_chunk_result(content="chunk-a", heading_path=["Page 1"], heading_level=1, token_count=5)
        chunk_b = _make_chunk_result(content="chunk-b", heading_path=["Page 1"], heading_level=1, token_count=8)
        chunk_c = _make_chunk_result(content="chunk-c", heading_path=["Page 2"], heading_level=1, token_count=6)

        mock_chunk.side_effect = [
            [chunk_a, chunk_b],  # page1 chunks
            [chunk_c],           # page2 chunks
        ]

        vec_a = [0.1, 0.2]
        vec_b = [0.3, 0.4]
        vec_c = [0.5, 0.6]
        mock_embed.return_value = [vec_a, vec_b, vec_c]

        wiki_repo = AsyncMock()
        wiki_repo.get_pages_for_structure = AsyncMock(return_value=[page1, page2])
        wiki_repo.create_chunks = AsyncMock()

        structure_id = uuid.uuid4()
        result = await generate_embeddings_task.fn(
            wiki_structure_id=structure_id,
            wiki_repo=wiki_repo,
        )

        # Should return total chunk count
        assert result == 3

        # embed_texts called with the 3 chunk contents
        mock_embed.assert_awaited_once_with(["chunk-a", "chunk-b", "chunk-c"])

        # create_chunks called with 3 PageChunk records
        wiki_repo.create_chunks.assert_awaited_once()
        chunk_records = wiki_repo.create_chunks.call_args[0][0]
        assert len(chunk_records) == 3

        # Verify first record
        rec0 = chunk_records[0]
        assert rec0.wiki_page_id == page1_id
        assert rec0.chunk_index == 0
        assert rec0.content == "chunk-a"
        assert rec0.content_embedding == vec_a
        assert rec0.heading_path == ["Page 1"]
        assert rec0.heading_level == 1
        assert rec0.token_count == 5

        # Verify second record belongs to page1 with index 1
        rec1 = chunk_records[1]
        assert rec1.wiki_page_id == page1_id
        assert rec1.chunk_index == 1
        assert rec1.content == "chunk-b"
        assert rec1.content_embedding == vec_b

        # Verify third record belongs to page2 with index 0
        rec2 = chunk_records[2]
        assert rec2.wiki_page_id == page2_id
        assert rec2.chunk_index == 0
        assert rec2.content == "chunk-c"
        assert rec2.content_embedding == vec_c


class TestGenerateEmbeddingsTaskChunkCount:
    """Returned count must equal the number of PageChunk records created."""

    @patch("src.flows.tasks.embeddings.embed_texts", new_callable=AsyncMock)
    @patch("src.flows.tasks.embeddings.chunk_markdown_from_settings")
    async def test_count_matches_records(self, mock_chunk, mock_embed):
        from src.flows.tasks.embeddings import generate_embeddings_task

        pages = [_make_mock_page() for _ in range(3)]
        # Each page produces 2 chunks => 6 total
        mock_chunk.return_value = [
            _make_chunk_result(content="c1"),
            _make_chunk_result(content="c2"),
        ]
        mock_embed.return_value = [[0.1]] * 6

        captured_records: list = []

        async def _capture_chunks(records):
            captured_records.extend(records)

        wiki_repo = AsyncMock()
        wiki_repo.get_pages_for_structure = AsyncMock(return_value=pages)
        wiki_repo.create_chunks = AsyncMock(side_effect=_capture_chunks)

        result = await generate_embeddings_task.fn(
            wiki_structure_id=uuid.uuid4(),
            wiki_repo=wiki_repo,
        )

        assert result == 6
        assert len(captured_records) == 6
        assert result == len(captured_records)
