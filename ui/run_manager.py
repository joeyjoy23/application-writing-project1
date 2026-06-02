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
from utils.config import build_settings, resolve_model_for_provider
from ui.run_cache import (
    merge_job_usage,
    save_stage_cache,
    should_parallel_stage23,
    try_load_cached_stage,
    try_load_parallel_cache,
)
from utils.status_log import (
    APP_START,
    CALLING_API,
    LOADING_PROMPT,
    PARSING_RESPONSE,
    PIPELINE_DONE,
    PREPARING,
    stage_call_api,
    stage_complete,
    stage_load_prompt,
)
from workflow import GaokaoWritingWorkflow, WorkflowState

from services.workflow_progress import get_next_stage, stage_has_content
from ui.history import auto_save_history
from ui.sidebar import api_key_configured, clear_run_job
from ui.stage_display import render_one_stage, sync_slots_from_state


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

    def __init__(self, steps: list[str] | None = None) -> None:
        self.progress = st.progress(0, text="等待开始…")
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

    def clear_stream_preview(self) -> None:
        self._live_line.empty()
        self._preview_title.empty()
        self._preview_body.empty()

    def set_progress(self, value: int, text: str) -> None:
        self.progress.progress(min(max(value, 0), 100), text=text)

    def sync_stream_from_job(self, job: dict[str, Any]) -> None:
        stage, total, preview = _read_job_stream(job)
        if total <= 0:
            return
        self.update_stream(stage, total, preview)

    def persist_logs(self, job: dict[str, Any]) -> None:
        job["logs"] = list(self._steps)


# ── 内部工具 ──


