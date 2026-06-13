"""记录 workflow 生成时使用的 LLM，用于检测换模型后是否应重跑。"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from utils.config import PROVIDER_OPTIONS, resolve_model_for_provider


def resolved_llm(provider: str, model: str) -> tuple[str, str]:
    p = (provider or "").strip()
    m = resolve_model_for_provider(p, model or "")
    return p, m


def llm_selection_mismatch(
    source_provider: str | None,
    source_model: str | None,
    current_provider: str,
    current_model: str,
) -> bool:
    """当前侧边栏 LLM 与生成 workflow 时使用的 LLM 是否不一致。"""
    if not source_provider or not source_model:
        return False
    cp, cm = resolved_llm(current_provider, current_model)
    return source_provider != cp or source_model != cm


def job_llm_settings_changed(
    job: dict[str, Any],
    *,
    current_provider: str,
    current_model: str,
) -> bool:
    """run_job 锁定的 LLM 是否与当前侧边栏选择不一致（含模型 ID 规范化）。"""
    cp, cm = resolved_llm(current_provider, current_model)
    return cp != job.get("locked_provider") or cm != job.get("locked_model")


def origin_fields_from_record(
    data: dict[str, Any],
    record: dict[str, Any] | None = None,
) -> tuple[str | None, str | None]:
    """从历史 JSON 与记录行提取 (provider, resolved_model)。"""
    provider = data.get("provider")
    rec = record or {}
    model = (data.get("model") or rec.get("model_name") or rec.get("model") or "").strip()
    if provider in PROVIDER_OPTIONS and model:
        _, resolved = resolved_llm(provider, model)
        return provider, resolved
    return None, None


def set_workflow_origin(provider: str, model: str) -> None:
    p, m = resolved_llm(provider, model)
    st.session_state.workflow_source_provider = p
    st.session_state.workflow_source_model = m


def set_workflow_origin_from_job(job: dict[str, Any]) -> None:
    set_workflow_origin(
        str(job.get("locked_provider") or ""),
        str(job.get("locked_model") or ""),
    )


def sync_workflow_origin_from_record(
    data: dict[str, Any],
    record: dict[str, Any],
    *,
    record_id: int | None = None,
) -> bool:
    """将历史记录中的 provider/model 写入 session，便于换模型检测。"""
    provider, model = origin_fields_from_record(data, record)
    if not provider or not model:
        return False
    set_workflow_origin(provider, model)
    if record_id is not None:
        st.session_state.current_history_record_id = int(record_id)
    return True


def clear_workflow_origin() -> None:
    st.session_state.workflow_source_provider = None
    st.session_state.workflow_source_model = None


def session_llm_mismatch() -> bool:
    ensure_workflow_origin_from_history()
    return llm_selection_mismatch(
        st.session_state.get("workflow_source_provider"),
        st.session_state.get("workflow_source_model"),
        st.session_state.provider,
        st.session_state.model,
    )


def ensure_workflow_origin_from_history() -> None:
    """旧会话无来源记录时，从当前历史记录还原生成时使用的模型。"""
    if st.session_state.get("workflow_source_provider") and st.session_state.get(
        "workflow_source_model"
    ):
        return
    state = st.session_state.get("workflow_state")
    if not state or not getattr(state, "stage1", None):
        return
    record_id = st.session_state.get("current_history_record_id")
    if not record_id:
        return
    from db import get_record_by_id

    record = get_record_by_id(record_id)
    if not record:
        return
    try:
        data = json.loads(record.get("full_content") or "{}")
    except json.JSONDecodeError:
        return
    provider = data.get("provider")
    model = (data.get("model") or record.get("model_name") or record.get("model") or "").strip()
    if provider in PROVIDER_OPTIONS and model:
        set_workflow_origin(provider, model)
