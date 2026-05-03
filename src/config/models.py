from __future__ import annotations

from collections.abc import AsyncGenerator

from google.adk.models.base_llm import BaseLlm
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

_LITELLM_PREFIXES = ("vertex_ai/", "azure/", "bedrock/", "openai/")

_STUB_MODEL_NAME = "stub"


class StubLlm(BaseLlm):
    """Offline-friendly LLM placeholder used in E2E and Playwright suites.

    Activated by setting ``DEFAULT_MODEL=stub`` (or any per-agent override to
    ``stub``). Yields a single deterministic ``LlmResponse`` so that
    :class:`google.adk.agents.LlmAgent` can be constructed and its run loop
    invoked without contacting a real provider.

    The Python E2E suite (``tests/e2e/``) overrides whole-agent invocations
    via ``tests/e2e/stubs.py``, so end-to-end flow paths never reach this
    class.  It exists so that the API can boot, app-startup imports succeed,
    and ad-hoc agent runs degrade gracefully when no API key is configured.
    """

    model: str = _STUB_MODEL_NAME

    @classmethod
    def supported_models(cls) -> list[str]:
        return [_STUB_MODEL_NAME]

    async def generate_content_async(  # type: ignore[override]
        self, llm_request: object, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Yield a single canned response.  ``stream`` is ignored."""
        content = types.Content(
            role="model",
            parts=[types.Part.from_text(text="{}")],
        )
        yield LlmResponse(content=content, partial=False)


def get_model(model_name: str) -> str | LiteLlm | StubLlm:
    if model_name == _STUB_MODEL_NAME:
        return StubLlm()

    if model_name.startswith("gemini-"):
        return model_name

    if any(model_name.startswith(p) for p in _LITELLM_PREFIXES):
        return LiteLlm(model=model_name)

    raise ValueError(
        f"Unrecognized model format: {model_name!r}. "
        f"Expected 'gemini-*', 'stub', or a provider-prefixed string "
        f"({', '.join(_LITELLM_PREFIXES)})."
    )
