"""运行断点：离开页面后恢复 guest_id、workflow 与历史（无 Streamlit UI）。"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from db import (
    delete_run_checkpoint,
    get_run_checkpoint,
    save_run_checkpoint,
    upsert_record,
)
from services.workflow_storage import (
    workflow_content_length,
    workflow_state_from_json,
    workflow_state_to_json,
    workflow_stages_mask,
)
from utils.question_input import format_image_question_for_history
from workflow import WorkflowState

logger = logging.getLogger("app.run_recovery")

_CHECKPOINT_STREAM_INTERVAL = 5.0
_STALE_RUNNING_SECONDS = 300.0


def apply_stage_result_to_state(
    state: WorkflowState,
    stage_num: int,
    result: Any,
    job: dict[str, Any] | None = None,
) -> None:
    """与 run_manager._apply_stage_result 一致，但不依赖 session_state。"""
    from utils.parsers import stage1_summary_incomplete

    if stage_num == 1:
        state.stage1 = result
        if job and job.get("question_image") and state.stage1:
            state.question = format_image_question_for_history(
                state.stage1.structured_json
            )
            job["question"] = state.question
        msg = stage1_summary_incomplete(getattr(result, "human_summary", "") or "")
        if msg and msg not in state.errors:
            state.errors.append(msg)
    elif stage_num == 2:
        state.stage2 = result
    elif stage_num == 3:
        state.stage3 = result
    elif stage_num == 4:
        state.stage4 = result


def _checkpoint_payload(
    job: dict[str, Any],
    state: WorkflowState,
    *,
    run_status: str,
) -> dict[str, Any]:
    raw = (job.get("question") or state.question or "").strip()
    usage = job.get("usage_total")
    usage_dict = None
    if usage and hasattr(usage, "prompt_tokens"):
        usage_dict = {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cached_tokens": usage.cached_tokens,
        }
    return {
        "question": raw,
        "locked_provider": job.get("locked_provider") or "",
        "locked_model": job.get("locked_model") or "",
        "mode": job.get("mode") or "full",
        "stages": list(job.get("stages") or []),
        "stage_index": int(job.get("stage_index") or 0),
        "run_status": run_status,
        "stream_stage": int(job.get("stream_stage") or 0),
        "stream_total": int(job.get("stream_total") or 0),
        "stream_preview": str(job.get("stream_preview") or ""),
        "student_level": job.get("student_level") or "中等",
        "workflow_content": workflow_state_to_json(
            state,
            provider=job.get("locked_provider") or "",
            model=job.get("locked_model") or "",
            raw_input=raw,
            student_level=job.get("student_level") or "中等",
        ),
        "usage": usage_dict,
        "has_question_image": bool(job.get("question_image")),
    }


def persist_run_checkpoint(
    owner_id: str,
    job: dict[str, Any],
    state: WorkflowState,
    *,
    run_status: str = "running",
) -> None:
    if not owner_id:
        return
    try:
        save_run_checkpoint(
            owner_id,
            json.dumps(
                _checkpoint_payload(job, state, run_status=run_status),
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.exception("保存运行断点失败 owner=%s", owner_id[:8])


def maybe_persist_stream_checkpoint(
    owner_id: str,
    job: dict[str, Any],
    state: WorkflowState,
) -> None:
    """流式输出时节流写入，便于离开后看到「已收到 N 字」。"""
    if not owner_id:
        return
    now = time.time()
    last = float(job.get("_checkpoint_stream_ts") or 0)
    if now - last < _CHECKPOINT_STREAM_INTERVAL:
        return
    job["_checkpoint_stream_ts"] = now
    persist_run_checkpoint(owner_id, job, state, run_status="running")


def persist_stage_completion_background(
    owner_id: str,
    job: dict[str, Any],
    state: WorkflowState,
    stage_num: int,
    result: Any,
) -> None:
    """API 线程完成某 Stage 后立即落库（不依赖页面是否仍连接）。"""
    if not owner_id:
        return
    try:
        apply_stage_result_to_state(state, stage_num, result, job)
        raw = (job.get("question") or state.question or "").strip()
        if raw:
            state.question = raw
        provider = job.get("locked_provider") or ""
        model = job.get("locked_model") or ""
        usage = job.get("usage_total")
        usage_dict = None
        if usage and hasattr(usage, "prompt_tokens"):
            usage_dict = {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "cached_tokens": usage.cached_tokens,
            }
        content = workflow_state_to_json(
            state,
            provider=provider,
            model=model,
            raw_input=raw,
            student_level=job.get("student_level") or "中等",
        )
        record_id, _ = upsert_record(
            raw or state.question,
            model,
            content,
            raw_input=raw,
            word_count=workflow_content_length(state),
            stages_mask=workflow_stages_mask(state),
            usage=usage_dict,
            owner_id=owner_id,
        )
        if record_id and job.get("question_image"):
            from db import save_history_question_image

            save_history_question_image(
                int(record_id),
                job["question_image"],
                owner_id=owner_id,
            )
        idx = int(job.get("stage_index") or 0)
        stages = job.get("stages") or []
        more = idx + 1 < len(stages)
        persist_run_checkpoint(
            owner_id,
            job,
            state,
            run_status="running" if more else "idle",
        )
        logger.info(
            "后台已持久化 Stage %d（record #%s）owner=%s",
            stage_num,
            record_id,
            owner_id[:8],
        )
    except Exception:
        logger.exception("后台持久化 Stage %d 失败", stage_num)


def clear_run_checkpoint_for_owner(owner_id: str) -> None:
    if not owner_id:
        return
    try:
        delete_run_checkpoint(owner_id)
    except Exception:
        logger.exception("清除运行断点失败")


def try_recover_session_from_checkpoint(owner_id: str) -> str | None:
    """
    新会话载入时恢复 workflow。返回提示文案；无可恢复内容时返回 None。
    """
    import streamlit as st

    if st.session_state.get("run_job") or st.session_state.get("_checkpoint_recovered"):
        return None
    if st.session_state.get("workflow_state") and st.session_state.workflow_state.stage1:
        return None

    row = get_run_checkpoint(owner_id)
    if not row:
        return None

    try:
        data = json.loads(row.get("payload_json") or "{}")
    except json.JSONDecodeError:
        delete_run_checkpoint(owner_id)
        return None

    workflow_content = data.get("workflow_content") or ""
    if not workflow_content:
        delete_run_checkpoint(owner_id)
        return None

    raw = (data.get("question") or "").strip()
    state = workflow_state_from_json(workflow_content, raw_input=raw)
    if not state.stage1:
        run_status = data.get("run_status") or ""
        preview = (data.get("stream_preview") or "").strip()
        if run_status == "running" and preview:
            if raw:
                st.session_state.question = raw
                st.session_state.last_question = raw
                st.session_state["question_editor"] = raw
            st.session_state._recovered_stream_preview = preview
            st.session_state._recovered_stream_total = int(data.get("stream_total") or 0)
            st.session_state._checkpoint_recovered = True
            return (
                "检测到上次运行中断，已收到部分输出但未完成解析。"
                f"（约 {st.session_state._recovered_stream_total} 字）请重新运行 Stage 1。"
            )
        delete_run_checkpoint(owner_id)
        return None

    st.session_state.workflow_state = state
    st.session_state.last_question = raw or state.question
    st.session_state.question = raw or state.question
    if data.get("has_question_image"):
        st.session_state.question_image = None
    st.session_state.current_history_record_id = None
    st.session_state._checkpoint_recovered = True
    st.session_state.is_running = False
    st.session_state.run_job = None

    from services.workflow_progress import stage_has_content

    run_status = data.get("run_status") or "idle"
    updated_at = (row.get("updated_at") or "").strip()
    stale = False
    if run_status == "running" and updated_at:
        from utils.datetime_util import utc_now_str

        try:
            from datetime import datetime, timezone

            fmt = "%Y-%m-%d %H:%M:%S"
            t0 = datetime.strptime(updated_at, fmt).replace(tzinfo=timezone.utc)
            t1 = datetime.strptime(utc_now_str(), fmt).replace(tzinfo=timezone.utc)
            stale = (t1 - t0).total_seconds() > _STALE_RUNNING_SECONDS
        except ValueError:
            stale = False

    done = sum(1 for s in range(1, 5) if stage_has_content(state, s))

    if stale and done < 4:
        return (
            f"已恢复上次离开时的备课进度（已完成 {done}/4）。"
            "上次运行可能因页面断开而中断，可从对应 Stage 续跑。"
        )
    return f"已恢复上次离开时的备课进度（已完成 {done}/4），可在历史或本页继续。"
