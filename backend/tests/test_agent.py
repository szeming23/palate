import pytest
from conftest import make_code

from palate import access, agent, db
from palate.llm import LLMError, Usage


async def test_chat_turn_end_to_end(code, provider, fake_places):
    _, acc = code
    provider.tool_calls = [
        ("search_places", {"query": "chicken rice bishan"}),
        ("present_recommendations", {"picks": [{"place_id": "p1", "reason": "Near you"}]}),
    ]
    out = await agent.chat(access=acc, message="bishan chicken rice", model="claude-haiku-4-5")

    assert out["reply"] == "Here you go!"
    assert [c["place_id"] for c in out["cards"]] == ["p1"]
    # Both sides of the turn are saved, with the cards on the assistant message.
    msgs = db.recent_messages("me", 10)
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "bishan chicken rice"), ("assistant", "Here you go!")]
    assert msgs[1]["cards"][0]["recommendation_id"]
    assert access.today_usage(acc)["messages"] == 1


async def test_chat_sends_history_and_context(code, provider):
    _, acc = code
    db.add_message("me", "user", "earlier question")
    db.add_message("me", "assistant", "earlier answer")
    db.add_memory("me", "fact", "Vegetarian")

    await agent.chat(access=acc, message="dinner?", model="claude-haiku-4-5", lat=1.3521, lng=103.8198)

    call = provider.calls[0]
    assert call["api_key"] == "sk-ant-test"
    assert call["history"][-1] == {"role": "user", "content": "dinner?"}
    assert call["history"][0]["content"] == "earlier question"
    assert "Vegetarian" in call["system_context"]
    assert "1.35210, 103.81980" in call["system_context"]


async def test_failed_turn_saves_nothing(code, monkeypatch, provider):
    _, acc = code

    async def boom(**_):
        raise LLMError("The Claude API key was rejected.")

    monkeypatch.setattr(provider, "run", boom)
    with pytest.raises(LLMError):
        await agent.chat(access=acc, message="hi", model="claude-haiku-4-5")
    assert db.recent_messages("me", 10) == []
    assert access.today_usage(acc)["messages"] == 0


async def test_usage_cost_is_recorded(provider):
    _, acc = make_code(daily_usd=10)
    provider.usage = Usage(input_tokens=1_000_000, output_tokens=0)
    await agent.chat(access=acc, message="hi", model="claude-haiku-4-5")
    assert access.today_usage(acc)["cost_usd"] == 1.0  # Haiku: $1 / MTok input


def test_context_for_new_user():
    ctx = agent.build_context("nobody", None, None)
    assert "location is unknown" in ctx
    assert "not filled in yet" in ctx
    assert "don't remember anything" in ctx


def test_context_includes_profile_and_feedback():
    db.set_profile("me", {"dietary": "halal", "likes": ""})
    rid = db.add_recommendation("me", "p1", "Tian Tian", "chicken rice")
    db.set_feedback("me", rid, "down")
    ctx = agent.build_context("me", None, None)
    assert '"dietary": "halal"' in ctx
    assert '"likes"' not in ctx  # empty fields are dropped
    assert "👎 Tian Tian (for 'chicken rice')" in ctx
