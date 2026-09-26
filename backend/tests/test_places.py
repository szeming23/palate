import json

import httpx
import pytest

from palate import config, places

REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def google(monkeypatch):
    """Intercept HTTP calls to Google. Set .status/.payload; .requests records what was sent."""

    class Google:
        status = 200
        payload: dict = {"places": []}
        requests: list[httpx.Request] = []

    g = Google()
    g.requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        g.requests.append(request)
        return httpx.Response(g.status, json=g.payload)

    monkeypatch.setattr(
        places.httpx, "AsyncClient", lambda **kw: REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kw)
    )
    return g


def test_haversine():
    assert places.haversine_m(1.3, 103.8, 1.3, 103.8) == 0
    # One degree of latitude is ~111 km.
    assert 111_000 < places.haversine_m(1.0, 103.8, 2.0, 103.8) < 111_400


async def test_search_parses_results_and_distance(google):
    google.payload = {
        "places": [
            {
                "id": "abc",
                "displayName": {"text": "Tian Tian"},
                "formattedAddress": "1 Kadayanallur St",
                "location": {"latitude": 1.2805, "longitude": 103.8440},
                "rating": 4.3,
                "userRatingCount": 2000,
                "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
                "primaryTypeDisplayName": {"text": "Hawker stall"},
                "currentOpeningHours": {"openNow": True},
                "googleMapsUri": "https://maps.google.com/?cid=1",
            },
            {"id": "bare"},
        ]
    }
    [full, bare] = await places.search_text("chicken rice", lat=1.2805, lng=103.8440)

    assert full["name"] == "Tian Tian"
    assert full["price"] == "$"
    assert full["open_now"] is True
    assert full["distance_m"] == 0
    # Missing fields don't crash.
    assert bare["name"] == "Unknown"
    assert bare["distance_m"] is None


async def test_search_request_shape(google):
    await places.search_text("laksa", lat=1.3, lng=103.8, radius_m=999_999, open_now=True)
    [req] = google.requests
    body = json.loads(req.content)
    assert req.headers["X-Goog-Api-Key"] == "test-places-key"
    assert body["textQuery"] == "laksa"
    assert body["regionCode"] == "SG"
    assert body["openNow"] is True
    # Radius is capped at the API maximum.
    assert body["locationBias"]["circle"]["radius"] == 50_000.0


async def test_search_without_location_has_no_bias(google):
    await places.search_text("laksa katong")
    body = json.loads(google.requests[0].content)
    assert "locationBias" not in body
    assert "openNow" not in body


async def test_field_mask_stays_on_the_cheap_sku(google):
    # Reviews/photos bump every call to a pricier SKU. Change this test only on purpose.
    await places.search_text("laksa")
    mask = google.requests[0].headers["X-Goog-FieldMask"]
    assert "reviews" not in mask
    assert "photos" not in mask


async def test_search_api_error(google):
    google.status = 403
    with pytest.raises(places.PlacesError, match="403"):
        await places.search_text("laksa")


async def test_search_without_key(google, monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_PLACES_API_KEY", "")
    with pytest.raises(places.PlacesError, match="not set"):
        await places.search_text("laksa")
    assert google.requests == []
