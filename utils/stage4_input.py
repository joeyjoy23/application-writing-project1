"""Stage4 API 输入压缩与上游哈希（与缓存键一致）。"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

MAX_CHARS_PER_STAGE = 4000
_HEADING = re.compile(r"^#{1,4}\s+.+$", re.MULTILINE)


def _digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def summarize_stage_output(text: str, label: str, *, max_chars: int = MAX_CHARS_PER_STAGE) -> str:
    """结构化摘要：保留标题行与首尾段落，降低 Stage4 输入 token。"""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text

    headings = _HEADING.findall(text)
    head_block = "\n".join(headings[:12]) if headings else ""

    head_budget = min(1800, max_chars // 2)
    tail_budget = max_chars - head_budget - 120
    head = text[:head_budget]
    tail = text[-tail_budget:] if tail_budget > 0 else ""

    parts = [f"【{label} 摘要（原文约 {len(text)} 字，已压缩供 Stage4 使用）】"]
    if head_block:
        parts.append("【保留的标题结构】\n" + head_block)
    parts.append("【开头节选】\n" + head)
    parts.append("【结尾节选】\n" + tail)
    return "\n\n".join(parts)


def build_stage4_user_sections(
    stage1_json: dict[str, Any],
    stage2_output: str,
    stage3_output: str,
) -> tuple[str, str, str]:
    """返回 (json_block, stage2_section, stage3_section) 供 Stage4 user 拼接。"""
    json_block = json.dumps(stage1_json, ensure_ascii=False, indent=2, sort_keys=True)
    s2 = summarize_stage_output(stage2_output, "Stage2")
    s3 = summarize_stage_output(stage3_output, "Stage3")
    return json_block, s2, s3


def build_stage4_upstream_digest(
    stage1_json: dict[str, Any],
    stage2_raw: str,
    stage3_raw: str,
) -> str:
    """缓存键用：与送入 Stage4 的压缩内容一致。"""
    j, s2, s3 = build_stage4_user_sections(stage1_json, stage2_raw, stage3_raw)
    return _digest(j + "\n---\n" + s2 + "\n---\n" + s3)
