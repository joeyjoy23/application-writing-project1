"""浏览器 localStorage：模型选择与 API Key 自动记住。"""

from __future__ import annotations

import json

import streamlit as st
from streamlit_js_eval import (
    get_local_storage,
    remove_local_storage,
    streamlit_js_eval,
)

from services.api_key_persist import (
    STORAGE_KEY,
    BrowserPrefs,
    build_storage_payload,
    key_for_provider,
    merge_provider_key,
    parse_storage_payload,
    prefs_has_content,
)
from utils.config import (
    PROVIDER_MODELS,
    PROVIDER_OPTIONS,
    normalize_agnes_model_id,
    normalize_deepseek_model_id,
    normalize_mimo_model_id,
    normalize_zhipu_model_id,
)


def _normalize_model_for_provider(provider: str, model: str) -> str:
    p = provider.lower()
    m = (model or "").strip()
    if p == "deepseek":
        return normalize_deepseek_model_id(m)
    if p == "zhipu":
        return normalize_zhipu_model_id(m)
    if p == "mimo":
        return normalize_mimo_model_id(m)
    if p == "agnes":
        return normalize_agnes_model_id(m)
    return m


def _apply_provider_model(provider: str, model: str) -> None:
    """将 localStorage 中的 provider/model 写回 session（校验合法）。"""
    if provider and provider in PROVIDER_OPTIONS:
        st.session_state.provider = provider
    p = st.session_state.provider
    if not model:
        return
    normalized = _normalize_model_for_provider(p, model)
    options = PROVIDER_MODELS.get(p, [])
    if normalized in options:
        st.session_state.model = normalized
    elif options:
        st.session_state.model = options[0]


def _safe_set_local_storage(key: str, value: str, *, component_key: str) -> None:
    """写入 localStorage（JSON 转义，避免 Key 含引号时破坏 JS）。"""
    js_ex = f"localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
    streamlit_js_eval(js_expressions=js_ex, key=component_key)


def _normalize_ls_raw(raw: str | None) -> str | None:
    """区分「组件尚未返回」与「localStorage 无此项」。"""
    if raw is None:
        return None
    if raw == "null":
        return ""
    return raw


def hydrate_session_from_browser() -> None:
    """首次加载：恢复上次 provider / model / Key。"""
    if st.session_state.get("_browser_keys_hydrated"):
        return
    # 同一次 rerun 内勿重复挂载 localStorage 组件（会 DuplicateElementKey）
    if st.session_state.get("_browser_ls_hydrate_mounted"):
        return
    st.session_state._browser_ls_hydrate_mounted = True

    raw = _normalize_ls_raw(get_local_storage(STORAGE_KEY, component_key="awp_ls_hydrate"))
    if raw is None:
        attempts = int(st.session_state.get("_browser_ls_attempts") or 0) + 1
        st.session_state._browser_ls_attempts = attempts
        st.session_state._browser_ls_hydrate_mounted = False
        if attempts < 5:
            st.rerun()
        raw = ""

    st.session_state._browser_keys_hydrated = True
    prefs = parse_storage_payload(raw)
    if prefs.provider or prefs.model:
        _apply_provider_model(prefs.provider, prefs.model)
    if prefs.keys:
        st.session_state._stored_api_keys = dict(prefs.keys)
        st.session_state.remember_api_key = prefs.remember
    stored = key_for_provider(prefs.keys, st.session_state.provider) if prefs.keys else ""
    if stored and not (st.session_state.get("api_key") or "").strip():
        st.session_state.api_key = stored
    if prefs.guest_id:
        st.session_state.guest_id = prefs.guest_id
    # 每次打开会话默认勾选 LLM 结果缓存（本页内仍可手动关闭）
    st.session_state.use_llm_cache = True


def persist_session_to_browser(*, force: bool = False) -> None:
    """同步 provider / model / Key 到 localStorage。"""
    remember = bool(st.session_state.get("remember_api_key"))
    keys = dict(st.session_state.get("_stored_api_keys") or {})
    provider = st.session_state.provider
    model = st.session_state.model
    api_key = (st.session_state.get("api_key") or "").strip()

    hydrated = bool(st.session_state.get("_browser_keys_hydrated"))
    if not hydrated and not force:
        # 读取完成前：仅在有 Key 且勾选记住时乐观写入，避免空数据覆盖 localStorage
        if not (remember and api_key):
            return
    elif not hydrated and force and not api_key:
        return

    from db.identity import ensure_guest_id

    guest_id = ensure_guest_id()

    keys = merge_provider_key(keys, provider, api_key, remember=remember)
    st.session_state._stored_api_keys = keys

    prefs = BrowserPrefs(
        remember=remember,
        keys=keys,
        provider=provider,
        model=model,
        guest_id=guest_id,
        use_llm_cache=bool(st.session_state.get("use_llm_cache", True)),
    )
    if not prefs_has_content(prefs):
        if hydrated:
            remove_local_storage(STORAGE_KEY, component_key="awp_ls_remove")
        return

    _safe_set_local_storage(
        STORAGE_KEY,
        build_storage_payload(
            remember=remember,
            keys=keys,
            provider=provider,
            model=model,
            guest_id=guest_id,
            use_llm_cache=bool(st.session_state.get("use_llm_cache", True)),
        ),
        component_key="awp_ls_save",
    )


def stash_provider_key_before_switch(old_provider: str) -> None:
    """切换 provider 前暂存当前 Key。"""
    k = (st.session_state.get("api_key") or "").strip()
    if not k:
        return
    keys = dict(st.session_state.get("_stored_api_keys") or {})
    keys[old_provider] = k
    st.session_state._stored_api_keys = keys


def load_provider_key_after_switch(new_provider: str) -> None:
    """切换 provider 后载入对应 Key。"""
    keys = st.session_state.get("_stored_api_keys") or {}
    st.session_state.api_key = key_for_provider(keys, new_provider)


def clear_browser_saved_keys() -> None:
    """清除本机 localStorage 中的 Key（保留已记住的模型选择）。"""
    st.session_state.api_key = ""
    st.session_state._stored_api_keys = {}
    st.session_state.remember_api_key = True
    st.session_state._browser_keys_hydrated = True
    _safe_set_local_storage(
        STORAGE_KEY,
        build_storage_payload(
            remember=True,
            keys={},
            provider=st.session_state.provider,
            model=st.session_state.model,
        ),
        component_key="awp_ls_clear",
    )
