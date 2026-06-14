"""历史时间：库内统一 UTC，展示转为北京时间（可配置 APP_TIMEZONE）。"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

_STAMP_FMT = "%Y-%m-%d %H:%M:%S"
_LIST_FMT = "%Y-%m-%d %H:%M"
_STAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def display_tz() -> ZoneInfo:
    name = (os.getenv("APP_TIMEZONE") or "Asia/Shanghai").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def utc_now_str() -> str:
    """写入数据库的创建/更新时间（UTC，无时区后缀）。"""
    return datetime.now(timezone.utc).strftime(_STAMP_FMT)


def format_created_at_display(stored: str | None) -> str:
    """
    将库内 UTC 时间戳转为用户时区显示。
    历史数据在 Streamlit Cloud 上亦为 UTC 的 naive 字符串。
    """
    raw = (stored or "").strip()
    if not raw:
        return "—"
    if not _STAMP_RE.match(raw):
        return raw
    dt_utc = datetime.strptime(raw, _STAMP_FMT).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(display_tz()).strftime(_STAMP_FMT)


def format_created_at_list(stored: str | None) -> str:
    """历史列表用：展示到分钟，不含秒。"""
    raw = (stored or "").strip()
    if not raw:
        return "—"
    if not _STAMP_RE.match(raw):
        return raw[:16] if len(raw) >= 16 else raw
    dt_utc = datetime.strptime(raw, _STAMP_FMT).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(display_tz()).strftime(_LIST_FMT)


def created_at_date_part(stored: str | None) -> str:
    """导出文件名用的日期（按展示时区）。"""
    shown = format_created_at_display(stored)
    return shown[:10] if len(shown) >= 10 else shown
