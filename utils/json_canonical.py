"""JSON 规范化序列化：缓存键与 API 前缀保持一致。"""

from __future__ import annotations

import json
from typing import Any


def canonical_json_dumps(obj: Any) -> str:
    """sort_keys + 紧凑分隔符，避免 indent 差异导致缓存未命中。"""
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
