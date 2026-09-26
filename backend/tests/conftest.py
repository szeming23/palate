"""Shared fixtures. Tests never touch the real palate.db, .env keys, Claude or Google."""

import pytest
from fastapi.testclient import TestClient

from palate import access, config, db, places
from palate.llm import PROVIDERS, RunResult, Usage
from palate.main import app


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Fresh SQLite file and fake server config for every test."""
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(config, "LLM_KEYS", {"anthropic-main": ("anthropic", "sk-ant-test")})
    monkeypatch.setattr(config, "GOOGLE_PLACES_API_KEY", "test-places-key")
    db.init()


def make_code(
    name="phone",
    user_id="me",
    key_names=("anthropic-main",),
    allowed_models=None,
    daily_messages=None,
    daily_usd=None,
) -> tuple[str, dict]:
    """Create an access code; returns (plaintext code, access row)."""
    code = access.generate_code()
    db.add_access_code(
        name=name,
        code_hash=access.hash_code(code),
        user_id=user_id,
        key_names=list(key_names),
        allowed_models=allowed_models,
        daily_messages=daily_messages,
        daily_usd=daily_usd,
    )
    return code, access.lookup(code)


@pytest.fixture
def code():
    return make_code()


@pytest.fixture
def client(code):
    """HTTP client authorised with a default access code."""
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {code[0]}"
        yield c


def place(pid="p1", name="Tian Tian", lat=1.2805, lng=103.8440, **extra) -> dict:
    """A place dict shaped like places.search_text() output."""
    return {
        "place_id": pid,
        "name": name,
        "address": "1 Test St",
        "type": "Hawker stall",
        "rating": 4.5,
        "rating_count": 1000,
        "price": "$",
        "open_now": True,
        "maps_url": f"https://maps.example/{pid}",
        "lat": lat,
        "lng": lng,
        "distance_m": None,
        **extra,
    }


@pytest.fixture
def fake_places(monkeypatch):
    """Replace Places search. Set .results to control output; .calls records kwargs."""

    class Fake:
        results: list[dict] = [place()]
        calls: list[dict] = []

        async def __call__(self, **kwargs):
            self.calls.append(kwargs)
            return [dict(p) for p in self.results]

    fake = Fake()
    fake.calls = []
    monkeypatch.setattr(places, "search_text", fake)
    return fake


class ScriptedProvider:
    """Stands in for an LLM: runs a scripted list of tool calls, then replies with fixed text."""

    def __init__(self, tool_calls=(), text="Here you go!", usage=None):
        self.tool_calls = list(tool_calls)
        self.text = text
        self.usage = usage or Usage(input_tokens=1000, output_tokens=200)
        self.calls: list[dict] = []
        self.tool_outputs: list[str] = []

    async def run(self, *, execute, **kwargs) -> RunResult:
        self.calls.append(kwargs)
        for name, args in self.tool_calls:
            self.tool_outputs.append(await execute(name, args))
        return RunResult(self.text, self.usage)


@pytest.fixture
def provider(monkeypatch):
    """Swap the Anthropic provider for a scripted one. Mutate .tool_calls/.text as needed."""
    fake = ScriptedProvider()
    monkeypatch.setitem(PROVIDERS, "anthropic", fake)
    return fake
