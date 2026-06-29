"""api_key_browser 持久化逻辑测试（不依赖 Streamlit 运行时）。"""

from __future__ import annotations

from services.api_key_persist import merge_provider_key


def test_optimistic_merge_before_hydrate_keeps_provider_key() -> None:
    """hydrate 完成前写入：至少保留当前 provider 的 Key。"""
    keys = merge_provider_key({}, "deepseek", "sk-user-entered", remember=True)
    assert keys == {"deepseek": "sk-user-entered"}


def test_optimistic_merge_does_not_wipe_other_providers_when_merging() -> None:
    """已有其他 provider 的 Key 时，合并写入而非覆盖整表为空。"""
    existing = {"openai": "sk-o", "deepseek": "sk-old"}
    keys = merge_provider_key(existing, "deepseek", "sk-new", remember=True)
    assert keys["openai"] == "sk-o"
    assert keys["deepseek"] == "sk-new"
