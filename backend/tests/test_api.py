from conftest import make_code
from fastapi.testclient import TestClient

from palate import db
from palate.llm import LLMError
from palate.main import app
from palate.places import PlacesError


def test_health_needs_no_auth():
    with TestClient(app) as c:
        body = c.get("/health").json()
    assert body == {"ok": True, "places_configured": True, "llm_keys_configured": 1}


def test_bad_access_code_is_401(client):
    for headers in ({"Authorization": "Bearer plt_nope"}, {"Authorization": ""}):
        assert client.get("/me", headers=headers).status_code == 401


def test_me(client):
    body = client.get("/me").json()
    assert body["name"] == "phone"
    assert body["today"] == {"messages": 0, "cost_usd": 0.0}


def test_models_filtered_by_code():
    code, _ = make_code("limited", allowed_models=["claude-haiku-4-5"])
    with TestClient(app) as c:
        body = c.get("/models", headers={"Authorization": f"Bearer {code}"}).json()
    assert body["default"] == "claude-haiku-4-5"
    assert [m["id"] for m in body["models"]] == ["claude-haiku-4-5"]


def test_chat(client, provider, fake_places):
    provider.tool_calls = [
        ("search_places", {"query": "laksa"}),
        ("present_recommendations", {"picks": [{"place_id": "p1", "reason": "Shiok"}]}),
    ]
    r = client.post("/chat", json={"message": "laksa", "model": "claude-haiku-4-5"})
    assert r.status_code == 200
    card = r.json()["cards"][0]
    # Feedback on the returned card works.
    rid = card["recommendation_id"]
    assert client.put(f"/recommendations/{rid}/feedback", json={"feedback": "up"}).status_code == 200
    assert db.recent_feedback("me")[0]["feedback"] == "up"
    # And the turn shows up in history.
    assert len(client.get("/history").json()["messages"]) == 2


def test_chat_own_key_header_is_used(client, provider):
    client.post("/chat", json={"message": "hi", "model": "claude-haiku-4-5"}, headers={"X-LLM-API-Key": " sk-mine "})
    assert provider.calls[0]["api_key"] == "sk-mine"


def test_chat_validation(client, provider):
    assert client.post("/chat", json={"message": ""}).status_code == 422
    assert client.post("/chat", json={"message": "x" * 2001}).status_code == 422


def test_chat_error_mapping(client, provider, monkeypatch):
    assert client.post("/chat", json={"message": "hi", "model": "nope"}).status_code == 400

    for exc in (LLMError("bad key"), PlacesError("quota")):

        async def boom(exc=exc, **_):
            raise exc

        monkeypatch.setattr(provider, "run", boom)
        r = client.post("/chat", json={"message": "hi", "model": "claude-haiku-4-5"})
        assert r.status_code == 502
        assert r.json()["detail"] == str(exc)


def test_daily_limit_over_http(provider):
    code, _ = make_code("capped", daily_messages=1)
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {code}"
        assert c.post("/chat", json={"message": "hi", "model": "claude-haiku-4-5"}).status_code == 200
        assert c.post("/chat", json={"message": "hi", "model": "claude-haiku-4-5"}).status_code == 429


def test_clear_history(client):
    db.add_message("me", "user", "hi")
    assert client.delete("/history").json() == {"ok": True}
    assert client.get("/history").json()["messages"] == []


def test_profile_roundtrip(client):
    assert client.get("/profile").json()["dietary"] == ""
    client.put("/profile", json={"dietary": "halal", "budget": "< $10"})
    body = client.get("/profile").json()
    assert body["dietary"] == "halal"
    assert body["budget"] == "< $10"


def test_memories_crud(client):
    mid = client.post("/memories", json={"kind": "location", "content": "Works at Raffles Place"}).json()["id"]
    assert client.get("/memories").json()["memories"][0]["id"] == mid
    assert client.delete(f"/memories/{mid}").status_code == 200
    assert client.delete(f"/memories/{mid}").status_code == 404
    assert client.post("/memories", json={"kind": "gossip", "content": "x"}).status_code == 422


def test_users_are_isolated(client):
    """A friend's code must not see or change my data."""
    mid = db.add_memory("me", "fact", "Mine")
    rid = db.add_recommendation("me", "p1", "Tian Tian", "q")
    friend, _ = make_code("friend", user_id="friend")
    h = {"Authorization": f"Bearer {friend}"}
    assert client.get("/memories", headers=h).json()["memories"] == []
    assert client.delete(f"/memories/{mid}", headers=h).status_code == 404
    assert client.put(f"/recommendations/{rid}/feedback", json={"feedback": "down"}, headers=h).status_code == 404
