"""Tools the agent can call. Definitions are provider-neutral JSON Schema; each
LLM provider adapts them to its own wire format."""

import json
from dataclasses import dataclass, field

from . import db, places


@dataclass
class ToolContext:
    """Per-request state shared between tool calls."""

    user_id: str
    query: str
    lat: float | None = None
    lng: float | None = None
    # Every place returned by search this turn, keyed by place_id. Cards are
    # built only from these, so the model can't invent a restaurant.
    seen_places: dict[str, dict] = field(default_factory=dict)
    cards: list[dict] = field(default_factory=list)


TOOLS: list[dict] = [
    {
        "name": "search_places",
        "description": (
            "Search Google Places for food spots (restaurants, hawker stalls, cafes, food courts) in Singapore. "
            "Use a specific text query that includes the dish or cuisine and, when relevant, the area, "
            "e.g. 'chicken rice Bishan' or 'halal dim sum Tampines'. If the user's current location is known "
            "and they didn't name an area, pass use_current_location=true to bias results near them. "
            "You may call this several times with different phrasings to get a better spread."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text search, e.g. 'bak chor mee Toa Payoh'."},
                "use_current_location": {
                    "type": "boolean",
                    "description": "Bias results around the user's current GPS location.",
                },
                "radius_m": {
                    "type": "integer",
                    "description": "Bias radius in metres when using current location. Default 2000.",
                },
                "open_now": {"type": "boolean", "description": "Only return places open right now."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_memory",
        "description": (
            "Save a durable fact about the user for future recommendations. Use kind='fact' for tastes, "
            "dislikes, dietary needs, allergies, budget habits (e.g. 'Dislikes coriander'). Use kind='location' "
            "for places they frequent (e.g. 'Works near Raffles Place'). Only save things likely to stay true; "
            "don't save one-off cravings. Don't duplicate a memory that already exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["fact", "location"]},
                "content": {"type": "string", "description": "One short sentence."},
            },
            "required": ["kind", "content"],
        },
    },
    {
        "name": "forget_memory",
        "description": "Delete a saved memory by id when the user says it is wrong or no longer true.",
        "input_schema": {
            "type": "object",
            "properties": {"memory_id": {"type": "integer"}},
            "required": ["memory_id"],
        },
    },
    {
        "name": "present_recommendations",
        "description": (
            "Show your final picks to the user as cards. Call this once, after searching, with 3-5 place_ids "
            "taken from search_places results, best first, each with a one-line reason tailored to the user. "
            "Then write a short friendly reply; don't repeat every card's details in the text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "picks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "place_id": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": ["place_id", "reason"],
                    },
                }
            },
            "required": ["picks"],
        },
    },
]


def _slim(p: dict) -> dict:
    """What the model sees from a search result (drop coordinates/URLs to save tokens)."""
    return {k: v for k, v in p.items() if k not in ("lat", "lng", "maps_url") and v is not None}


async def execute(name: str, args: dict, ctx: ToolContext) -> str:
    """Run a tool and return its result as a string. Raises on failure."""
    if name == "search_places":
        use_loc = args.get("use_current_location") and ctx.lat is not None
        results = await places.search_text(
            query=args["query"],
            lat=ctx.lat if use_loc else None,
            lng=ctx.lng if use_loc else None,
            radius_m=args.get("radius_m", 2000),
            open_now=args.get("open_now", False),
        )
        # Distance is still useful even when the query named another area.
        if ctx.lat is not None:
            for p in results:
                if p["distance_m"] is None and p["lat"] is not None:
                    p["distance_m"] = places.haversine_m(ctx.lat, ctx.lng, p["lat"], p["lng"])
        for p in results:
            ctx.seen_places[p["place_id"]] = p
        if not results:
            return "No results. Try a broader or differently worded query."
        return json.dumps([_slim(p) for p in results], ensure_ascii=False)

    if name == "save_memory":
        mem_id = db.add_memory(ctx.user_id, args["kind"], args["content"].strip())
        return f"Saved memory #{mem_id}."

    if name == "forget_memory":
        ok = db.delete_memory(ctx.user_id, int(args["memory_id"]))
        return "Deleted." if ok else "No memory with that id."

    if name == "present_recommendations":
        ctx.cards = []
        unknown = []
        for pick in args["picks"]:
            place = ctx.seen_places.get(pick["place_id"])
            if not place:
                unknown.append(pick["place_id"])
                continue
            rec_id = db.add_recommendation(ctx.user_id, place["place_id"], place["name"], ctx.query)
            ctx.cards.append({**place, "reason": pick["reason"], "recommendation_id": rec_id})
        if unknown:
            return (
                f"Shown {len(ctx.cards)} cards. These place_ids were not from this turn's search results "
                f"and were skipped: {unknown}"
            )
        return f"Shown {len(ctx.cards)} cards to the user."

    raise ValueError(f"Unknown tool: {name}")
