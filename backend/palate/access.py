"""Access codes: map a client's code to a user, LLM keys, allowed models and daily limits."""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from . import config, db
from .llm import MODELS, ModelInfo


class AccessError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


@dataclass
class Grant:
    """What the model call is allowed to use for this request."""

    model: ModelInfo
    api_key: str
    own_key: bool


def generate_code() -> str:
    # 128 bits of randomness, so a fast hash is enough (no need for bcrypt).
    return "plt_" + secrets.token_urlsafe(16)


def hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def lookup(code: str) -> dict | None:
    return db.get_access_code_by_hash(hash_code(code)) if code else None


def _providers_with_keys(access: dict) -> set[str]:
    return {config.LLM_KEYS[k][0] for k in access["key_names"] if k in config.LLM_KEYS}


def allowed_models(access: dict, own_key_provider: str | None = None) -> list[ModelInfo]:
    """Models this code may use: in its allow-list and backed by a server key (or the client's own key)."""
    providers = _providers_with_keys(access)
    if own_key_provider:
        providers.add(own_key_provider)
    return [
        m
        for m in MODELS
        if m.provider in providers and (access["allowed_models"] is None or m.id in access["allowed_models"])
    ]


def start_of_today_utc() -> str:
    local_midnight = datetime.now(ZoneInfo(config.TIMEZONE)).replace(hour=0, minute=0, second=0, microsecond=0)
    return local_midnight.astimezone(UTC).isoformat(timespec="seconds")


def today_usage(access: dict) -> dict:
    return db.usage_since(access["id"], start_of_today_utc())


def authorize(access: dict, model_id: str, own_api_key: str = "") -> Grant:
    """Pick the key for this request and enforce the code's limits. Raises AccessError."""
    model = next((m for m in MODELS if m.id == model_id), None)
    if model is None:
        raise AccessError(400, f"Unknown model '{model_id}'.")
    if access["allowed_models"] is not None and model.id not in access["allowed_models"]:
        raise AccessError(403, f"Your access code can't use {model.label}.")

    used = today_usage(access)
    if access["daily_messages"] is not None and used["messages"] >= access["daily_messages"]:
        raise AccessError(429, f"Daily limit of {access['daily_messages']} messages reached. Resets at midnight.")

    # The client's own key only covers LLM cost; Places calls and the message cap still apply.
    if own_api_key:
        return Grant(model, own_api_key, own_key=True)

    if access["daily_usd"] is not None and used["cost_usd"] >= access["daily_usd"]:
        raise AccessError(429, f"Daily budget of US${access['daily_usd']:.2f} reached. Resets at midnight.")

    for name in access["key_names"]:
        provider, secret = config.LLM_KEYS.get(name, (None, None))
        if provider == model.provider:
            return Grant(model, secret, own_key=False)
    raise AccessError(403, f"No {model.provider} key is set up for your access code.")
