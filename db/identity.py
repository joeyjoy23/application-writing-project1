"""访客 ID 与管理员模式（Neon 多用户隔离）。"""

from __future__ import annotations

import os
import uuid

import streamlit as st


def _admin_password_from_env() -> str:
    """Streamlit Cloud Secrets 或 .env 中的 ADMIN_PASSWORD。"""
    try:
        if hasattr(st, "secrets") and "ADMIN_PASSWORD" in st.secrets:
            return str(st.secrets["ADMIN_PASSWORD"]).strip()
    except Exception:
        pass
    return (os.getenv("ADMIN_PASSWORD") or "").strip()


def ensure_guest_id() -> str:
    """每个浏览器会话一个 guest_id，用于隔离历史记录。

    本地 SQLite 模式下返回固定值 ``"local"``，确保服务重启/页面刷新后
    历史记录和 LLM 缓存仍可命中（不会因 session 变更产生新 UUID 而丢失）。
    仅在 Neon PostgreSQL 多用户云部署时才使用会话级 UUID。
    """
    # 本地模式：固定 owner_id，跨 session 稳定
    if not (os.getenv("DATABASE_URL") or "").strip():
        return "local"
    # 云模式：每会话一个 UUID 做多租户隔离
    gid = st.session_state.get("guest_id")
    if not gid:
        gid = str(uuid.uuid4())
        st.session_state.guest_id = gid
    return gid


def is_history_admin() -> bool:
    return bool(st.session_state.get("is_history_admin"))


def try_admin_login(password: str) -> bool:
    expected = _admin_password_from_env()
    if not expected:
        return False
    if (password or "").strip() == expected:
        st.session_state.is_history_admin = True
        return True
    return False


def logout_admin() -> None:
    st.session_state.is_history_admin = False


def admin_password_configured() -> bool:
    return bool(_admin_password_from_env())


def history_scope() -> tuple[str, bool]:
    """返回 (owner_id, is_admin)。管理员查看时不按 owner 过滤。"""
    return ensure_guest_id(), is_history_admin()
