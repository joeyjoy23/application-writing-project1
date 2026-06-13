"""历史记录：本地 SQLite 或 Neon PostgreSQL（由 DATABASE_URL 决定）。"""

from __future__ import annotations

import logging
import os
from typing import Any

import streamlit as st

from db.common import format_stages_mask, make_question_hash
from db.identity import (
    admin_password_configured,
    ensure_guest_id,
    history_scope,
    is_history_admin,
    logout_admin,
    try_admin_login,
)

logger = logging.getLogger("app.db")

__all__ = [
    "init_db",
    "save_record",
    "upsert_record",
    "get_all_records",
    "count_records",
    "get_record_by_id",
    "delete_record",
    "toggle_star",
    "format_stages_mask",
    "make_question_hash",
    "ensure_guest_id",
    "is_history_admin",
    "try_admin_login",
    "logout_admin",
    "admin_password_configured",
    "history_scope",
    "using_postgres",
    "invalidate_history_cache",
    "get_cached_stage_result",
    "save_cached_stage_result",
]


def using_postgres() -> bool:
    return bool((os.getenv("DATABASE_URL") or "").strip())


def _backend():
    if using_postgres():
        from db import postgres_backend

        return postgres_backend
    from db import sqlite_backend

    return sqlite_backend


def init_db() -> None:
    _backend().init_db()


def _scope_kwargs() -> dict[str, Any]:
    owner_id, admin = history_scope()
    return {"owner_id": owner_id, "admin": admin}


def invalidate_history_cache() -> None:
    get_all_records.clear()
    count_records.clear()


def save_record(
    topic: str,
    model: str,
    content: str,
    *,
    raw_input: str | None = None,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> int:
    return _backend().save_record(
        topic,
        model,
        content,
        raw_input=raw_input,
        word_count=word_count,
        stages_mask=stages_mask,
        **_scope_kwargs(),
    )


def upsert_record(
    question: str,
    model: str,
    content: str,
    *,
    raw_input: str | None = None,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> tuple[int, bool]:
    result = _backend().upsert_record(
        question,
        model,
        content,
        raw_input=raw_input,
        word_count=word_count,
        stages_mask=stages_mask,
        owner_id=history_scope()[0],
    )
    invalidate_history_cache()
    return result


@st.cache_data(show_spinner=False)
def get_all_records(
    keyword: str,
    scope_owner_id: str,
    scope_admin: bool,
    *,
    limit: int = 20,
    offset: int = 0,
    starred_only: bool = False,
) -> list[dict[str, Any]]:
    return _backend().get_all_records(
        keyword,
        limit=limit,
        offset=offset,
        owner_id=scope_owner_id,
        admin=scope_admin,
        starred_only=starred_only,
    )


@st.cache_data(ttl=10, show_spinner=False)
def count_records(
    keyword: str,
    scope_owner_id: str,
    scope_admin: bool,
    *,
    starred_only: bool = False,
) -> int:
    return _backend().count_records(
        keyword,
        owner_id=scope_owner_id,
        admin=scope_admin,
        starred_only=starred_only,
    )


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    return _backend().get_record_by_id(record_id, **_scope_kwargs())


def delete_record(record_id: int) -> bool:
    ok = _backend().delete_record(record_id, **_scope_kwargs())
    if ok:
        invalidate_history_cache()
    return ok


def toggle_star(record_id: int, starred: bool, *, owner_id: str, admin: bool) -> bool:
    ok = _backend().toggle_star(record_id, starred, owner_id=owner_id, admin=admin)
    if ok:
        invalidate_history_cache()
    return ok
