"""Builds the prompt from the user's memory and runs one chat turn."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config, db, tools
from .access import authorize
from .llm import PROVIDERS

SYSTEM_PROMPT = """You are Palate, a friendly food buddy in Singapore who recommends where to eat.

How you work:
- The user tells you what they feel like and/or where they are, e.g. "bishan chicken rice", "something \
cheap near me", "date night Tiong Bahru". Use search_places to find real options, then call \
present_recommendations with your best 3-5 picks. Never recommend a place that didn't come from search_places.
- Rank picks using what you know about the user (profile, memories, past thumbs up/down), plus rating, \
review count, distance and whether it's open. A 4.3 with 2,000 reviews usually beats a 4.9 with 12.
- Respect dietary needs and allergies strictly. If a place is a poor fit, leave it out.
- When the user reveals a lasting preference or a place they frequent, save it with save_memory. If they \
correct something you remembered, forget_memory the old one (and save the new one if needed).
- If the request is ambiguous and you have no location to go on, ask one short question instead of guessing.
- If the user is just chatting (not asking for food), reply normally without searching.
- Keep replies short and casual. Singlish flavour is welcome but don't overdo it. The cards carry the \
details, so your text should add the "why", not repeat addresses and ratings."""


def build_context(user_id: str, lat: float | None, lng: float | None) -> str:
    profile = db.get_profile(user_id)
    memories = db.list_memories(user_id)
    feedback = db.recent_feedback(user_id)
    now = datetime.now(ZoneInfo("Asia/Singapore"))

    parts = [f"Current time in Singapore: {now:%A %d %b %Y, %H:%M}."]
    if lat is not None and lng is not None:
        parts.append(f"User's current GPS location: {lat:.5f}, {lng:.5f}.")
    else:
        parts.append("User's current location is unknown.")

    profile = {k: v for k, v in profile.items() if v}
    parts.append(
        "User profile (set by the user):\n" + json.dumps(profile, ensure_ascii=False)
        if profile
        else "User profile: not filled in yet."
    )

    if memories:
        lines = "\n".join(f"- #{m['id']} [{m['kind']}] {m['content']}" for m in memories)
        parts.append(f"Things you remember about the user:\n{lines}")
    else:
        parts.append("You don't remember anything about the user yet.")

    if feedback:
        lines = "\n".join(
            f"- {'👍' if f['feedback'] == 'up' else '👎'} {f['name']} (for '{f['query']}')" for f in feedback
        )
        parts.append(f"Recent feedback on past recommendations:\n{lines}")

    return "\n\n".join(parts)


async def chat(
    *,
    access: dict,
    message: str,
    model: str,
    own_api_key: str = "",
    lat: float | None = None,
    lng: float | None = None,
) -> dict:
    """Run one chat turn for an access code. Raises access.AccessError, LLMError or PlacesError."""
    grant = authorize(access, model, own_api_key)
    user_id = access["user_id"]
    provider = PROVIDERS[grant.model.provider]

    history = [{"role": m["role"], "content": m["content"]} for m in db.recent_messages(user_id, config.HISTORY_TURNS)]
    history.append({"role": "user", "content": message})

    ctx = tools.ToolContext(user_id=user_id, query=message, lat=lat, lng=lng)

    async def execute(name: str, args: dict) -> str:
        return await tools.execute(name, args, ctx)

    result = await provider.run(
        api_key=grant.api_key,
        model=grant.model.id,
        system_stable=SYSTEM_PROMPT,
        system_context=build_context(user_id, lat, lng),
        history=history,
        tools=tools.TOOLS,
        execute=execute,
    )
    db.record_usage(
        access["id"],
        grant.model.id,
        grant.own_key,
        result.usage.input_tokens + result.usage.cache_write_tokens + result.usage.cache_read_tokens,
        result.usage.output_tokens,
        result.usage.cost_usd(grant.model),
    )

    # Save only after a successful run so a failed request doesn't leave a dangling user turn.
    db.add_message(user_id, "user", message)
    msg_id = db.add_message(user_id, "assistant", result.text, ctx.cards)
    return {"id": msg_id, "reply": result.text, "cards": ctx.cards}
