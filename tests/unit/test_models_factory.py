from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _mock_litellm():
    """Patch LiteLlm so tests don't require google-adk installed."""
    mock_cls = MagicMock()
    mock_cls.__name__ = "LiteLlm"
    modules = {
        "google": MagicMock(),
        "google.adk": MagicMock(),
        "google.adk.models": MagicMock(),
        "google.adk.models.lite_llm": MagicMock(LiteLlm=mock_cls),
    }
    with patch.dict("sys.modules", modules):
        import src.config.models as mod

        importlib.reload(mod)
        yield mock_cls


def _get_model(model_name: str):
    """Helper: reload module under mocked imports, then call get_model."""
    import src.config.models as mod

    importlib.reload(mod)
    return mod.get_model(model_name)


class TestGetModelGemini:
    def test_gemini_pro_returns_string(self):
        assert _get_model("gemini-1.5-pro") == "gemini-1.5-pro"

    def test_gemini_flash_returns_string(self):
        assert _get_model("gemini-2.0-flash") == "gemini-2.0-flash"


class TestGetModelLiteLlm:
    @pytest.mark.parametrize("model_name", [
        "vertex_ai/claude-3-opus",
        "azure/gpt-4o",
        "bedrock/anthropic.claude-v2",
        "openai/gpt-4-turbo",
    ])
    def test_provider_prefixed_returns_litellm_instance(
        self, model_name, _mock_litellm
    ):
        result = _get_model(model_name)
        _mock_litellm.assert_called_with(model=model_name)
        assert result == _mock_litellm.return_value


class TestGetModelInvalid:
    @pytest.mark.parametrize("model_name", [
        "gpt-4",
        "claude-3-opus",
        "some-random-model",
        "",
    ])
    def test_unknown_format_raises_value_error(self, model_name):
        with pytest.raises(ValueError, match="Unrecognized model format"):
            _get_model(model_name)
