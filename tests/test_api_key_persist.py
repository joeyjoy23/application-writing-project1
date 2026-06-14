"""services/api_key_persist 单元测试。"""

from __future__ import annotations

from services.api_key_persist import (
    BrowserPrefs,
    build_storage_payload,
    key_for_provider,
    merge_provider_key,
    parse_storage_payload,
    prefs_has_content,
)


def test_parse_empty_returns_defaults() -> None:
    prefs = parse_storage_payload(None)
    assert prefs == BrowserPrefs(False, {}, "", "")


def test_build_and_parse_roundtrip() -> None:
    raw = build_storage_payload(
        remember=True,
        keys={"deepseek": "sk-test", "openai": "sk-o"},
        provider="deepseek",
        model="deepseek-v4-pro",
    )
    prefs = parse_storage_payload(raw)
    assert prefs.remember is True
    assert prefs.keys == {"deepseek": "sk-test", "openai": "sk-o"}
    assert prefs.provider == "deepseek"
    assert prefs.model == "deepseek-v4-pro"


def test_parse_legacy_payload_without_model_fields() -> None:
    raw = build_storage_payload(remember=True, keys={"deepseek": "sk-x"})
    prefs = parse_storage_payload(raw)
    assert prefs.keys == {"deepseek": "sk-x"}
    assert prefs.provider == ""
    assert prefs.model == ""


def test_parse_invalid_json() -> None:
    prefs = parse_storage_payload("{not json")
    assert prefs.keys == {}


def test_merge_provider_key_remember_on() -> None:
    keys = merge_provider_key({}, "deepseek", "  sk-x  ", remember=True)
    assert keys == {"deepseek": "sk-x"}


def test_merge_provider_key_remember_off_removes() -> None:
    keys = merge_provider_key({"deepseek": "sk-x"}, "deepseek", "sk-x", remember=False)
    assert keys == {}


def test_key_for_provider() -> None:
    assert key_for_provider({"deepseek": "sk-a"}, "deepseek") == "sk-a"
    assert key_for_provider({}, "openai") == ""


def test_prefs_has_content() -> None:
    assert prefs_has_content(BrowserPrefs(False, {}, "deepseek", ""))
    assert not prefs_has_content(BrowserPrefs(False, {}, "", ""))
