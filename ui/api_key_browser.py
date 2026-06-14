"""浏览器 localStorage：模型选择与 API Key 自动记住。"""

from __future__ import annotations

import streamlit as st
from streamlit_js_eval import get_local_storage, remove_local_storage, set_local_storage

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


def hydrate_session_from_browser() -> None:
    """首次加载：恢复上次 provider / model / Key。"""
    if st.session_state.get("_browser_keys_hydrated"):
        return

    raw = get_local_storage(STORAGE_KEY, component_key="awp_ls_hydrate")
    if raw is None:
        if not st.session_state.get("_browser_ls_tried"):
            st.session_state._browser_ls_tried = True
            return
        raw = ""

    st.session_state._browser_keys_hydrated = True
    prefs = parse_storage_payload(raw)
    if prefs.provider or prefs.model:
        _apply_provider_model(prefs.provider, prefs.model)
    if prefs.keys:
        st.session_state._stored_api_keys = dict(prefs.keys)
        st.session_state.remember_api_key = prefs.remember
    if prefs.keys and not (st.session_state.get("api_key") or "").strip():
        stored = key_for_provider(prefs.keys, st.session_state.provider)
        if stored:
            st.session_state.api_key = stored


def persist_session_to_browser() -> None:
    """同步 provider / model / Key 到 localStorage。"""
    remember = bool(st.session_state.get("remember_api_key"))
    keys = dict(st.session_state.get("_stored_api_keys") or {})
    provider = st.session_state.provider
    model = st.session_state.model
    api_key = st.session_state.get("api_key") or ""

    keys = merge_provider_key(keys, provider, api_key, remember=remember)
    st.session_state._stored_api_keys = keys

    prefs = BrowserPrefs(
        remember=remember,
        keys=keys,
        provider=provider,
        model=model,
    )
    if not prefs_has_content(prefs):
        remove_local_storage(STORAGE_KEY, component_key="awp_ls_remove")
        return

    set_local_storage(
        STORAGE_KEY,
        build_storage_payload(
            remember=remember,
            keys=keys,
            provider=provider,
            model=model,
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
    set_local_storage(
        STORAGE_KEY,
        build_storage_payload(
            remember=True,
            keys={},
            provider=st.session_state.provider,
            model=st.session_state.model,
        ),
        component_key="awp_ls_clear",
    )
