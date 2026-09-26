"""Google Places API (New) client."""

import math

import httpx

from . import config

SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Only request fields we show. The field mask decides the billing SKU, so adding
# fields like reviews or photos moves every call to a pricier tier.
FIELD_MASK = ",".join(
    f"places.{f}"
    for f in [
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "rating",
        "userRatingCount",
        "priceLevel",
        "primaryTypeDisplayName",
        "currentOpeningHours.openNow",
        "googleMapsUri",
    ]
)

PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": "Free",
    "PRICE_LEVEL_INEXPENSIVE": "$",
    "PRICE_LEVEL_MODERATE": "$$",
    "PRICE_LEVEL_EXPENSIVE": "$$$",
    "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$",
}


class PlacesError(Exception):
    pass


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)))


async def search_text(
    query: str,
    lat: float | None = None,
    lng: float | None = None,
    radius_m: int = 2000,
    open_now: bool = False,
    max_results: int = 10,
) -> list[dict]:
    if not config.GOOGLE_PLACES_API_KEY:
        raise PlacesError("GOOGLE_PLACES_API_KEY is not set on the server.")

    body: dict = {
        "textQuery": query,
        "pageSize": max_results,
        "regionCode": "SG",
        "languageCode": "en",
    }
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": float(min(radius_m, 50_000))}
        }
    if open_now:
        body["openNow"] = True

    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.post(
            SEARCH_URL,
            json=body,
            headers={
                "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
                "X-Goog-FieldMask": FIELD_MASK,
            },
        )
    if resp.status_code != 200:
        raise PlacesError(f"Places API error {resp.status_code}: {resp.text[:300]}")

    results = []
    for p in resp.json().get("places", []):
        loc = p.get("location") or {}
        place = {
            "place_id": p["id"],
            "name": (p.get("displayName") or {}).get("text", "Unknown"),
            "address": p.get("formattedAddress"),
            "type": (p.get("primaryTypeDisplayName") or {}).get("text"),
            "rating": p.get("rating"),
            "rating_count": p.get("userRatingCount"),
            "price": PRICE_LEVELS.get(p.get("priceLevel", "")),
            "open_now": (p.get("currentOpeningHours") or {}).get("openNow"),
            "maps_url": p.get("googleMapsUri"),
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "distance_m": None,
        }
        if lat is not None and lng is not None and place["lat"] is not None:
            place["distance_m"] = haversine_m(lat, lng, place["lat"], place["lng"])
        results.append(place)
    return results
