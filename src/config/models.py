from __future__ import annotations

from google.adk.models.lite_llm import LiteLlm

_LITELLM_PREFIXES = ("vertex_ai/", "azure/", "bedrock/", "openai/")


def get_model(model_name: str) -> str | LiteLlm:
    if model_name.startswith("gemini-"):
        return model_name

    if any(model_name.startswith(p) for p in _LITELLM_PREFIXES):
        return LiteLlm(model=model_name)

    raise ValueError(
        f"Unrecognized model format: {model_name!r}. "
        f"Expected 'gemini-*' or a provider-prefixed string "
        f"({', '.join(_LITELLM_PREFIXES)})."
    )
