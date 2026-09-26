from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

# (tool_name, tool_input) -> result string. Raises on failure.
ToolExecutor = Callable[[str, dict], Awaitable[str]]


@dataclass(frozen=True)
class ModelInfo:
    id: str
    provider: str
    label: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float


@dataclass
class Usage:
    """Token counts summed across every API call in one turn."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0

    def cost_usd(self, m: ModelInfo) -> float:
        # Cache writes bill at 1.25x input, cache reads at 0.1x input.
        inp = self.input_tokens + 1.25 * self.cache_write_tokens + 0.1 * self.cache_read_tokens
        return (inp * m.input_usd_per_mtok + self.output_tokens * m.output_usd_per_mtok) / 1_000_000


@dataclass
class RunResult:
    text: str
    usage: Usage


class LLMError(Exception):
    """An error safe to show to the user (bad key, rate limit, etc.)."""


class LLMProvider(Protocol):
    async def run(
        self,
        *,
        api_key: str,
        model: str,
        system_stable: str,
        system_context: str,
        history: list[dict],
        tools: list[dict],
        execute: ToolExecutor,
    ) -> RunResult:
        """Run the tool-use loop until the model is done and return its final text and usage.

        system_stable: instructions that never change (cacheable).
        system_context: per-request user context (memories, location, time).
        history: [{"role": "user"|"assistant", "content": str}, ...] ending with the new user message.
        tools: provider-neutral tool definitions (name, description, input_schema).
        """
        ...
