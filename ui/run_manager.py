"""运行管理：RunUI、线程调度、advance_run_job、try_start_run_job。"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

import streamlit as st

logger = logging.getLogger("app.run_manager")

# ── 轮询间隔配置 ──
_POLL_INTERVAL_FAST = 0.5    # 状态转换后快速进入下一状态（秒）
_POLL_INTERVAL_SLOW = 1.0    # API 调用中轮询间隔（秒），减少闪烁

from llm.client import LLMClient, RunCancelled
from llm.usage import ChatUsage
from utils.config import (
    build_settings,
    recommended_image_models_text,
    resolve_model_for_provider,
    supports_question_image_upload,
)
from services.run_recovery import (
    clear_run_checkpoint_for_owner,
    maybe_persist_stream_checkpoint,
    persist_run_checkpoint,
    persist_stage_completion_background,
)
from utils.question_input import question_input_conflict
from ui.run_cache import (
    merge_job_usage,
    save_stage_cache,
    try_load_cached_stage,
)
from utils.status_log import (
    PARSING_RESPONSE,
    PIPELINE_FULL,
    PIPELINE_RESUME,
    PIPELINE_SKIP,
    pipeline_done,
    stage_call_api,
    stage_complete,
)
from utils.parsers import format_image_question_for_history, stage1_summary_incomplete
from workflow import GaokaoWritingWorkflow, WorkflowState

from services.workflow_origin import (
    ensure_workflow_origin_from_history,
    job_llm_settings_changed,
    session_llm_mismatch,
    set_workflow_origin_from_job,
)
from services.workflow_progress import get_next_stage, stage_has_content
from ui.history import auto_save_history, allow_history_save
from ui.sidebar import api_key_configured, clear_run_job
from ui.stage_display import (
    render_one_stage,
    render_stage_in_progress,
    render_stage_placeholder,
    sync_slots_from_state,
)


def _require_stage1_json(state: WorkflowState) -> dict[str, Any]:
    if state.stage1 is None:
        raise ValueError("Stage 1 未完成，无法运行后续阶段")
    return state.stage1.structured_json


def _require_stage2_raw(state: WorkflowState) -> str:
    if state.stage2 is None:
        raise ValueError("Stage 2 未完成，无法运行 Stage 4")
    return state.stage2.raw


def _require_stage3_raw(state: WorkflowState) -> str:
    if state.stage3 is None:
        raise ValueError("Stage 3 未完成，无法运行 Stage 4")
    return state.stage3.raw


# ── Workflow 工厂 ──


def get_workflow() -> GaokaoWritingWorkflow:
    settings = build_settings(
        st.session_state.provider,
        api_key=st.session_state.api_key,
        model=st.session_state.model,
    )
    return GaokaoWritingWorkflow(client=LLMClient(settings))


def get_workflow_from_job(job: dict[str, Any]) -> GaokaoWritingWorkflow:
    settings = build_settings(
        job["locked_provider"],
        api_key=job.get("api_key") or st.session_state.api_key,
        model=job["locked_model"],
    )
    return GaokaoWritingWorkflow(client=LLMClient(settings))


# ── RunUI ──


class RunUI:
    """运行过程 UI：步骤列表（不刷屏）+ 单行字数 + 实时预览。"""

    def __init__(
        self,
        steps: list[str] | None = None,
        *,
        job: dict[str, Any] | None = None,
    ) -> None:
        self._job = job
        progress_val = int((job or {}).get("ui_progress") or 0)
        progress_text = str((job or {}).get("ui_progress_text") or "等待开始…")
        self.progress = st.progress(progress_val, text=progress_text)
        self.status = st.status("运行状态", expanded=True)
        self._steps: list[str] = list(steps) if steps else []
        self._step_area = self.status.empty()
        self._live_line = st.empty()
        self._preview_title = st.empty()
        self._preview_body = st.empty()
        self._last_stream_total = 0
        if self._steps:
            self._refresh_steps()

    def log(self, message: str) -> None:
        """追加一步（相同内容不重复）。"""
        if message and message not in self._steps:
            self._steps.append(message)
            self._refresh_steps()

    def _refresh_steps(self) -> None:
        if self._steps:
            self._step_area.markdown("\n".join(f"- {s}" for s in self._steps))
        else:
            self._step_area.markdown("_等待开始…_")

    def update_stream(self, stage: int, total: int, full_text: str) -> None:
        """原地刷新字数；预览用纯文本减轻卡顿。"""
        if total == self._last_stream_total and total >= 3000:
            hint = "（字数暂未增加，模型可能在收尾，请稍候…）"
        else:
            hint = ""
            self._last_stream_total = total
        self._live_line.markdown(
            f"**Stage {stage}** 生成中 · 已收到 **{total}** 字{hint}"
        )
        if total > 0:
            self.set_progress(
                min(8 + stage * 18 + min(total // 80, 12), 75),
                text=f"Stage {stage} · 生成中（{total} 字）…",
            )
        if total < 800:
            return
        self._preview_title.markdown("**实时生成内容**（纯文本预览）")
        show = full_text[-2500:] if len(full_text) > 2500 else full_text
        if len(full_text) > 2500:
            show = "…（仅显示最后 2500 字）\n" + show
        self._preview_body.text(show)

    def show_connecting_wait(self, stage: int, model: str, elapsed: int) -> None:
        """API 已发出、尚未收到首字时刷新等待提示（fragment 每轮重建 UI）。"""
        self._live_line.markdown(
            f"**Stage {stage}** 等待模型响应 · 已 **{elapsed}** 秒"
            f"（模型：**{model}**）"
        )
        self.set_progress(
            min(8 + stage * 18, 28),
            text=f"Stage {stage} · 等待响应（{elapsed}s）…",
        )

    def clear_stream_preview(self) -> None:
        self._live_line.empty()
        self._preview_title.empty()
        self._preview_body.empty()

    def set_progress(self, value: int, text: str) -> None:
        value = min(max(value, 0), 100)
        self.progress.progress(value, text=text)
        if self._job is not None:
            self._job["ui_progress"] = value
            self._job["ui_progress_text"] = text

    def sync_stream_from_job(self, job: dict[str, Any]) -> None:
        stage, total, preview = _read_job_stream(job)
        if total <= 0:
            started = float(job.get("_api_started_at") or time.time())
            elapsed = max(0, int(time.time() - started))
            model = job.get("locked_model", st.session_state.get("model", ""))
            self.show_connecting_wait(stage, model, elapsed)
            return
        self.update_stream(stage, total, preview)

    def persist_logs(self, job: dict[str, Any]) -> None:
        job["logs"] = list(self._steps)


# ── 内部工具 ──


def _sync_cancel_from_settings(job: dict[str, Any]) -> None:
    if job_llm_settings_changed(
        job,
        current_provider=st.session_state.provider,
        current_model=st.session_state.model,
    ):
        job["cancel_event"].set()
        st.session_state.run_cancelled = True


def _running_stages_for_job(job: dict[str, Any], state: WorkflowState) -> set[int]:
    """API 线程运行中时，返回正在生成的 Stage 编号集合。"""
    if job.get("phase") != "api":
        return set()
    thread = job.get("thread")
    if thread is None or not thread.is_alive():
        return set()
    idx = job["stage_index"]
    stages = job.get("stages") or []
    if idx < len(stages):
        return {stages[idx]}
    return set()


def _stage_slot_signature(
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> tuple[int, ...]:
    return tuple(id(s) for s in slots)


def _resolve_paint_mode(
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
    job: dict[str, Any] | None,
    requested: str,
) -> str:
    """整页 rerun 会重建 st.empty()；此时必须 full 重绘已完成阶段，不能 incremental 跳过。"""
    if requested != "incremental" or job is None:
        return requested
    sig = _stage_slot_signature(slots)
    prev = job.get("_stage_slot_sig")
    job["_stage_slot_sig"] = sig
    if prev is not None and prev != sig:
        return "full"
    return "incremental"


def _slot_paint_plan(
    state: WorkflowState,
    running: set[int],
    *,
    incremental: bool,
) -> list[str | None]:
    """各 Stage 占位更新计划：content / in_progress / placeholder / None(跳过)。"""
    plan: list[str | None] = []
    for n in range(1, 5):
        if n in running:
            plan.append("in_progress")
        elif stage_has_content(state, n):
            plan.append("content")
        elif incremental:
            plan.append(None)
        else:
            plan.append("placeholder")
    return plan


def _sync_visible_stage_slots(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
    job: dict[str, Any] | None,
    *,
    paint_mode: str = "full",
) -> None:
    """恢复 Stage 占位。

    每次整页 rerun 会重建 st.empty()，已完成阶段必须重绘。
    incremental 时仍重绘已完成阶段（否则 fragment 轮询时 st.empty 内容会被清空）。
    """
    running = _running_stages_for_job(job, state) if job else set()
    if not any(stage_has_content(state, n) for n in range(1, 5)) and not running:
        return

    incremental = paint_mode == "incremental"
    actions = _slot_paint_plan(state, running, incremental=incremental)

    for n, slot in enumerate(slots, start=1):
        action = actions[n - 1]
        if action == "content":
            render_one_stage(slot, state, n)
        elif action == "in_progress":
            render_stage_in_progress(slot, n)
        elif action == "placeholder":
            render_stage_placeholder(slot, n)


def _flush_stage(
    state: WorkflowState,
    stage_num: int,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
    ui: RunUI,
    job: dict[str, Any] | None = None,
) -> None:
    """保存状态并刷新各 Stage 占位（含已完成阶段）。"""
    st.session_state.workflow_state = state
    ui.clear_stream_preview()
    ui.log(f"正在显示 Stage {stage_num} 结果…")
    ui.set_progress(min(82 + stage_num * 4, 99), text=f"Stage {stage_num} · 显示结果…")
    _sync_visible_stage_slots(state, slots, job, paint_mode="full")
    render_one_stage(slots[stage_num - 1], state, stage_num)
    ui.log(stage_complete(stage_num))


def _ensure_job_lock(job: dict[str, Any]) -> threading.Lock:
    lock = job.get("job_lock")
    if lock is None:
        lock = threading.Lock()
        job["job_lock"] = lock
    return lock


def _job_append_log(
    job: dict[str, Any],
    message: str,
    cancel_event: threading.Event | None = None,
) -> None:
    if cancel_event and cancel_event.is_set():
        return
    with _ensure_job_lock(job):
        logs: list[str] = job.setdefault("logs", [])
        if message and message not in logs:
            logs.append(message)


def _job_on_progress(
    job: dict[str, Any], stage: int, cancel_event: threading.Event
):
    def _cb(msg: str) -> None:
        if cancel_event.is_set():
            return
        _job_append_log(job, msg, cancel_event)
        with _ensure_job_lock(job):
            job["stream_stage"] = stage

    return _cb


def _job_on_stream(
    job: dict[str, Any],
    stage: int,
    cancel_event: threading.Event,
    state: WorkflowState,
):
    def _cb(_d: str, total: int, full: str) -> None:
        if cancel_event.is_set():
            return
        preview = full[-2500:] if len(full) > 2500 else full
        with _ensure_job_lock(job):
            job["stream_stage"] = stage
            job["stream_total"] = total
            job["stream_preview"] = preview
        maybe_persist_stream_checkpoint(job.get("owner_id") or "", job, state)

    return _cb


def _read_job_stream(job: dict[str, Any]) -> tuple[int, int, str]:
    """主线程读取流式进度（与 worker 写入互斥）。"""
    with _ensure_job_lock(job):
        return (
            int(job.get("stream_stage") or 1),
            int(job.get("stream_total") or 0),
            str(job.get("stream_preview") or ""),
        )


def _execute_stage_api(
    job: dict[str, Any],
    stage_num: int,
    state: WorkflowState,
    cancel_event: threading.Event,
) -> Any:
    if cancel_event.is_set():
        raise RunCancelled("已切换模型或提供商，当前请求已停止。")

    wf = get_workflow_from_job(job)
    question = job["question"]
    should_cancel = cancel_event.is_set

    if stage_num == 1:
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        result = wf.run_stage1(
            question,
            question_image=job.get("question_image"),
            on_progress=_job_on_progress(job, 1, cancel_event),
            on_stream=_job_on_stream(job, 1, cancel_event, state),
            should_cancel=should_cancel,
        )
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        merge_job_usage(job, wf.last_usage)
        return result
    if stage_num == 2:
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        result = wf.run_stage2(
            question,
            _require_stage1_json(state),
            on_progress=_job_on_progress(job, 2, cancel_event),
            on_stream=_job_on_stream(job, 2, cancel_event, state),
            should_cancel=should_cancel,
        )
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        merge_job_usage(job, wf.last_usage)
        return result
    if stage_num == 3:
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        result = wf.run_stage3(
            question,
            _require_stage1_json(state),
            on_progress=_job_on_progress(job, 3, cancel_event),
            on_stream=_job_on_stream(job, 3, cancel_event, state),
            should_cancel=should_cancel,
        )
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        merge_job_usage(job, wf.last_usage)
        return result
    if stage_num == 4:
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        result = wf.run_stage4(
            _require_stage1_json(state),
            _require_stage2_raw(state),
            _require_stage3_raw(state),
            student_level=job.get("student_level", "中等"),
            on_progress=_job_on_progress(job, 4, cancel_event),
            on_stream=_job_on_stream(job, 4, cancel_event, state),
            should_cancel=should_cancel,
        )
        if cancel_event.is_set():
            raise RunCancelled("已切换模型或提供商，当前请求已停止。")
        merge_job_usage(job, wf.last_usage)
        return result
    raise ValueError(f"invalid stage: {stage_num}")


def _stage_timeout_seconds() -> float:
    """单 Stage API 线程最长等待（秒）；与 API_READ_TIMEOUT_SECONDS 建议一致或略小。"""
    return float(os.getenv("STAGE_TIMEOUT_SECONDS", "300"))


_THREAD_JOIN_AFTER_CANCEL_SECONDS = 2.0


def _stop_api_thread(t: threading.Thread, cancel_event: threading.Event) -> None:
    """通知 API 线程停止并等待收尾。"""
    cancel_event.set()
    t.join(timeout=_THREAD_JOIN_AFTER_CANCEL_SECONDS)


def _start_api_thread(job: dict[str, Any], stage_num: int, state: WorkflowState) -> None:
    cancel_event: threading.Event = job["cancel_event"]
    _ensure_job_lock(job)
    model = job.get("locked_model", "unknown")

    def worker() -> None:
        lock = _ensure_job_lock(job)
        try:
            timeout_msg = (
                f"Stage {stage_num} 生成超时（超过 {int(_stage_timeout_seconds())} 秒），"
                "请换更快模型重试，或在 Secrets / .env 增大 STAGE_TIMEOUT_SECONDS。"
            )
            cancelled_msg = "已切换模型或提供商，当前请求已停止。"
            start_time = time.time()

            for attempt in range(2):
                if cancel_event.is_set():
                    with lock:
                        job["thread_error"] = ("cancelled", cancelled_msg)
                    return

                result_holder: list[Any] = []
                error_holder: list[tuple[str, str]] = []

                def _run_once() -> None:
                    try:
                        logger.info("Stage %d 开始调用 API，模型: %s", stage_num, model)
                        result_holder.append(
                            _execute_stage_api(job, stage_num, state, cancel_event)
                        )
                    except RunCancelled:
                        logger.info("Stage %d 用户取消", stage_num)
                        error_holder.append(("cancelled", cancelled_msg))
                    except Exception as e:
                        logger.exception("Stage %d 失败", stage_num)
                        error_holder.append(("error", str(e)))

                t = threading.Thread(target=_run_once, daemon=True)
                t.start()
                t.join(timeout=_stage_timeout_seconds())

                if not t.is_alive():
                    with lock:
                        if result_holder:
                            elapsed = time.time() - start_time
                            logger.info(
                                "Stage %d 完成，耗时 %.1f 秒", stage_num, elapsed
                            )
                            job["thread_result"] = result_holder[0]
                            persist_stage_completion_background(
                                job.get("owner_id") or "",
                                job,
                                state,
                                stage_num,
                                result_holder[0],
                            )
                            return
                        if error_holder:
                            job["thread_error"] = error_holder[0]
                            return

                cancelled_during_wait = cancel_event.is_set()
                logger.warning(
                    "Stage %d 第 %d 次调用超时（%d 秒），正在停止旧线程…",
                    stage_num,
                    attempt + 1,
                    int(_stage_timeout_seconds()),
                )
                _stop_api_thread(t, cancel_event)

                if cancelled_during_wait:
                    with lock:
                        if error_holder:
                            job["thread_error"] = error_holder[0]
                        else:
                            job["thread_error"] = ("cancelled", cancelled_msg)
                    return

                if attempt == 0:
                    cancel_event.clear()
                    continue

                with lock:
                    job["thread_error"] = ("timeout", timeout_msg)
                return
        finally:
            with lock:
                job["thread_done"] = True

    with _ensure_job_lock(job):
        job["thread"] = threading.Thread(target=worker, daemon=True)
        job["thread_done"] = False
        job["thread_error"] = None
        job["thread_result"] = None
        job["stream_total"] = 0
        job["stream_preview"] = ""
        job["stream_stage"] = stage_num
        job["_api_dispatching"] = False
        job["thread"].start()


def _begin_cached_or_api(
    job: dict[str, Any],
    state: WorkflowState,
    ui: RunUI,
    stage_num: int,
) -> bool:
    """
    若命中缓存则写入 state 并进入 flush；若已启动线程返回 True；否则返回 False 由调用方启动线程。
    """
    cached = try_load_cached_stage(job, stage_num, state)
    if cached is None:
        return False
    _apply_stage_result(state, stage_num, cached)
    st.session_state.workflow_state = state
    job["phase"] = "flush"
    job["thread"] = None
    ui.log(f"已从缓存加载 Stage {stage_num}（未调用 API）")
    ui.persist_logs(job)
    try:
        st.toast(f"已从缓存加载 Stage {stage_num}", icon="ℹ️")
    except Exception:
        pass
    return True


def _prepare_stage_api_logs(
    ui: RunUI, stage_num: int, job: dict[str, Any]
) -> None:
    job["_api_started_at"] = time.time()
    ui.log(stage_call_api(stage_num))
    ui.set_progress(8 + stage_num * 18, text=f"Stage {stage_num} · 调用 API…")
    model = job.get("locked_model", st.session_state.model)
    ui.show_connecting_wait(stage_num, model, 0)


def _apply_stage_result(state: WorkflowState, stage_num: int, result: Any) -> None:
    if stage_num == 1:
        state.stage1 = result
        job = st.session_state.get("run_job")
        if job and job.get("question_image") and state.stage1:
            state.question = format_image_question_for_history(
                state.stage1.structured_json
            )
            job["question"] = state.question
            st.session_state.question = state.question
            st.session_state.last_question = state.question
        msg = stage1_summary_incomplete(getattr(result, "human_summary", "") or "")
        if msg and msg not in state.errors:
            state.errors.append(msg)
    elif stage_num == 2:
        state.stage2 = result
    elif stage_num == 3:
        state.stage3 = result
    elif stage_num == 4:
        state.stage4 = result
        job = st.session_state.get("run_job")
        level = (job or {}).get("student_level") or st.session_state.get(
            "student_level", "中等"
        )
        st.session_state.stage4_student_level = level


def _persist_history_from_job(
    job: dict[str, Any] | None,
    state: WorkflowState,
    *,
    notify: bool = True,
    notify_updates: bool = False,
) -> None:
    """将当前 workflow 写入历史（至少需已完成 Stage 1）。"""
    if not job or not state.stage1:
        return
    usage_total = job.get("usage_total")
    usage_dict = None
    if usage_total and hasattr(usage_total, "prompt_tokens"):
        usage_dict = {
            "prompt_tokens": usage_total.prompt_tokens,
            "completion_tokens": usage_total.completion_tokens,
            "cached_tokens": usage_total.cached_tokens,
        }
    auto_save_history(
        state,
        provider=job.get("locked_provider"),
        model=job.get("locked_model"),
        raw_input=job.get("question"),
        notify=notify,
        notify_updates=notify_updates,
        usage=usage_dict,
        question_image=job.get("question_image"),
    )


def _pipeline_stages_for_mode(mode: str, *, skip_completed: bool = False, state: WorkflowState | None = None) -> list[int]:
    """返回 mode 对应的 Stage 列表。"""
    ALL_STAGES = [1, 2, 3, 4]
    if mode == "full":
        stages = list(ALL_STAGES)
    elif mode == "stage1":
        stages = [1]
    elif mode == "stage2":
        stages = [2]
    elif mode == "stage3":
        stages = [3]
    elif mode == "stage4":
        stages = [4]
    elif mode == "resume":
        if state:
            next_stage = get_next_stage(state)
            if next_stage is not None:
                stages = list(range(next_stage, 5))
            else:
                stages = []
        else:
            stages = list(ALL_STAGES)
    else:
        return []

    if skip_completed and state and mode != "resume":
        stages = [s for s in stages if not stage_has_content(state, s)]

    return stages


# ── 公开 API ──


def try_start_run_job(mode: str, question: str) -> bool:
    """尝试启动运行任务；返回 True 表示成功启动。"""
    if st.session_state.is_running:
        st.warning("正在分析中；若要换模型，请先在侧边栏切换（将自动停止）或点「停止当前运行」。")
        return False
    if not api_key_configured():
        st.error("请先在侧边栏配置 API Key")
        return False

    image = st.session_state.get("question_image")
    if question_input_conflict(question, image):
        st.error("请只保留文字或图片其中一种输入方式。")
        return False
    if image and not supports_question_image_upload(
        st.session_state.provider, st.session_state.model
    ):
        st.error(
            "当前模型不支持本地上传识图。"
            f"请改用 {recommended_image_models_text()} 等侧边栏带 👁 的模型。"
        )
        return False

    state: WorkflowState = st.session_state.workflow_state or WorkflowState(
        question=question
    )
    from utils.question_input import resolve_effective_question

    question = resolve_effective_question(
        question,
        image,
        workflow_question=state.question if state.stage1 else None,
        last_question=st.session_state.get("last_question"),
    )
    if image and not (question or "").strip():
        question = "[图片题目]"
    state.question = question

    ensure_workflow_origin_from_history()
    model_changed = session_llm_mismatch() and state.stage1 is not None
    if model_changed:
        if mode == "full":
            state = WorkflowState(question=question)
            st.session_state.workflow_state = state
            stages = [1, 2, 3, 4]
            st.toast("已切换模型，将用新模型重新生成全部阶段", icon="🔄")
        elif mode == "stage1":
            state = WorkflowState(question=question)
            st.session_state.workflow_state = state
            stages = [1]
            st.toast("已切换模型，将用新模型重新生成 Stage 1", icon="🔄")
        else:
            src_model = st.session_state.get("workflow_source_model") or "其他模型"
            st.warning(
                f"当前内容由 **{src_model}** 生成，与侧边栏所选模型不一致。"
                "请点击「完整流程」或先运行 Stage 1，用新模型重新生成。"
            )
            return False
    elif mode == "stage2" and not state.stage1:
        st.error("请先运行 Stage 1")
        return False
    elif mode == "stage3" and not state.stage1:
        st.error("请先运行 Stage 1")
        return False
    elif mode == "stage4" and (not state.stage1 or not state.stage2 or not state.stage3):
        st.error("请先完成 Stage 1、Stage 2 与 Stage 3")
        return False

    if not model_changed:
        skip_completed = mode == "full"
        stages = _pipeline_stages_for_mode(
            mode,
            skip_completed=skip_completed,
            state=state if skip_completed or mode == "resume" else None,
        )
    if not stages:
        st.warning(
            "四阶段已全部完成，无需重新生成。"
            "如需重跑，请点击下方 **清空并重跑完整流程**，或先 **清空结果**。"
        )
        return False

    st.session_state.workflow_state = state
    if state.errors:
        state.errors.clear()
    locked_provider = st.session_state.provider
    locked_model = resolve_model_for_provider(locked_provider, st.session_state.model)
    allow_history_save(question, locked_model)
    from db.identity import ensure_guest_id

    owner_id = ensure_guest_id()
    # 勿写入 st.session_state.model：侧边栏 selectbox(key="model") 已绑定，会触发 StreamlitAPIException
    st.session_state.run_job = {
        "mode": mode,
        "question": question,
        "stages": stages,
        "stage_index": 0,
        "phase": "api",
        "locked_provider": locked_provider,
        "locked_model": locked_model,
        "api_key": st.session_state.api_key,
        "cancel_event": threading.Event(),
        "thread": None,
        "thread_done": False,
        "thread_error": None,
        "thread_result": None,
        "logs": [],
        "stream_stage": stages[0],
        "stream_total": 0,
        "stream_preview": "",
        "usage_total": ChatUsage(),
        "pending_flushes": None,
        "_flush_queue_idx": 0,
        "student_level": st.session_state.get("student_level", "中等"),
        "question_image": image,
        "owner_id": owner_id,
        "skip_llm_cache": model_changed,
    }
    persist_run_checkpoint(owner_id, st.session_state.run_job, state, run_status="running")
    st.session_state.llm_run_usage = None
    if mode == "full":
        if len(stages) < 4:
            st.session_state.run_job["logs"].append(
                PIPELINE_SKIP.format(n=stages[0])
            )
        else:
            st.session_state.run_job["logs"].append(PIPELINE_FULL)
    elif mode == "resume":
        st.session_state.run_job["logs"].append(
            PIPELINE_RESUME.format(n=stages[0])
        )
    st.session_state.run_cancelled = False
    st.session_state.is_running = True
    st.session_state.failed_stage = None
    st.session_state.stopped_stage = None
    logger.info("运行启动 mode=%s stages=%s model=%s", mode, stages, locked_model)
    return True


# ── 任务结束处理 ──


def _finish_job_cancelled(
    ui: RunUI,
    job: dict[str, Any],
    msg: str,
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    stage_num = job["stages"][job["stage_index"]]
    logger.info("用户取消了 Stage %d", stage_num)
    ui.log(f"⏹ {msg}")
    ui.status.update(label="已停止", state="error")
    ui.persist_logs(job)
    st.session_state.workflow_state = state
    st.session_state.last_question = job["question"]
    st.session_state.failed_stage = None
    st.session_state.stopped_stage = stage_num
    set_workflow_origin_from_job(job)
    _persist_history_from_job(job, state, notify=True)
    sync_slots_from_state(state, slots)
    clear_run_job()
    st.warning(msg)


def _finish_job_success(
    ui: RunUI,
    job: dict[str, Any],
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    mode = job["mode"]
    if mode == "full":
        ui.set_progress(100, text="全部完成")
        ui.log(pipeline_done())
        ui.status.update(label="✅ 完整流程已完成", state="complete")
    else:
        stage_num = job["stages"][-1]
        ui.set_progress(100, text=f"Stage {stage_num} 完成")
        ui.status.update(label=f"✅ Stage {stage_num} 完成", state="complete")
    ui.persist_logs(job)
    st.session_state.workflow_state = state
    st.session_state.last_question = job["question"]
    st.session_state.failed_stage = None
    st.session_state.stopped_stage = None
    if state.errors:
        state.errors.clear()
    set_workflow_origin_from_job(job)
    logger.info("运行完成 mode=%s", mode)
    _persist_history_from_job(job, state, notify=False)
    clear_run_checkpoint_for_owner(job.get("owner_id") or "")
    clear_run_job()
    if state.errors:
        for err in state.errors:
            st.warning(err)


# ── 主循环 ──




def advance_run_job(
    question: str,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    """轮询后台 API；允许侧边栏在 rerun 间切换模型并取消。

    策略：API 调用中用 fragment 局部刷新减少闪烁；
    状态转换点（启动/完成/失败/flush）仍用整页 rerun。
    """
    job = st.session_state.run_job
    if not job:
        return

    _sync_cancel_from_settings(job)
    state: WorkflowState = st.session_state.workflow_state or WorkflowState(
        question=question
    )
    state.question = job["question"]
    ui = RunUI(job.get("logs"), job=job)
    stage_num = job["stages"][job["stage_index"]]
    thread = job.get("thread")
    thread_alive = thread is not None and thread.is_alive()
    paint_mode = _resolve_paint_mode(slots, job, "incremental")
    if job["phase"] != "flush":
        if thread_alive or (job["phase"] == "api" and thread is None):
            _sync_visible_stage_slots(state, slots, job, paint_mode=paint_mode)

    if job["phase"] == "api":
        if job.get("thread") is None:
            if job.get("_api_dispatching"):
                dispatch_ts = float(job.get("_api_dispatch_ts") or 0)
                if dispatch_ts and time.time() - dispatch_ts > 8:
                    job["_api_dispatching"] = False
            need_full_rerun = False
            start_api = False
            with _ensure_job_lock(job):
                if job.get("thread") is None:
                    if _begin_cached_or_api(job, state, ui, stage_num):
                        need_full_rerun = True
                    elif not job.get("_api_dispatching"):
                        job["_api_dispatching"] = True
                        job["_api_dispatch_ts"] = time.time()
                        start_api = True
            if need_full_rerun:
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return
            if start_api:
                _prepare_stage_api_logs(ui, stage_num, job)
                ui.persist_logs(job)
                _start_api_thread(job, stage_num, state)
                _sync_visible_stage_slots(state, slots, job, paint_mode=paint_mode)
                return
            if job.get("_api_started_at"):
                ui.sync_stream_from_job(job)
            return

        thread = job["thread"]
        ui.sync_stream_from_job(job)
        ui.persist_logs(job)

        if thread.is_alive():
            if job["cancel_event"].is_set():
                _stop_api_thread(thread, job["cancel_event"])
                _finish_job_cancelled(
                    ui,
                    job,
                    "已切换模型或提供商，当前请求已停止。请用新模型重新点击运行。",
                    state,
                    slots,
                )
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return

            # fragment run_every 轮询：勿整页 rerun，避免 Stage 1 等已完成阶段闪烁
            return

        # ── 线程结束，处理结果 ──
        with _ensure_job_lock(job):
            err = job.get("thread_error")
            thread_result = job.get("thread_result")
        if err:
            if job.get("_error_handled"):
                return
            job["_error_handled"] = True

            kind, msg = err
            failed_stage = stage_num
            if kind == "cancelled":
                _finish_job_cancelled(ui, job, msg, state, slots)
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return
            if kind == "timeout":
                ui.status.update(label=f"Stage {failed_stage} 超时", state="error")
                ui.log(f"⏱️ {msg}")
                state.errors.append(msg)
                ui.persist_logs(job)
                st.session_state.workflow_state = state
                st.session_state.last_question = job["question"]
                st.session_state.failed_stage = failed_stage
                st.session_state.stopped_stage = None
                _persist_history_from_job(job, state, notify=True)
                sync_slots_from_state(state, slots)
                clear_run_job()
                st.warning(msg)
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return
            else:
                ui.status.update(label="执行失败", state="error")
                ui.log(f"❌ {msg}")
                state.errors.append(msg)
                ui.persist_logs(job)
                st.session_state.workflow_state = state
                st.session_state.last_question = job["question"]
                st.session_state.failed_stage = failed_stage
                st.session_state.stopped_stage = None
                _persist_history_from_job(job, state, notify=True)
                sync_slots_from_state(state, slots)
                clear_run_job()
                st.error(msg)
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return

        if thread_result is not None:
            _apply_stage_result(state, stage_num, thread_result)
            save_stage_cache(job, stage_num, state, thread_result)
            st.session_state.workflow_state = state
            job["phase"] = "flush"
            job["thread"] = None
            ui.clear_stream_preview()
            ui.log(PARSING_RESPONSE)
            ui.set_progress(22 + stage_num * 18, text=f"Stage {stage_num} · 解析完成")
            ui.persist_logs(job)
            time.sleep(_POLL_INTERVAL_FAST)
            st.rerun()
            return

    if job["phase"] == "flush":
        _sync_visible_stage_slots(state, slots, job, paint_mode="full")
        pending = job.get("pending_flushes")
        if pending:
            flush_idx = int(job.get("_flush_queue_idx") or 0)
            stage_num = pending[flush_idx]
        else:
            stage_num = job["stages"][job["stage_index"]]

        _flush_stage(state, stage_num, slots, ui, job)
        ui.persist_logs(job)
        st.session_state.workflow_state = state
        _persist_history_from_job(job, state, notify=True, notify_updates=False)
        mask = sum(
            1 for s in range(1, 5) if stage_has_content(state, s)
        )
        ui.log(f"已同步历史（已完成 {mask}/4 个阶段，同题同模型合并为一条）")

        if pending:
            flush_idx = int(job.get("_flush_queue_idx") or 0)
            if flush_idx + 1 < len(pending):
                job["_flush_queue_idx"] = flush_idx + 1
                job["phase"] = "flush"
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return
            job["stage_index"] += len(pending)
            job["pending_flushes"] = None
            job["_flush_queue_idx"] = 0
        else:
            job["stage_index"] += 1

        if job["stage_index"] < len(job["stages"]):
            job["phase"] = "api"
            job["thread"] = None
            time.sleep(_POLL_INTERVAL_FAST)
            st.rerun()
            return
        _finish_job_success(ui, job, state, slots)
        time.sleep(_POLL_INTERVAL_FAST)
        st.rerun()
