import json

import pytest
from conftest import place

from palate import db, tools


def ctx(**kw) -> tools.ToolContext:
    return tools.ToolContext(user_id="me", query="chicken rice", **kw)


def test_tool_definitions_are_well_formed():
    names = [t["name"] for t in tools.TOOLS]
    assert names == ["search_places", "save_memory", "forget_memory", "present_recommendations"]
    for t in tools.TOOLS:
        assert t["description"]
        assert t["input_schema"]["type"] == "object"


async def test_search_hides_coords_from_model_and_records_seen(fake_places):
    c = ctx()
    out = json.loads(await tools.execute("search_places", {"query": "chicken rice"}, c))
    assert out[0]["name"] == "Tian Tian"
    assert not {"lat", "lng", "maps_url"} & out[0].keys()
    assert "p1" in c.seen_places


async def test_search_uses_location_only_when_asked(fake_places):
    c = ctx(lat=1.35, lng=103.85)
    await tools.execute("search_places", {"query": "laksa"}, c)
    await tools.execute("search_places", {"query": "laksa", "use_current_location": True}, c)
    assert fake_places.calls[0]["lat"] is None
    assert fake_places.calls[1]["lat"] == 1.35
    # Distance is filled in even when the search wasn't location-biased.
    assert c.seen_places["p1"]["distance_m"] > 0


async def test_search_no_results(fake_places):
    fake_places.results = []
    assert "No results" in await tools.execute("search_places", {"query": "x"}, ctx())


async def test_save_and_forget_memory():
    c = ctx()
    out = await tools.execute("save_memory", {"kind": "fact", "content": "  Hates coriander "}, c)
    [mem] = db.list_memories("me")
    assert mem["content"] == "Hates coriander"
    assert f"#{mem['id']}" in out
    assert await tools.execute("forget_memory", {"memory_id": mem["id"]}, c) == "Deleted."
    assert "No memory" in await tools.execute("forget_memory", {"memory_id": mem["id"]}, c)


async def test_present_only_builds_cards_from_searched_places():
    """The model must not be able to invent a restaurant."""
    c = ctx(seen_places={"p1": place("p1")})
    out = await tools.execute(
        "present_recommendations",
        {"picks": [{"place_id": "p1", "reason": "Classic"}, {"place_id": "made-up", "reason": "Trust me"}]},
        c,
    )
    assert [card["place_id"] for card in c.cards] == ["p1"]
    assert c.cards[0]["reason"] == "Classic"
    assert "made-up" in out
    # Each card is logged so 👍/👎 can refer to it.
    assert db.set_feedback("me", c.cards[0]["recommendation_id"], "up")


async def test_present_twice_replaces_cards():
    c = ctx(seen_places={"p1": place("p1"), "p2": place("p2")})
    await tools.execute("present_recommendations", {"picks": [{"place_id": "p1", "reason": "a"}]}, c)
    await tools.execute("present_recommendations", {"picks": [{"place_id": "p2", "reason": "b"}]}, c)
    assert [card["place_id"] for card in c.cards] == ["p2"]


async def test_unknown_tool():
    with pytest.raises(ValueError):
        await tools.execute("hack_the_planet", {}, ctx())
