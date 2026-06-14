"""历史库共用工具（哈希、摘要、展示）。"""

from __future__ import annotations

import hashlib


def make_question_hash(question: str) -> str:
    """同一道题用固定哈希，便于与模型名、用户组合去重。"""
    normalized = (question or "").strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def topic_summary(question: str, *, max_len: int = 100) -> str:
    return (question or "（无题目）").strip().replace("\n", " ")[:max_len]


def format_stages_mask(mask: str | None) -> str:
    """将 1010 转为 S1✓ S2· S3✓ S4· 便于列表展示。"""
    m = (mask or "0000").ljust(4, "0")[:4]
    parts = []
    for i, ch in enumerate(m, start=1):
        parts.append(f"S{i}{'✓' if ch == '1' else '·'}")
    return " ".join(parts)


def format_usage_total(record: dict[str, object]) -> str:
    """格式化 token 总量用于列表展示，如 '12.3k'。"""
    pt = int(record.get("prompt_tokens") or 0)
    ct = int(record.get("completion_tokens") or 0)
    total = pt + ct
    if total == 0:
        return "—"
    if total >= 1000:
        return f"{total / 1000:.1f}k"
    return str(total)


def format_usage_detail(record: dict[str, object]) -> str:
    """格式化 token 详情用于详情页展示。"""
    pt = int(record.get("prompt_tokens") or 0)
    ct = int(record.get("completion_tokens") or 0)
    cat = int(record.get("cached_tokens") or 0)
    if pt == 0 and ct == 0:
        return "无用量记录"
    parts = [f"输入 {pt:,}", f"输出 {ct:,}"]
    if cat:
        parts.append(f"缓存命中 {cat:,}")
    return " · ".join(parts)
