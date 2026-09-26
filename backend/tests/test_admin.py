import sys

import pytest

from palate import access, admin, db


def cli(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["palate.admin", *args])
    admin.main()


def test_add_prints_a_working_code(monkeypatch, capsys):
    cli(monkeypatch, "codes", "add", "phone", "--key", "anthropic-main", "--daily-usd", "3")
    code = next(w for w in capsys.readouterr().out.split() if w.startswith("plt_"))
    acc = access.lookup(code)
    assert acc["name"] == "phone"
    assert acc["user_id"] == "me"
    assert acc["daily_usd"] == 3.0


@pytest.mark.parametrize(
    "args",
    [
        ["--key", "no-such-key"],
        ["--key", "anthropic-main", "--models", "gpt-9"],
    ],
)
def test_add_rejects_bad_input(monkeypatch, args):
    with pytest.raises(SystemExit):
        cli(monkeypatch, "codes", "add", "phone", *args)
    assert db.list_access_codes() == []


def test_duplicate_name_and_remove(monkeypatch, capsys):
    cli(monkeypatch, "codes", "add", "phone", "--key", "anthropic-main")
    with pytest.raises(SystemExit, match="already exists"):
        cli(monkeypatch, "codes", "add", "phone", "--key", "anthropic-main")
    cli(monkeypatch, "codes", "list")
    assert "phone" in capsys.readouterr().out
    cli(monkeypatch, "codes", "remove", "phone")
    assert db.list_access_codes() == []


def test_keys_are_masked(monkeypatch, capsys):
    cli(monkeypatch, "keys")
    out = capsys.readouterr().out
    assert "...test" in out
    assert "sk-ant-test" not in out
