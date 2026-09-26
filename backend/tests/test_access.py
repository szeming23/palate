import pytest
from conftest import make_code

from palate import access, config, db


def test_codes_are_random_and_stored_hashed():
    code, acc = make_code()
    assert code.startswith("plt_")
    assert code != access.generate_code()
    assert "code_hash" not in acc
    assert access.lookup(code)["name"] == "phone"


@pytest.mark.parametrize("bad", ["", "plt_wrong"])
def test_lookup_rejects_unknown_codes(bad):
    make_code()
    assert access.lookup(bad) is None


def test_allowed_models_needs_a_server_key():
    _, acc = make_code(key_names=["missing-key"])
    assert access.allowed_models(acc) == []
    # ...unless the client brings its own key for that provider.
    assert {m.provider for m in access.allowed_models(acc, own_key_provider="anthropic")} == {"anthropic"}


def test_allowed_models_respects_allow_list():
    _, acc = make_code(allowed_models=["claude-haiku-4-5"])
    assert [m.id for m in access.allowed_models(acc)] == ["claude-haiku-4-5"]


def test_authorize_picks_the_server_key():
    _, acc = make_code()
    grant = access.authorize(acc, "claude-haiku-4-5")
    assert grant.api_key == "sk-ant-test"
    assert grant.own_key is False


def test_authorize_prefers_the_clients_own_key():
    _, acc = make_code()
    grant = access.authorize(acc, "claude-haiku-4-5", own_api_key="sk-ant-mine")
    assert grant.api_key == "sk-ant-mine"
    assert grant.own_key is True


@pytest.mark.parametrize(
    ("kwargs", "model", "status"),
    [
        ({}, "gpt-nonexistent", 400),
        ({"allowed_models": ["claude-haiku-4-5"]}, "claude-opus-5", 403),
        ({"key_names": ["missing-key"]}, "claude-haiku-4-5", 403),
    ],
)
def test_authorize_rejects(kwargs, model, status):
    _, acc = make_code(**kwargs)
    with pytest.raises(access.AccessError) as e:
        access.authorize(acc, model)
    assert e.value.status == status


def test_daily_message_limit():
    _, acc = make_code(daily_messages=2)
    for _ in range(2):
        access.authorize(acc, "claude-haiku-4-5")
        db.record_usage(acc["id"], "claude-haiku-4-5", False, 10, 10, 0.0)
    with pytest.raises(access.AccessError) as e:
        access.authorize(acc, "claude-haiku-4-5")
    assert e.value.status == 429
    # The message cap applies even with the client's own key.
    with pytest.raises(access.AccessError):
        access.authorize(acc, "claude-haiku-4-5", own_api_key="sk-ant-mine")


def test_daily_usd_budget_skipped_by_own_key():
    _, acc = make_code(daily_usd=1.0)
    db.record_usage(acc["id"], "claude-opus-5", False, 0, 0, 1.5)
    with pytest.raises(access.AccessError) as e:
        access.authorize(acc, "claude-opus-5")
    assert e.value.status == 429
    assert access.authorize(acc, "claude-opus-5", own_api_key="sk-ant-mine").own_key


def test_own_key_spend_does_not_count_towards_budget():
    _, acc = make_code(daily_usd=1.0)
    db.record_usage(acc["id"], "claude-opus-5", True, 0, 0, 5.0)
    assert access.today_usage(acc) == {"messages": 1, "cost_usd": 0.0}
    access.authorize(acc, "claude-opus-5")


def test_usage_before_today_is_ignored():
    _, acc = make_code(daily_messages=1)
    db.record_usage(acc["id"], "claude-haiku-4-5", False, 0, 0, 0.0)
    with db.connect() as conn:
        conn.execute("UPDATE usage SET created_at = '2000-01-01T00:00:00+00:00'")
    assert access.today_usage(acc)["messages"] == 0


def test_start_of_today_is_singapore_midnight():
    # SG is UTC+8 with no DST, so local midnight is always 16:00 UTC.
    assert config.TIMEZONE == "Asia/Singapore"
    assert access.start_of_today_utc().endswith("T16:00:00+00:00")
