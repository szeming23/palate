import logging

import anthropic

from .base import LLMError, RunResult, ToolExecutor, Usage

log = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 8

# Models that support adaptive thinking. Haiku 4.5 does not.
ADAPTIVE_THINKING = {"claude-opus-5", "claude-sonnet-5"}
# Models that support server-side refusal fallbacks.
SERVER_FALLBACKS = {"claude-opus-5"}


class AnthropicProvider:
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
        client = anthropic.AsyncAnthropic(api_key=api_key)

        system = [
            # Stable prefix first so it caches across requests; per-request context after it.
            {"type": "text", "text": system_stable, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": system_context},
        ]
        messages: list[dict] = [{"role": m["role"], "content": m["content"]} for m in history]

        params: dict = {
            "model": model,
            "max_tokens": 16000,
            "system": system,
            "tools": tools,
        }
        if model in ADAPTIVE_THINKING:
            params["thinking"] = {"type": "adaptive"}
        if model in SERVER_FALLBACKS:
            # If a safety classifier declines, the API retries on its recommended fallback model.
            params["betas"] = ["server-side-fallback-2026-07-01"]
            params["fallbacks"] = "default"

        usage = Usage()
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response = await client.beta.messages.create(messages=messages, **params)
                u = response.usage
                usage.input_tokens += u.input_tokens
                usage.output_tokens += u.output_tokens
                usage.cache_write_tokens += u.cache_creation_input_tokens or 0
                usage.cache_read_tokens += u.cache_read_input_tokens or 0

                if response.stop_reason == "refusal":
                    return RunResult("Sorry, I can't help with that one.", usage)

                if response.stop_reason != "tool_use":
                    return RunResult(_text(response.content) or "(no reply)", usage)

                messages.append({"role": "assistant", "content": response.content})
                results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    try:
                        output = await execute(block.name, block.input)
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": output})
                    except Exception as e:  # report tool failures back to the model
                        log.exception("tool %s failed", block.name)
                        results.append(
                            {"type": "tool_result", "tool_use_id": block.id, "content": str(e), "is_error": True}
                        )
                # All results for a turn go back in one user message.
                messages.append({"role": "user", "content": results})

            text = _text(response.content) or "Sorry, that took too many steps. Try a more specific request."
            return RunResult(text, usage)

        except anthropic.AuthenticationError:
            raise LLMError("The Claude API key was rejected.") from None
        except anthropic.PermissionDeniedError:
            raise LLMError("The Claude API key doesn't have access to this model.") from None
        except anthropic.NotFoundError:
            raise LLMError(f"Model '{model}' was not found.") from None
        except anthropic.RateLimitError:
            raise LLMError("Claude rate limit hit. Wait a moment and try again.") from None
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API error ({e.status_code}).") from None
        except anthropic.APIConnectionError:
            raise LLMError("Couldn't reach the Claude API.") from None


def _text(content) -> str:
    return "\n".join(b.text for b in content if b.type == "text").strip()
