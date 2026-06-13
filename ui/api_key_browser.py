"""浏览器 localStorage 读写 API Key（opt-in 记住）。"""

from __future__ import annotations

import streamlit as st
from streamlit_js_eval import get_local_storage, remove_local_storage, set_local_storage

from services.api_key_persist import (
    STORAGE_KEY,
    build_storage_payload,
    key_for_provider,
    merge_provider_key,
    parse_storage_payload,
)


def hydrate_session_from_browser() -> None:
    """首次加载时从 localStorage 恢复 remember 与当前 provider 的 Key。"""
    if st.session_state.get("_browser_keys_hydrated"):
        return

    raw = get_local_storage(STORAGE_KEY, component_key="awp_ls_hydrate")
    if raw is None:
        if not st.session_state.get("_browser_ls_tried"):
            st.session_state._browser_ls_tried = True
            return
        raw = ""

    st.session_state._browser_keys_hydrated = True
    remember, keys = parse_storage_payload(raw)
    st.session_state.remember_api_key = remember
    st.session_state._stored_api_keys = keys

    if remember and not (st.session_state.get("api_key") or "").strip():
        provider = st.session_state.provider
        stored = key_for_provider(keys, provider)
        if stored:
            st.session_state.api_key = stored


def persist_session_to_browser() -> None:
    """将 session 中 remember 与 keys 同步到 localStorage。"""
    remember = bool(st.session_state.get("remember_api_key"))
    keys = dict(st.session_state.get("_stored_api_keys") or {})
    provider = st.session_state.provider
    api_key = st.session_state.get("api_key") or ""

    keys = merge_provider_key(keys, provider, api_key, remember=remember)
    st.session_state._stored_api_keys = keys

    if remember and keys:
        set_local_storage(
            STORAGE_KEY,
            build_storage_payload(True, keys),
            component_key="awp_ls_save",
        )
    else:
        remove_local_storage(STORAGE_KEY, component_key="awp_ls_remove")


def stash_provider_key_before_switch(old_provider: str) -> None:
    """切换 provider 前，把当前输入框 Key 写入内存 dict。"""
    if not st.session_state.get("remember_api_key"):
        return
    keys = dict(st.session_state.get("_stored_api_keys") or {})
    keys = merge_provider_key(
        keys,
        old_provider,
        st.session_state.get("api_key") or "",
        remember=True,
    )
    st.session_state._stored_api_keys = keys


def load_provider_key_after_switch(new_provider: str) -> None:
    """切换 provider 后，从内存 dict 载入对应 Key。"""
    if not st.session_state.get("remember_api_key"):
        return
    keys = st.session_state.get("_stored_api_keys") or {}
    st.session_state.api_key = key_for_provider(keys, new_provider)


def clear_browser_saved_keys() -> None:
    """清除本机 localStorage 与 session 中的手动 Key。"""
    remove_local_storage(STORAGE_KEY, component_key="awp_ls_clear")
    st.session_state.api_key = ""
    st.session_state.remember_api_key = False
    st.session_state._stored_api_keys = {}
    st.session_state._browser_keys_hydrated = True
