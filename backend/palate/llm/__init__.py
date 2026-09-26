"""LLM provider registry. To add a provider (OpenAI, Gemini, ...), implement
LLMProvider in a new module, register it in PROVIDERS, and add its models to MODELS."""

from .anthropic_provider import AnthropicProvider
from .base import LLMError, LLMProvider, ModelInfo, RunResult, Usage

PROVIDERS: dict[str, LLMProvider] = {
    "anthropic": AnthropicProvider(),
}

# Prices are USD per million tokens, used for daily spend caps.
MODELS: list[ModelInfo] = [
    ModelInfo("claude-opus-5", "anthropic", "Claude Opus 5 (best)", 5.00, 25.00),
    ModelInfo("claude-sonnet-5", "anthropic", "Claude Sonnet 5 (balanced)", 2.00, 10.00),
    ModelInfo("claude-haiku-4-5", "anthropic", "Claude Haiku 4.5 (fastest, cheapest)", 1.00, 5.00),
]

DEFAULT_MODEL = "claude-opus-5"


def get_model(model_id: str) -> ModelInfo:
    for m in MODELS:
        if m.id == model_id:
            return m
    raise LLMError(f"Unknown model '{model_id}'.")


__all__ = ["PROVIDERS", "MODELS", "DEFAULT_MODEL", "get_model", "LLMError", "ModelInfo", "RunResult", "Usage"]
