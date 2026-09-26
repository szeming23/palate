"""SQLite storage. Every table carries user_id so we can go multi-user later."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    user_id    TEXT PRIMARY KEY,
    data       TEXT NOT NULL DEFAULT '{}',   -- explicit preferences (JSON)
    updated_at TEXT NOT NULL
);

-- Things learned from chat ("hates coriander") and location habits ("works at Raffles Place").
CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('fact', 'location')),
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    cards      TEXT,                          -- JSON list of place cards (assistant only)
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    place_id   TEXT NOT NULL,
    name       TEXT NOT NULL,
    query      TEXT NOT NULL,
    feedback   TEXT CHECK (feedback IN ('up', 'down')),
    created_at TEXT NOT NULL
);

-- Access codes: what a client sends as its "password". Only the SHA-256 hash is stored.
CREATE TABLE IF NOT EXISTS access_codes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL UNIQUE,          -- e.g. "my-phone", "dev-laptop"
    code_hash      TEXT NOT NULL UNIQUE,
    user_id        TEXT NOT NULL,                 -- whose memory/history this code uses
    key_names      TEXT NOT NULL,                 -- JSON list of LLM key names (see config.LLM_KEYS)
    allowed_models TEXT,                          -- JSON list, NULL = all models
    daily_messages INTEGER,                       -- NULL = unlimited
    daily_usd      REAL,                          -- NULL = unlimited
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    code_id       INTEGER NOT NULL,
    model         TEXT NOT NULL,
    own_key       INTEGER NOT NULL DEFAULT 0,     -- 1 if the client paid with its own key
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd      REAL NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_usage_code ON usage(code_id, created_at);
CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id);
CREATE INDEX IF NOT EXISTS idx_recs_user ON recommendations(user_id, id);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --- profile ---------------------------------------------------------------


def get_profile(user_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    return json.loads(row["data"]) if row else {}


def set_profile(user_id: str, data: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO profiles (user_id, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
            (user_id, json.dumps(data), now()),
        )


# --- memories --------------------------------------------------------------


def list_memories(user_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, kind, content, created_at FROM memories WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_memory(user_id: str, kind: str, content: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO memories (user_id, kind, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, kind, content, now()),
        )
        return cur.lastrowid


def delete_memory(user_id: str, memory_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM memories WHERE id = ? AND user_id = ?", (memory_id, user_id))
        return cur.rowcount > 0


# --- chat history ----------------------------------------------------------


def add_message(user_id: str, role: str, content: str, cards: list | None = None) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO messages (user_id, role, content, cards, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, role, content, json.dumps(cards) if cards else None, now()),
        )
        return cur.lastrowid


def recent_messages(user_id: str, limit: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, role, content, cards, created_at FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    out = []
    for r in reversed(rows):
        d = dict(r)
        d["cards"] = json.loads(d["cards"]) if d["cards"] else []
        out.append(d)
    return out


def clear_messages(user_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))


# --- recommendations & feedback --------------------------------------------


def add_recommendation(user_id: str, place_id: str, name: str, query: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO recommendations (user_id, place_id, name, query, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, place_id, name, query, now()),
        )
        return cur.lastrowid


def set_feedback(user_id: str, rec_id: int, feedback: str | None) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE recommendations SET feedback = ? WHERE id = ? AND user_id = ?",
            (feedback, rec_id, user_id),
        )
        return cur.rowcount > 0


def recent_feedback(user_id: str, limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT name, query, feedback FROM recommendations "
            "WHERE user_id = ? AND feedback IS NOT NULL ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# --- access codes & usage --------------------------------------------------


def _code_row(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    d["key_names"] = json.loads(d["key_names"])
    d["allowed_models"] = json.loads(d["allowed_models"]) if d["allowed_models"] else None
    d.pop("code_hash", None)
    return d


def add_access_code(
    name: str,
    code_hash: str,
    user_id: str,
    key_names: list[str],
    allowed_models: list[str] | None,
    daily_messages: int | None,
    daily_usd: float | None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO access_codes (name, code_hash, user_id, key_names, allowed_models, "
            "daily_messages, daily_usd, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                code_hash,
                user_id,
                json.dumps(key_names),
                json.dumps(allowed_models) if allowed_models else None,
                daily_messages,
                daily_usd,
                now(),
            ),
        )
        return cur.lastrowid


def get_access_code_by_hash(code_hash: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM access_codes WHERE code_hash = ?", (code_hash,)).fetchone()
    return _code_row(row)


def list_access_codes() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM access_codes ORDER BY id").fetchall()
    return [_code_row(r) for r in rows]


def delete_access_code(name: str) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM access_codes WHERE name = ?", (name,))
        return cur.rowcount > 0


def record_usage(
    code_id: int, model: str, own_key: bool, input_tokens: int, output_tokens: int, cost_usd: float
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO usage (code_id, model, own_key, input_tokens, output_tokens, cost_usd, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code_id, model, int(own_key), input_tokens, output_tokens, cost_usd, now()),
        )


def usage_since(code_id: int, since_utc_iso: str) -> dict:
    """Messages and server-paid spend for a code since a UTC timestamp."""
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS messages, "
            "COALESCE(SUM(CASE WHEN own_key = 0 THEN cost_usd ELSE 0 END), 0) AS cost_usd "
            "FROM usage WHERE code_id = ? AND created_at >= ?",
            (code_id, since_utc_iso),
        ).fetchone()
    return {"messages": row["messages"], "cost_usd": round(row["cost_usd"], 4)}
