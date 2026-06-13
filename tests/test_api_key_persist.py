"""services/api_key_persist 单元测试。"""

from __future__ import annotations

from services.api_key_persist import (
    build_storage_payload,
    key_for_provider,
    merge_provider_key,
    parse_storage_payload,
)


def test_parse_empty_returns_defaults() -> None:
    remember, keys = parse_storage_payload(None)
    assert remember is False
    assert keys == {}


def test_build_and_parse_roundtrip() -> None:
    raw = build_storage_payload(True, {"deepseek": "sk-test", "openai": "sk-o"})
    remember, keys = parse_storage_payload(raw)
    assert remember is True
    assert keys == {"deepseek": "sk-test", "openai": "sk-o"}


def test_parse_invalid_json() -> None:
    remember, keys = parse_storage_payload("{not json")
    assert remember is False
    assert keys == {}


def test_merge_provider_key_remember_on() -> None:
    keys = merge_provider_key({}, "deepseek", "  sk-x  ", remember=True)
    assert keys == {"deepseek": "sk-x"}


def test_merge_provider_key_remember_off_removes() -> None:
    keys = merge_provider_key({"deepseek": "sk-x"}, "deepseek", "sk-x", remember=False)
    assert keys == {}


def test_key_for_provider() -> None:
    assert key_for_provider({"deepseek": "sk-a"}, "deepseek") == "sk-a"
    assert key_for_provider({}, "openai") == ""
