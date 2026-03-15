"""Tests for src.services.context_enrichment — contextual enrichment service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.services.context_enrichment import generate_chunk_contexts

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_settings(**overrides):
    """Return a mock Settings with sensible defaults for context enrichment."""
    s = MagicMock()
    s.DEFAULT_MODEL = overrides.get("DEFAULT_MODEL", "gemini-2.5-flash")
    s.CONTEXT_MODEL = overrides.get("CONTEXT_MODEL", "")
    s.CONTEXT_MAX_TOKENS = overrides.get("CONTEXT_MAX_TOKENS", 100)
    s.CONTEXT_CONCURRENCY = overrides.get("CONTEXT_CONCURRENCY", 5)
    return s


def _make_completion_response(content: str):
    """Build a mock litellm acompletion response."""
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


# ===========================================================================
# Tests
# ===========================================================================


class TestGenerateChunkContextsBasic:
    """Basic batch context generation."""

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_generates_contexts_for_all_chunks(self, mock_litellm, _settings):
        responses = [
            _make_completion_response("Context for chunk 1."),
            _make_completion_response("Context for chunk 2."),
        ]
        mock_litellm.acompletion = AsyncMock(side_effect=responses)

        results = await generate_chunk_contexts(
            chunks=["chunk text 1", "chunk text 2"],
            section_content="Full section content here.",
            page_title="Getting Started",
            heading_paths=[["Getting Started", "Install"], ["Getting Started", "Config"]],
        )

        assert len(results) == 2
        assert results[0] == "Context for chunk 1."
        assert results[1] == "Context for chunk 2."
        assert mock_litellm.acompletion.await_count == 2

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_single_chunk(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_completion_response("Single context.")
        )

        results = await generate_chunk_contexts(
            chunks=["only chunk"],
            section_content="Section text.",
            page_title="Page",
            heading_paths=[["Section"]],
        )

        assert results == ["Single context."]

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_empty_chunks_list(self, mock_litellm, _settings):
        results = await generate_chunk_contexts(
            chunks=[],
            section_content="Section.",
            page_title="Page",
            heading_paths=[],
        )

        assert results == []
        mock_litellm.acompletion.assert_not_called()


class TestGenerateChunkContextsPartialFailure:
    """LLM failure for individual chunks should return None, not crash."""

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_returns_none_on_failure(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            side_effect=[
                _make_completion_response("Good context."),
                RuntimeError("API rate limit"),
                _make_completion_response("Another good context."),
            ]
        )

        results = await generate_chunk_contexts(
            chunks=["chunk1", "chunk2", "chunk3"],
            section_content="Section content.",
            page_title="Page",
            heading_paths=[["A"], ["B"], ["C"]],
        )

        assert len(results) == 3
        assert results[0] == "Good context."
        assert results[1] is None  # Failed gracefully
        assert results[2] == "Another good context."

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_all_failures_returns_all_none(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            side_effect=RuntimeError("Service unavailable")
        )

        results = await generate_chunk_contexts(
            chunks=["a", "b"],
            section_content="Section.",
            page_title="Page",
            heading_paths=[["X"], ["Y"]],
        )

        assert results == [None, None]


class TestGenerateChunkContextsModelSelection:
    """Model and parameter fallback logic."""

    @patch(
        "src.services.context_enrichment.get_settings",
        return_value=_fake_settings(CONTEXT_MODEL="gpt-4o-mini"),
    )
    @patch("src.services.context_enrichment.litellm")
    async def test_uses_context_model_when_set(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_completion_response("ctx")
        )

        await generate_chunk_contexts(
            chunks=["chunk"],
            section_content="Section.",
            page_title="Page",
            heading_paths=[["S"]],
        )

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    @patch(
        "src.services.context_enrichment.get_settings",
        return_value=_fake_settings(CONTEXT_MODEL="", DEFAULT_MODEL="gemini-2.5-flash"),
    )
    @patch("src.services.context_enrichment.litellm")
    async def test_falls_back_to_default_model(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_completion_response("ctx")
        )

        await generate_chunk_contexts(
            chunks=["chunk"],
            section_content="Section.",
            page_title="Page",
            heading_paths=[["S"]],
        )

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert call_kwargs["model"] == "gemini-2.5-flash"

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_explicit_model_overrides_settings(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_completion_response("ctx")
        )

        await generate_chunk_contexts(
            chunks=["chunk"],
            section_content="Section.",
            page_title="Page",
            heading_paths=[["S"]],
            model="claude-sonnet-4-6",
        )

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-6"


class TestGenerateChunkContextsPromptContent:
    """Verify the prompt includes section content, chunk, and heading path."""

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_prompt_contains_section_and_chunk(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_completion_response("ctx")
        )

        await generate_chunk_contexts(
            chunks=["The refresh() method resets tokens."],
            section_content="## OAuth2\n\nThe refresh() method resets tokens.\n\nOther content here.",
            page_title="Authentication Guide",
            heading_paths=[["Auth", "OAuth2"]],
        )

        call_kwargs = mock_litellm.acompletion.call_args.kwargs
        prompt = call_kwargs["messages"][0]["content"]

        assert "OAuth2" in prompt
        assert "refresh() method" in prompt
        assert "Authentication Guide" in prompt
        assert "Auth > OAuth2" in prompt

    @patch("src.services.context_enrichment.get_settings", return_value=_fake_settings())
    @patch("src.services.context_enrichment.litellm")
    async def test_empty_heading_path_uses_root(self, mock_litellm, _settings):
        mock_litellm.acompletion = AsyncMock(
            return_value=_make_completion_response("ctx")
        )

        await generate_chunk_contexts(
            chunks=["content"],
            section_content="Preamble content.",
            page_title="Page",
            heading_paths=[[]],
        )

        prompt = mock_litellm.acompletion.call_args.kwargs["messages"][0]["content"]
        assert "Root" in prompt
