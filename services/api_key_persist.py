"""浏览器 localStorage 偏好（模型 + API Key）编解码。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

STORAGE_KEY = "awp_api_keys_v1"


@dataclass(frozen=True)
class BrowserPrefs:
    remember: bool
    keys: dict[str, str]
    provider: str
    model: str
    guest_id: str = ""
    use_llm_cache: bool = True


def parse_storage_payload(raw: str | None) -> BrowserPrefs:
    """解析 localStorage JSON。"""
    if not raw or not str(raw).strip():
        return BrowserPrefs(False, {}, "", "", use_llm_cache=True)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return BrowserPrefs(False, {}, "", "", use_llm_cache=True)
    if not isinstance(data, dict):
        return BrowserPrefs(False, {}, "", "", use_llm_cache=True)

    remember = bool(data.get("remember", False))
    keys_raw = data.get("keys")
    keys: dict[str, str] = {}
    if isinstance(keys_raw, dict):
        keys = {
            str(provider): str(key).strip()
            for provider, key in keys_raw.items()
            if key and str(key).strip()
        }
    provider = str(data.get("provider") or "").strip()
    model = str(data.get("model") or "").strip()
    guest_id = str(data.get("guest_id") or "").strip()
    use_llm_cache = data.get("use_llm_cache", True)
    if isinstance(use_llm_cache, str):
        use_llm_cache = use_llm_cache.strip().lower() not in ("0", "false", "no")
    else:
        use_llm_cache = bool(use_llm_cache)
    return BrowserPrefs(
        remember=remember,
        keys=keys,
        provider=provider,
        model=model,
        guest_id=guest_id,
        use_llm_cache=use_llm_cache,
    )


def build_storage_payload(
    *,
    remember: bool,
    keys: dict[str, str],
    provider: str = "",
    model: str = "",
    guest_id: str = "",
    use_llm_cache: bool = True,
) -> str:
    """序列化为 localStorage JSON。"""
    cleaned = {
        str(p): str(key).strip()
        for p, key in keys.items()
        if key and str(key).strip()
    }
    payload: dict[str, Any] = {
        "remember": bool(remember),
        "keys": cleaned,
        "provider": (provider or "").strip(),
        "model": (model or "").strip(),
    }
    gid = (guest_id or "").strip()
    if gid:
        payload["guest_id"] = gid
    payload["use_llm_cache"] = bool(use_llm_cache)
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
    if remember:
        if trimmed:
            updated[provider] = trimmed
        # 输入框暂空时不删除已记住的 Key（避免加载顺序导致误清）
    else:
        updated.pop(provider, None)
    return updated


def key_for_provider(keys: dict[str, str], provider: str) -> str:
    return keys.get(provider, "")


def prefs_has_content(prefs: BrowserPrefs) -> bool:
    return bool(prefs.keys or prefs.provider or prefs.model or prefs.guest_id)
