"""分享链接有效期与 URL 拼接（无 DB / UI 依赖）。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from utils.datetime_util import _STAMP_FMT

SHARE_TTL_DAYS = 7


def share_ttl_days() -> int:
    raw = (os.getenv("SHARE_TTL_DAYS") or "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return SHARE_TTL_DAYS


def expires_at_from_now(*, days: int | None = None) -> str:
    d = days if days is not None else share_ttl_days()
    dt = datetime.now(timezone.utc) + timedelta(days=d)
    return dt.strftime(_STAMP_FMT)


def is_share_expired(expires_at: str, *, now_utc: datetime | None = None) -> bool:
    raw = (expires_at or "").strip()
    if not raw:
        return True
    now = now_utc or datetime.now(timezone.utc)
    try:
        exp = datetime.strptime(raw, _STAMP_FMT).replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return now >= exp


def build_share_url(token: str, base_url: str) -> str:
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return ""
    qs = urlencode({"share": token})
    return f"{base}/?{qs}"
