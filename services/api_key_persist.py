"""API Key localStorage 载荷编解码（无 Streamlit 依赖）。"""

from __future__ import annotations

import json
from typing import Any

STORAGE_KEY = "awp_api_keys_v1"


def parse_storage_payload(raw: str | None) -> tuple[bool, dict[str, str]]:
    """解析 localStorage JSON，返回 (remember, keys_by_provider)。"""
    if not raw or not str(raw).strip():
        return False, {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return False, {}
    if not isinstance(data, dict):
        return False, {}
    remember = bool(data.get("remember", False))
    keys_raw = data.get("keys")
    if not isinstance(keys_raw, dict):
        return remember, {}
    keys = {
        str(provider): str(key).strip()
        for provider, key in keys_raw.items()
        if key and str(key).strip()
    }
    return remember, keys


def build_storage_payload(remember: bool, keys: dict[str, str]) -> str:
    """序列化为 localStorage JSON。"""
    cleaned = {
        str(provider): str(key).strip()
        for provider, key in keys.items()
        if key and str(key).strip()
    }
    payload: dict[str, Any] = {"remember": bool(remember), "keys": cleaned}
    return json.dumps(payload, ensure_ascii=False)


def merge_provider_key(
    keys: dict[str, str],
    provider: str,
    api_key: str,
    *,
    remember: bool,
) -> dict[str, str]:
    """按 remember 开关合并某 provider 的 Key。"""
    updated = dict(keys)
    trimmed = api_key.strip()
    if remember and trimmed:
        updated[provider] = trimmed
    else:
        updated.pop(provider, None)
    return updated


def key_for_provider(keys: dict[str, str], provider: str) -> str:
    return keys.get(provider, "")
