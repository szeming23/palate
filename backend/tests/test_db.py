import sqlite3

import pytest

from palate import db


def test_init_is_idempotent():
    db.init()
    db.init()


def test_profile_roundtrip_and_overwrite():
    assert db.get_profile("me") == {}
    db.set_profile("me", {"dietary": "halal"})
    db.set_profile("me", {"dietary": "vegetarian"})
    assert db.get_profile("me") == {"dietary": "vegetarian"}


def test_memories_are_per_user():
    mid = db.add_memory("me", "fact", "Dislikes coriander")
    db.add_memory("friend", "location", "Works in Jurong")
    assert [m["content"] for m in db.list_memories("me")] == ["Dislikes coriander"]
    # Another user can't delete my memory.
    assert db.delete_memory("friend", mid) is False
    assert db.delete_memory("me", mid) is True
    assert db.list_memories("me") == []


def test_memory_kind_is_constrained():
    with pytest.raises(sqlite3.IntegrityError):
        db.add_memory("me", "secret", "x")


def test_recent_messages_are_oldest_first_and_limited():
    for i in range(5):
        db.add_message("me", "user", f"msg {i}")
    db.add_message("me", "assistant", "reply", cards=[{"place_id": "p1"}])
    msgs = db.recent_messages("me", 3)
    assert [m["content"] for m in msgs] == ["msg 3", "msg 4", "reply"]
    assert msgs[-1]["cards"] == [{"place_id": "p1"}]
    assert msgs[0]["cards"] == []


def test_clear_messages_only_clears_that_user():
    db.add_message("me", "user", "hi")
    db.add_message("friend", "user", "hi")
    db.clear_messages("me")
    assert db.recent_messages("me", 10) == []
    assert len(db.recent_messages("friend", 10)) == 1


def test_feedback_roundtrip():
    rid = db.add_recommendation("me", "p1", "Tian Tian", "chicken rice")
    db.add_recommendation("me", "p2", "No feedback", "chicken rice")
    assert db.set_feedback("friend", rid, "up") is False
    assert db.set_feedback("me", rid, "up") is True
    assert db.recent_feedback("me") == [{"name": "Tian Tian", "query": "chicken rice", "feedback": "up"}]
    db.set_feedback("me", rid, None)
    assert db.recent_feedback("me") == []


def test_access_code_names_are_unique():
    db.add_access_code("phone", "h1", "me", ["k"], None, None, None)
    with pytest.raises(sqlite3.IntegrityError):
        db.add_access_code("phone", "h2", "me", ["k"], None, None, None)


def test_delete_access_code():
    db.add_access_code("phone", "h1", "me", ["k"], ["claude-haiku-4-5"], 5, 1.0)
    [row] = db.list_access_codes()
    assert row["allowed_models"] == ["claude-haiku-4-5"]
    assert db.delete_access_code("phone") is True
    assert db.delete_access_code("phone") is False
    assert db.get_access_code_by_hash("h1") is None
