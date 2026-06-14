"""Stage 正文统一格式化（网页展示与 Word 导出共用基线）。"""

from __future__ import annotations

from typing import Literal

from utils.parsers import (
    prettify_stage_markdown,
    sanitize_llm_html_breaks,
    strip_reader_self_check,
)

Target = Literal["ui", "word"]


def prepare_stage_text(
    stage: int,
    raw: str | None,
    *,
    target: Target = "ui",
) -> str:
    """
    整理 Stage 原始 Markdown：sanitize → 去自检 → prettify。
    target 预留扩展；当前 ui/word 基线一致，UI 额外样式在 stage_display 中处理。
    """
    _ = target
    if not raw or not str(raw).strip():
        return raw or ""
    text = str(raw).strip()
    if stage == 3:
        text = sanitize_llm_html_breaks(text)
    if stage in (1, 2, 3, 4):
        text = strip_reader_self_check(text)
    return prettify_stage_markdown(text)
