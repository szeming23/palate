"""The Claude tool-use loop, with the Anthropic client replaced by a scripted fake."""

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from palate.llm import LLMError
from palate.llm import anthropic_provider as ap


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool_use(name, input, id="tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=input, id=id)


def response(stop_reason, *content, input_tokens=100, output_tokens=10):
    usage = SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_creation_input_tokens=5,
        cache_read_input_tokens=None,
    )
    return SimpleNamespace(stop_reason=stop_reason, content=list(content), usage=usage)


@pytest.fixture
def claude(monkeypatch):
    """Fake AsyncAnthropic. Set .responses (list of responses or exceptions); .requests records kwargs."""

    class Fake:
        responses: list = []
        requests: list[dict] = []

        async def create(self, **kwargs):
            # Snapshot messages: the provider mutates the list after each call.
            self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
            r = self.responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return r

    fake = Fake()
    fake.requests = []
    client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    monkeypatch.setattr(ap.anthropic, "AsyncAnthropic", lambda api_key: client)
    return fake


async def run(model="claude-opus-5", execute=None):
    async def default_execute(name, args):
        return f"ran {name}"

    return await ap.AnthropicProvider().run(
        api_key="sk",
        model=model,
        system_stable="stable",
        system_context="context",
        history=[{"role": "user", "content": "hi"}],
        tools=[],
        execute=execute or default_execute,
    )


async def test_plain_reply(claude):
    claude.responses = [response("end_turn", text("Hello!"))]
    result = await run()
    assert result.text == "Hello!"
    assert result.usage.input_tokens == 100
    assert result.usage.cache_write_tokens == 5


async def test_tool_loop_sends_results_back(claude):
    claude.responses = [
        response("tool_use", text("Searching"), tool_use("search_places", {"query": "laksa"})),
        response("end_turn", text("Found some")),
    ]
    result = await run()
    assert result.text == "Found some"
    assert result.usage.input_tokens == 200  # summed over both calls
    second = claude.requests[1]["messages"]
    assert second[-1] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "tu_1", "content": "ran search_places"}],
    }


async def test_tool_errors_go_back_to_the_model(claude):
    async def failing(name, args):
        raise RuntimeError("Places quota exceeded")

    claude.responses = [response("tool_use", tool_use("search_places", {})), response("end_turn", text("Sorry"))]
    await run(execute=failing)
    [result] = claude.requests[1]["messages"][-1]["content"]
    assert result["is_error"] is True
    assert "quota" in result["content"]


async def test_system_prompt_caches_the_stable_part(claude):
    claude.responses = [response("end_turn", text("ok"))]
    await run()
    stable, context = claude.requests[0]["system"]
    assert stable == {"type": "text", "text": "stable", "cache_control": {"type": "ephemeral"}}
    assert context == {"type": "text", "text": "context"}


@pytest.mark.parametrize(
    ("model", "thinking", "fallbacks"),
    [("claude-opus-5", True, True), ("claude-sonnet-5", True, False), ("claude-haiku-4-5", False, False)],
)
async def test_model_specific_params(claude, model, thinking, fallbacks):
    claude.responses = [response("end_turn", text("ok"))]
    await run(model=model)
    req = claude.requests[0]
    assert ("thinking" in req) is thinking
    assert ("fallbacks" in req) is fallbacks


async def test_refusal(claude):
    claude.responses = [response("refusal")]
    assert "can't help" in (await run()).text


async def test_too_many_rounds(claude):
    claude.responses = [response("tool_use", tool_use("search_places", {})) for _ in range(ap.MAX_TOOL_ROUNDS)]
    result = await run()
    assert "too many steps" in result.text
    assert len(claude.requests) == ap.MAX_TOOL_ROUNDS


def _status_error(cls, status):
    req = httpx.Request("POST", "https://api.anthropic.com")
    return cls("err", response=httpx.Response(status, request=req), body=None)


@pytest.mark.parametrize(
    ("exc", "message"),
    [
        (_status_error(anthropic.AuthenticationError, 401), "rejected"),
        (_status_error(anthropic.RateLimitError, 429), "rate limit"),
        (_status_error(anthropic.InternalServerError, 500), "(500)"),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), "reach"),
    ],
)
async def test_api_errors_become_user_safe(claude, exc, message):
    claude.responses = [exc]
    with pytest.raises(LLMError, match=message):
        await run()
