import pytest

from palate import config


def test_llm_keys_parsed_from_env(monkeypatch):
    monkeypatch.setenv("PALATE_KEY_ANTHROPIC_MAIN", "anthropic:sk-ant-abc")
    monkeypatch.setenv("PALATE_KEY_ANTHROPIC_DEV", " Anthropic : sk-ant-def ")
    keys = config._load_llm_keys()
    assert keys["anthropic-main"] == ("anthropic", "sk-ant-abc")
    assert keys["anthropic-dev"] == ("anthropic", "sk-ant-def")


def test_empty_key_vars_are_skipped(monkeypatch):
    monkeypatch.setenv("PALATE_KEY_UNUSED", "")
    assert "unused" not in config._load_llm_keys()


@pytest.mark.parametrize("value", ["sk-ant-no-provider", "anthropic:"])
def test_malformed_key_raises(monkeypatch, value):
    monkeypatch.setenv("PALATE_KEY_BAD", value)
    with pytest.raises(RuntimeError, match="PALATE_KEY_BAD"):
        config._load_llm_keys()