def _sync_cancel_from_settings(job: dict[str, Any]) -> None:
    if (
        st.session_state.provider != job["locked_provider"]
        or st.session_state.model != job["locked_model"]
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
    if should_parallel_stage23(job):
        out: set[int] = set()
        if not state.stage2:
            out.add(2)
        if not state.stage3:
            out.add(3)
        return out
    idx = job["stage_index"]
    stages = job.get("stages") or []
    if idx < len(stages):
        return {stages[idx]}
    return set()


def _sync_visible_stage_slots(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
    job: dict[str, Any] | None,
) -> None:
    """每次 rerun 后恢复已完成阶段展示，避免等待 Stage2/3 时 Stage1 消失。"""
    running = _running_stages_for_job(job, state) if job else set()
    if not any(stage_has_content(state, n) for n in range(1, 5)) and not running:
        return
    sync_slots_from_state(state, slots, running_stages=running)


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
    _sync_visible_stage_slots(state, slots, job)
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


def _job_on_stream(job: dict[str, Any], stage: int, cancel_event: threading.Event):
    def _cb(_d: str, total: int, full: str) -> None:
        if cancel_event.is_set():
            return
        preview = full[-2500:] if len(full) > 2500 else full
        with _ensure_job_lock(job):
            job["stream_stage"] = stage
            job["stream_total"] = total
            job["stream_preview"] = preview

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
            on_progress=_job_on_progress(job, 1, cancel_event),
            on_stream=_job_on_stream(job, 1, cancel_event),
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
            on_stream=_job_on_stream(job, 2, cancel_event),
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
            on_stream=_job_on_stream(job, 3, cancel_event),
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
            on_stream=_job_on_stream(job, 4, cancel_event),
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
        job["parallel_mode"] = False
        job["parallel_results"] = None
        job["stream_total"] = 0
        job["stream_preview"] = ""
        job["stream_stage"] = stage_num
        job["thread"].start()


def _start_parallel_23_thread(job: dict[str, Any], state: WorkflowState) -> None:
    """Stage2 与 Stage3 并行（仅依赖 Stage1）。"""
    cancel_event: threading.Event = job["cancel_event"]
    _ensure_job_lock(job)

    def worker() -> None:
        lock = _ensure_job_lock(job)
        results: dict[int, Any] = {}
        errors: dict[int, tuple[str, str]] = {}

        def run_one(stage_num: int) -> None:
            if cancel_event.is_set():
                errors[stage_num] = ("cancelled", "已切换模型或提供商，当前请求已停止。")
                return
            try:
                cached = try_load_cached_stage(job, stage_num, state)
                if cached is not None:
                    results[stage_num] = cached
                    return
                results[stage_num] = _execute_stage_api(
                    job, stage_num, state, cancel_event
                )
            except RunCancelled:
                errors[stage_num] = (
                    "cancelled",
                    "已切换模型或提供商，当前请求已停止。",
                )
            except Exception as e:
                logger.exception("并行 Stage %d 失败", stage_num)
                errors[stage_num] = ("error", str(e))

        t2 = threading.Thread(target=lambda: run_one(2), daemon=True)
        t3 = threading.Thread(target=lambda: run_one(3), daemon=True)
        t2.start()
        t3.start()
        timeout = _stage_timeout_seconds()
        t2.join(timeout=timeout)
        t3.join(timeout=timeout)
        if t2.is_alive():
            _stop_api_thread(t2, cancel_event)
        if t3.is_alive():
            _stop_api_thread(t3, cancel_event)

        with lock:
            if errors:
                sn = min(errors.keys())
                job["thread_error"] = errors[sn]
            elif len(results) < 2:
                job["thread_error"] = (
                    "error",
                    "Stage 2/3 并行未完成，请重试。",
                )
            else:
                job["parallel_results"] = results
            job["thread_done"] = True
            job["parallel_mode"] = True

    with _ensure_job_lock(job):
        job["thread"] = threading.Thread(target=worker, daemon=True)
        job["thread_done"] = False
        job["thread_error"] = None
        job["thread_result"] = None
        job["parallel_results"] = None
        job["parallel_mode"] = True
        job["stream_total"] = 0
        job["stream_preview"] = ""
        job["stream_stage"] = 2
        job["logs"].append("并行运行 Stage 2 与 Stage 3…")
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
    if should_parallel_stage23(job):
        hit = try_load_parallel_cache(job, state)
        if hit:
            _apply_stage_result(state, 2, hit[2])
            _apply_stage_result(state, 3, hit[3])
            st.session_state.workflow_state = state
            job["pending_flushes"] = [2, 3]
            job["_flush_queue_idx"] = 0
            job["phase"] = "flush"
            job["thread"] = None
            ui.log("已从缓存加载 Stage 2 与 Stage 3（未调用 API）")
            ui.persist_logs(job)
            try:
                st.toast("已从缓存加载 Stage 2 与 Stage 3", icon="ℹ️")
            except Exception:
                pass
            return True
        return False

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


def _prepare_stage_api_logs(ui: RunUI, stage_num: int) -> None:
    ui.log(LOADING_PROMPT)
    ui.log(stage_load_prompt(stage_num))
    ui.set_progress(8 + stage_num * 18, text=f"Stage {stage_num} · 加载提示词…")
    ui.log(CALLING_API)
    ui.log(stage_call_api(stage_num))
    model = st.session_state.get("run_job", {}).get("locked_model", st.session_state.model)
    ui._live_line.caption(
        f"正在连接 API（模型：**{model}**）。可随时在侧边栏换模型以停止本次请求。"
    )


def _apply_stage_result(state: WorkflowState, stage_num: int, result: Any) -> None:
    if stage_num == 1:
        state.stage1 = result
    elif stage_num == 2:
        state.stage2 = result
    elif stage_num == 3:
        state.stage3 = result
    elif stage_num == 4:
        state.stage4 = result


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
    auto_save_history(
        state,
        provider=job.get("locked_provider"),
        model=job.get("locked_model"),
        raw_input=job.get("question"),
        notify=notify,
        notify_updates=notify_updates,
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

    state: WorkflowState = st.session_state.workflow_state or WorkflowState(
        question=question
    )
    state.question = question

    if mode == "stage2" and not state.stage1:
        st.error("请先运行 Stage 1")
        return False
    if mode == "stage3" and not state.stage1:
        st.error("请先运行 Stage 1")
        return False
    if mode == "stage4" and (not state.stage1 or not state.stage2 or not state.stage3):
        st.error("请先完成 Stage 1、Stage 2 与 Stage 3")
        return False

    skip_completed = (mode == "full")
    stages = _pipeline_stages_for_mode(
        mode,
        skip_completed=skip_completed,
        state=state if skip_completed or mode == "resume" else None,
    )
    if not stages:
        st.info("所有阶段已完成，无需重新生成。如需重跑，请先清空结果。")
        return False

    st.session_state.workflow_state = state
    locked_provider = st.session_state.provider
    locked_model = resolve_model_for_provider(locked_provider, st.session_state.model)
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
        "logs": [APP_START, PREPARING],
        "stream_stage": stages[0],
        "stream_total": 0,
        "stream_preview": "",
        "usage_total": ChatUsage(),
        "pending_flushes": None,
        "_flush_queue_idx": 0,
        "parallel_mode": False,
        "parallel_results": None,
        "student_level": st.session_state.get("student_level", "中等"),
    }
    st.session_state.llm_run_usage = None
    if mode == "full":
        if len(stages) < 4:
            st.session_state.run_job["logs"].append(
                f"断点续传：跳过已完成阶段，从 Stage {stages[0]} 继续…"
            )
        else:
            st.session_state.run_job["logs"].append("Running full pipeline (4 stages)…")
    elif mode == "resume":
        st.session_state.run_job["logs"].append(
            f"断点续传：从 Stage {stages[0]} 继续生成…"
        )
    st.session_state.run_cancelled = False
    st.session_state.is_running = True
    st.session_state.failed_stage = None
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
    st.session_state.failed_stage = stage_num
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
        ui.log(PIPELINE_DONE)
        ui.status.update(label="✅ 完整流程已完成", state="complete")
    else:
        stage_num = job["stages"][-1]
        ui.set_progress(100, text=f"Stage {stage_num} 完成")
        ui.status.update(label=f"✅ Stage {stage_num} 完成", state="complete")
    ui.persist_logs(job)
    st.session_state.workflow_state = state
    st.session_state.last_question = job["question"]
    st.session_state.failed_stage = None
    logger.info("运行完成 mode=%s", mode)
    _persist_history_from_job(job, state, notify=False)
    clear_run_job()
    if state.errors:
        for err in state.errors:
            st.warning(err)


# ── 主循环 ──




def _poll_run_progress(
    question: str,
) -> bool:
    """轮询 API 线程进度（纯判断，不渲染任何 UI）。

    返回 True 表示线程仍在运行（应继续轮询），
    返回 False 表示已进入需要整页 rerun 的状态（调用方应 st.rerun()）。
    """
    job = st.session_state.run_job
    if not job or job["phase"] != "api":
        return False

    _sync_cancel_from_settings(job)
    thread = job.get("thread")

    # 还没启动线程 → 需要整页 rerun 来启动
    if thread is None:
        return False

    if not thread.is_alive():
        return False  # 线程结束，交给主流程处理状态转换

    # 检查取消
    if job["cancel_event"].is_set():
        return False  # 已取消，需整页处理

    # 线程仍在运行 → 刷新等待
    time.sleep(_POLL_INTERVAL_SLOW)
    st.rerun()
    return True  # 不可达（rerun 抛出异常），但类型检查需要


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
    ui = RunUI(job.get("logs"))
    stage_num = job["stages"][job["stage_index"]]
    _sync_visible_stage_slots(state, slots, job)

    if job["phase"] == "api":
        if job.get("thread") is None:
            # ── 启动阶段 ──
            if _begin_cached_or_api(job, state, ui, stage_num):
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return
            _prepare_stage_api_logs(ui, stage_num)
            ui.persist_logs(job)
            if should_parallel_stage23(job):
                _start_parallel_23_thread(job, state)
            else:
                _start_api_thread(job, stage_num, state)
            time.sleep(_POLL_INTERVAL_FAST)
            st.rerun()
            return

        thread: threading.Thread = job["thread"]
        ui.sync_stream_from_job(job)
        ui.persist_logs(job)

        if thread.is_alive():
            # 检查取消
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

            # ★ 线程仍在运行 → 进入 fragment 局部轮询
            _poll_run_progress(question)
            # fragment 返回后（线程结束/取消），重新进入主流程
            time.sleep(_POLL_INTERVAL_FAST)
            st.rerun()
            return

        # ── 线程结束，处理结果 ──
        with _ensure_job_lock(job):
            err = job.get("thread_error")
            thread_result = job.get("thread_result")
        if err:
            kind, msg = err
            if kind == "cancelled":
                _finish_job_cancelled(ui, job, msg, state, slots)
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return
            if kind == "timeout":
                ui.status.update(label=f"Stage {stage_num} 超时，跳过", state="error")
                ui.log(f"⏱️ {msg}")
                state.errors.append(msg)
                st.session_state.workflow_state = state
                st.session_state.last_question = job["question"]
                st.session_state.failed_stage = stage_num
                ui.persist_logs(job)
                _persist_history_from_job(job, state, notify=True)
                st.warning(msg)
                if job["stage_index"] + 1 < len(job["stages"]):
                    job["stage_index"] += 1
                    job["phase"] = "api"
                    job["thread"] = None
                    job["thread_done"] = False
                    job["thread_error"] = None
                    job["thread_result"] = None
                    job["stream_total"] = 0
                    job["stream_preview"] = ""
                    time.sleep(_POLL_INTERVAL_FAST)
                    st.rerun()
                    return
                _finish_job_success(ui, job, state, slots)
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
                st.session_state.failed_stage = stage_num
                _persist_history_from_job(job, state, notify=True)
                sync_slots_from_state(state, slots)
                clear_run_job()
                st.error(msg)
                time.sleep(_POLL_INTERVAL_FAST)
                st.rerun()
                return

        if job.get("parallel_mode") and job.get("parallel_results"):
            parallel = job["parallel_results"]
            for sn in (2, 3):
                if sn in parallel:
                    _apply_stage_result(state, sn, parallel[sn])
                    save_stage_cache(job, sn, state, parallel[sn])
            st.session_state.workflow_state = state
            job["pending_flushes"] = [2, 3]
            job["_flush_queue_idx"] = 0
            job["phase"] = "flush"
            job["thread"] = None
            job["parallel_results"] = None
            job["parallel_mode"] = False
            ui.clear_stream_preview()
            ui.log(PARSING_RESPONSE)
            ui.log("Stage 2 与 Stage 3 并行完成")
            ui.persist_logs(job)
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
