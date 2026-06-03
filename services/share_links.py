"""只读分享链接：创建、查询活跃链接、公开预览加载。"""

from __future__ import annotations

from typing import Any

import streamlit as st

from db import using_postgres
from utils.share_util import build_share_url


def get_app_base_url() -> str:
    try:
        if hasattr(st, "secrets") and "APP_BASE_URL" in st.secrets:
            return str(st.secrets["APP_BASE_URL"]).strip().rstrip("/")
    except Exception:
        pass
    import os

    return (os.getenv("APP_BASE_URL") or "").strip().rstrip("/")


def create_or_refresh_share_link(
    history_id: int, *, viewer_owner_id: str, admin: bool = False
) -> str | None:
    if not using_postgres():
        return None
    from db import postgres_backend

    return postgres_backend.create_or_refresh_share_link(
        history_id, viewer_owner_id=viewer_owner_id, admin=admin
    )


def get_active_share_url(history_id: int, *, base_url: str) -> str | None:
    if not using_postgres():
        return None
    from db import postgres_backend

    token = postgres_backend.get_active_share_token(history_id)
    if not token:
        return None
    return build_share_url(token, base_url) or None


def fetch_public_share(token: str) -> dict[str, Any] | None:
    if not using_postgres():
        return None
    from db import postgres_backend

    return postgres_backend.get_public_share((token or "").strip())
