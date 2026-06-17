"""历史记录保存与载入（Streamlit session）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

from db import get_record_by_id, upsert_record
from services.workflow_origin import sync_workflow_origin_from_record
from services.workflow_progress import get_next_stage, resume_label, stage_has_content
from services.workflow_storage import (
    workflow_content_length,
    workflow_state_from_json,
    workflow_state_to_json,
    workflow_stages_mask,
    resolve_raw_input,
)
from utils.config import PROVIDER_OPTIONS
from workflow import WorkflowState


def auto_save_history(
    state: WorkflowState,
    *,
    provider: str | None = None,
    model: str | None = None,
    raw_input: str | None = None,
    notify: bool = True,
    notify_updates: bool = False,
    usage: dict[str, int] | None = None,
) -> int | None:
    """
    写入历史：同题同模型合并为一条；换模型则另存一条。
    每完成一个 Stage 即可调用；后续续跑会更新同一条记录。
    返回 record_id；内容未变时返回 None。
    """
    if not state.stage1:
        return None
    try:
        raw = (
            raw_input
            or state.question
            or st.session_state.get("last_question")
            or st.session_state.get("question")
            or ""
        ).strip()
        if raw:
            state.question = raw
        actual_provider = provider or st.session_state.provider
        actual_model = model or st.session_state.model
        content = workflow_state_to_json(
            state,
            provider=actual_provider,
            model=actual_model,
            raw_input=raw,
            student_level=st.session_state.get("student_level", "中等"),
        )
        # Include usage data in fingerprint to ensure token data is saved
        usage_str = json.dumps(usage or {}, sort_keys=True)
        fingerprint = hashlib.sha256((content + usage_str).encode("utf-8")).hexdigest()
        if st.session_state.get("_last_save_fingerprint") == fingerprint:
            return None
        record_id, is_new = upsert_record(
            raw or state.question,
            actual_model,
            content,
            raw_input=raw,
            word_count=workflow_content_length(state),
            stages_mask=workflow_stages_mask(state),
            usage=usage,
        )
        st.session_state.current_history_record_id = int(record_id)
        st.session_state._last_save_fingerprint = fingerprint
        if notify:
            if is_new:
                st.toast(
                    f"已保存到历史（#{record_id}，模型：{actual_model}）",
                    icon="💾",
                )
            elif notify_updates:
                st.toast(
                    f"已更新历史（#{record_id}，同题同模型已合并）",
                    icon="💾",
                )
        return record_id
    except Exception as e:
        if notify:
            st.toast(f"历史保存失败：{e}", icon="⚠️")
        return None


def load_history_into_session(record_id: int) -> tuple[bool, str]:
    """从历史记录载入完整题目与 workflow，切换到新建模式以便续跑。"""
    record = get_record_by_id(record_id)
    if not record:
        return False, "记录不存在或已被删除"
    try:
        data = json.loads(record["full_content"])
    except json.JSONDecodeError:
        return False, "记录内容损坏，无法解析"

    raw = resolve_raw_input(record, data)
    if not raw:
        return False, "无法还原原始题目，请检查记录是否完整"

    state = workflow_state_from_json(record["full_content"], raw_input=raw)
    state.question = raw

    st.session_state.question = raw
    st.session_state.workflow_state = state
    st.session_state.last_question = raw
    st.session_state.failed_stage = None
    st.session_state.stopped_stage = None
    st.session_state.run_job = None
    st.session_state.is_running = False
    st.session_state.run_cancelled = False
    st.session_state._last_save_fingerprint = None
    st.session_state._confirm_clear = False
    st.session_state.history_view_id = None
    st.session_state.history_nav_state = None
    st.session_state.app_mode = "新建分析"
    st.session_state.current_history_record_id = int(record_id)

    saved_level = data.get("student_level")
    if saved_level in ("基础", "中等", "进阶"):
        st.session_state.student_level = saved_level
    if state.stage4:
        st.session_state.stage4_student_level = (
            saved_level if saved_level in ("基础", "中等", "进阶")
            else st.session_state.get("student_level", "中等")
        )
    else:
        st.session_state.stage4_student_level = None

    saved_provider = data.get("provider")
    saved_model = (data.get("model") or record.get("model_name") or "").strip()
    if saved_provider in PROVIDER_OPTIONS:
        st.session_state["_pending_provider"] = saved_provider
    if saved_model:
        st.session_state["_pending_model"] = saved_model
    sync_workflow_origin_from_record(data, record, record_id=record_id)

    return True, ""


def allow_history_save(question: str, model: str) -> None:
    """
    在启动运行前调用，标记当前 question+model 组合允许保存历史。
    设置 session_state._history_save_allowed 标志，供 auto_save_history 检查。
    """
    st.session_state._history_save_allowed = True
    st.session_state._history_save_question = question
    st.session_state._history_save_model = model


def history_resume_hint(state: WorkflowState) -> str:
    nxt = get_next_stage(state)
    if nxt is None:
        return "四阶段已全部完成，可在新建分析页查看、导出或清空后重跑。"
    done = sum(1 for s in range(1, 5) if stage_has_content(state, s))
    return (
        f"已载入到新建分析页（{done}/4），请点击「{resume_label(nxt)}」续跑。"
    )
