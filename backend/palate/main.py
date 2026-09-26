"""HTTP API used by the mobile app (and later the Telegram bot).

Run: uvicorn palate.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from . import access, agent, config, db
from .llm import DEFAULT_MODEL, LLMError
from .places import PlacesError


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init()
    yield


app = FastAPI(title="Palate", lifespan=lifespan)


def current_access(authorization: str = Header(default="")) -> dict:
    """Resolves the client's access code ("Authorization: Bearer plt_...")."""
    code = authorization.removeprefix("Bearer ").strip()
    found = access.lookup(code)
    if not found:
        raise HTTPException(401, "Unknown access code. Check Settings.")
    return found


def current_user(acc: dict = Depends(current_access)) -> str:
    return acc["user_id"]


# --- models ------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    model: str = DEFAULT_MODEL
    lat: float | None = None
    lng: float | None = None


class Profile(BaseModel):
    dietary: str = ""  # e.g. "halal", "vegetarian", "no beef"
    allergies: str = ""
    budget: str = ""  # e.g. "under $10 usually"
    likes: str = ""
    dislikes: str = ""
    notes: str = ""


class MemoryIn(BaseModel):
    kind: Literal["fact", "location"]
    content: str = Field(min_length=1, max_length=300)


class FeedbackIn(BaseModel):
    feedback: Literal["up", "down"] | None


# --- routes ------------------------------------------------------------------


@app.get("/health")
def health():
    return {
        "ok": True,
        "places_configured": bool(config.GOOGLE_PLACES_API_KEY),
        "llm_keys_configured": len(config.LLM_KEYS),
    }


@app.get("/me")
def me(acc: dict = Depends(current_access)):
    """Who this access code is, its limits and today's usage."""
    return {
        "name": acc["name"],
        "user_id": acc["user_id"],
        "daily_messages": acc["daily_messages"],
        "daily_usd": acc["daily_usd"],
        "today": access.today_usage(acc),
    }


@app.get("/models")
def list_models(acc: dict = Depends(current_access), own_key_provider: str | None = None):
    """Models this access code may use. Pass own_key_provider=anthropic if the client has its own key."""
    models = access.allowed_models(acc, own_key_provider)
    ids = [m.id for m in models]
    default = DEFAULT_MODEL if DEFAULT_MODEL in ids else (ids[0] if ids else None)
    return {"default": default, "models": [{"id": m.id, "provider": m.provider, "label": m.label} for m in models]}


@app.post("/chat")
async def chat(
    req: ChatRequest,
    acc: dict = Depends(current_access),
    x_llm_api_key: str = Header(default=""),
):
    # Optional: a client may pay with its own LLM key. It's used for this request only, never stored.
    try:
        return await agent.chat(
            access=acc,
            message=req.message,
            model=req.model,
            own_api_key=x_llm_api_key.strip(),
            lat=req.lat,
            lng=req.lng,
        )
    except access.AccessError as e:
        raise HTTPException(e.status, str(e)) from e
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    except PlacesError as e:
        raise HTTPException(502, str(e)) from e


@app.get("/history")
def history(user_id: str = Depends(current_user), limit: int = 50):
    return {"messages": db.recent_messages(user_id, limit)}


@app.delete("/history")
def clear_history(user_id: str = Depends(current_user)):
    db.clear_messages(user_id)
    return {"ok": True}


@app.get("/profile")
def get_profile(user_id: str = Depends(current_user)) -> Profile:
    return Profile(**db.get_profile(user_id))


@app.put("/profile")
def put_profile(profile: Profile, user_id: str = Depends(current_user)) -> Profile:
    db.set_profile(user_id, profile.model_dump())
    return profile


@app.get("/memories")
def list_memories(user_id: str = Depends(current_user)):
    return {"memories": db.list_memories(user_id)}


@app.post("/memories")
def add_memory(mem: MemoryIn, user_id: str = Depends(current_user)):
    return {"id": db.add_memory(user_id, mem.kind, mem.content)}


@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: int, user_id: str = Depends(current_user)):
    if not db.delete_memory(user_id, memory_id):
        raise HTTPException(404, "Memory not found.")
    return {"ok": True}


@app.put("/recommendations/{rec_id}/feedback")
def feedback(rec_id: int, body: FeedbackIn, user_id: str = Depends(current_user)):
    if not db.set_feedback(user_id, rec_id, body.feedback):
        raise HTTPException(404, "Recommendation not found.")
    return {"ok": True}
