"""历史题目原图：7 天保留期与过期判断（无 Streamlit / DB 依赖）。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from utils.datetime_util import utc_now_str

_STAMP_FMT = "%Y-%m-%d %H:%M:%S"


def history_image_retention_days() -> int:
    raw = (os.getenv("HISTORY_IMAGE_RETENTION_DAYS") or "7").strip()
    try:
        days = int(raw)
    except ValueError:
        days = 7
    return max(1, days)


def history_image_expires_at(*, from_utc: str | None = None) -> str:
    """自给定 UTC 时刻（或当前）起算保留截止时刻（UTC 字符串）。"""
    if from_utc and from_utc.strip():
        base = datetime.strptime(from_utc.strip(), _STAMP_FMT).replace(tzinfo=timezone.utc)
    else:
        base = datetime.now(timezone.utc)
    expire = base + timedelta(days=history_image_retention_days())
    return expire.strftime(_STAMP_FMT)


def is_history_image_expired(expires_at: str | None) -> bool:
    exp = (expires_at or "").strip()
    if not exp:
        return True
    return exp < utc_now_str()


def history_image_row_to_session(row: dict) -> dict:
    """DB 行 → session_state.question_image 形状。"""
    return {
        "mime": row.get("mime") or "image/jpeg",
        "b64": row["image_b64"],
        "name": row.get("name") or "history.jpg",
        "expires_at": row.get("expires_at"),
    }
