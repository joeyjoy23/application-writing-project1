"""WorkflowState 序列化与历史记录字段还原（无 UI 依赖）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from utils.datetime_util import created_at_date_part, display_tz
from workflow import (
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    WorkflowState,
)


def make_export_word_filename(model: str, date_str: str | None = None) -> str:
    """Word 导出文件名：应用文分析_YYYY-MM-DD_模型名.docx"""
    if not date_str:
        date_str = datetime.now(display_tz()).strftime("%Y-%m-%d")
    else:
        date_str = created_at_date_part(date_str)
    safe_model = re.sub(r'[<>:"/\\|?*]', "-", (model or "").strip()) or "model"
    return f"应用文分析_{date_str}_{safe_model}.docx"


def make_export_html_filename(model: str, date_str: str | None = None) -> str:
    """HTML 导出文件名：与 Word 同名规则，扩展名为 .html"""
    return make_export_word_filename(model, date_str).removesuffix(".docx") + ".html"


def make_export_json_filename(model: str, date_str: str | None = None) -> str:
    """JSON 导出文件名：与 Word 同名规则，扩展名为 .json"""
    return make_export_word_filename(model, date_str).removesuffix(".docx") + ".json"


def workflow_stages_mask(state: WorkflowState) -> str:
    """四位标记：stage1~4 是否已有内容。"""
    return "".join(
        "1" if flag else "0"
        for flag in (
            bool(state.stage1),
            bool(state.stage2),
            bool(state.stage3),
            bool(state.stage4),
        )
    )


def workflow_content_length(state: WorkflowState) -> int:
    """统计备课包各阶段文本总字数。"""
    total = len(state.question or "")
    if state.stage1:
        total += len(state.stage1.human_summary or "")
    if state.stage2:
        total += len(state.stage2.raw or "")
    if state.stage3:
        total += len(state.stage3.raw or "")
    if state.stage4:
        total += len(state.stage4.raw or "")
    return total


def workflow_state_payload(
    state: WorkflowState,
    *,
    provider: str,
    model: str,
    raw_input: str | None = None,
    student_level: str | None = None,
) -> dict[str, Any]:
    """构造写入数据库的 JSON 对象。"""
    raw = (raw_input if raw_input is not None else state.question or "").strip()
    payload: dict[str, Any] = {
        "raw_input": raw,
        "question": raw,
        "provider": provider,
        "model": model,
        "stage1_summary": state.stage1.human_summary if state.stage1 else None,
        "stage1_json": state.stage1.structured_json if state.stage1 else None,
        "stage2": state.stage2.raw if state.stage2 else None,
        "stage3": state.stage3.raw if state.stage3 else None,
        "stage4": state.stage4.raw if state.stage4 else None,
        "errors": state.errors,
    }
    if state.stage4 and student_level:
        payload["student_level"] = student_level
    return payload


def workflow_state_to_json(
    state: WorkflowState,
    *,
    provider: str,
    model: str,
    raw_input: str | None = None,
    student_level: str | None = None,
) -> str:
    """将备课包序列化为 JSON 字符串存入数据库。"""
    return json.dumps(
        workflow_state_payload(
            state,
            provider=provider,
            model=model,
            raw_input=raw_input,
            student_level=student_level,
        ),
        ensure_ascii=False,
    )


def resolve_raw_input(
    record: dict[str, Any], data: dict[str, Any] | None = None
) -> str:
    """还原用户当初粘贴的完整题目（兼容旧记录）。"""
    raw_col = (record.get("raw_input") or "").strip()
    if raw_col:
        return raw_col
    if data is None:
        try:
            data = json.loads(record.get("full_content") or "{}")
        except json.JSONDecodeError:
            data = {}
    for key in ("raw_input", "question"):
        val = (data.get(key) or "").strip()
        if val:
            return val
    s1 = data.get("stage1_json") or {}
    if isinstance(s1, dict):
        parts: list[str] = []
        for key in (
            "original_text",
            "sentence1",
            "sentence2",
            "prompt_text",
            "full_prompt",
        ):
            val = s1.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        if parts:
            return "\n\n".join(parts)
    return (record.get("topic") or "").strip()


def workflow_state_from_json(
    content: str, *, raw_input: str | None = None
) -> WorkflowState:
    """从数据库记录还原 WorkflowState。"""
    data = json.loads(content)
    question = (raw_input or data.get("raw_input") or data.get("question") or "").strip()
    state = WorkflowState(question=question)
    state.errors = list(data.get("errors") or [])
    if data.get("stage1_summary") is not None or data.get("stage1_json") is not None:
        state.stage1 = Stage1Result(
            raw="",
            structured_json=data.get("stage1_json") or {},
            human_summary=data.get("stage1_summary") or "",
        )
    if data.get("stage2"):
        state.stage2 = Stage2Result(raw=data["stage2"])
    if data.get("stage3"):
        state.stage3 = Stage3Result(raw=data["stage3"])
    if data.get("stage4"):
        state.stage4 = Stage4Result(raw=data["stage4"])
    return state
