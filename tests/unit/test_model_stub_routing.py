from __future__ import annotations

import pytest

from src.config.settings import get_settings


def test_get_model_returns_stub_when_value_is_stub(monkeypatch):
    """get_model('stub') must return a BaseLlm-compatible stub instance."""
    monkeypatch.setenv("DEFAULT_MODEL", "stub")
    get_settings.cache_clear()

    from google.adk.models.base_llm import BaseLlm

    from src.config.models import get_model

    model = get_model("stub")
    assert isinstance(model, BaseLlm), (
        f"Expected a BaseLlm-derived stub, got {type(model).__name__}"
    )
    assert "Stub" in type(model).__name__, (
        f"Expected a Stub-named class, got {type(model).__name__}"
    )


def test_get_model_returns_string_when_value_is_gemini(monkeypatch):
    """Real model names must NOT be coerced into stubs."""
    monkeypatch.setenv("DEFAULT_MODEL", "gemini-2.5-flash")
    get_settings.cache_clear()
    from src.config.models import get_model

    model = get_model("gemini-2.5-flash")
    assert isinstance(model, str), f"Expected str passthrough, got {type(model).__name__}"
    assert "Stub" not in type(model).__name__


@pytest.mark.asyncio
async def test_stub_embedding_returns_unit_vectors_when_model_is_stub(monkeypatch):
    """generate_embeddings must short-circuit to deterministic vectors when EMBEDDING_MODEL=stub."""
    monkeypatch.setenv("EMBEDDING_MODEL", "stub")
    get_settings.cache_clear()

    from src.services.embedding import generate_embeddings

    vectors = await generate_embeddings(["hello world", "another text"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 1024  # default EMBEDDING_DIMENSIONS
    # Deterministic: same input -> same vector
    again = await generate_embeddings(["hello world"])
    assert again[0] == vectors[0]


def teardown_module(_module: object) -> None:
    """Reset settings cache after this test module runs to avoid bleed-through."""
    get_settings.cache_clear()
