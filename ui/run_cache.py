"""运行期 LLM 缓存与 Stage2/3 并行辅助。"""

from __future__ import annotations

import logging
import threading
from typing import Any

import streamlit as st

from db import get_cached_stage_result, save_cached_stage_result
from llm.usage import ChatUsage
from workflow import WorkflowState

logger = logging.getLogger("app.run_cache")


def llm_cache_enabled() -> bool:
    return bool(st.session_state.get("use_llm_cache", True))


def _cache_kwargs(job: dict[str, Any], state: WorkflowState) -> dict[str, Any]:
    kw: dict[str, Any] = {
        "provider": job["locked_provider"],
        "model": job["locked_model"],
        "question": job["question"],
    }
    if state.stage1:
        kw["stage1_json"] = state.stage1.structured_json
    if state.stage2:
        kw["stage2_raw"] = state.stage2.raw
    if state.stage3:
        kw["stage3_raw"] = state.stage3.raw
    if job.get("student_level"):
        kw["student_level"] = job["student_level"]
    return kw


def try_load_cached_stage(
    job: dict[str, Any], stage_num: int, state: WorkflowState
) -> Any | None:
    if not llm_cache_enabled():
        return None
    try:
        return get_cached_stage_result(stage=stage_num, **_cache_kwargs(job, state))
    except Exception as exc:
        logger.warning("读取 LLM 缓存失败 stage=%s: %s", stage_num, exc)
        return None


def save_stage_cache(
    job: dict[str, Any], stage_num: int, state: WorkflowState, result: Any
) -> None:
    if not llm_cache_enabled():
        return
    try:
        save_cached_stage_result(stage=stage_num, result=result, **_cache_kwargs(job, state))
    except Exception as exc:
        logger.warning("写入 LLM 缓存失败 stage=%s: %s", stage_num, exc)


def merge_job_usage(job: dict[str, Any], usage: ChatUsage) -> None:
    total: ChatUsage = job.setdefault("usage_total", ChatUsage())
    total.merge(usage)
    st.session_state.llm_run_usage = {
        "prompt_tokens": total.prompt_tokens,
        "completion_tokens": total.completion_tokens,
        "cached_tokens": total.cached_tokens,
    }


def should_parallel_stage23(job: dict[str, Any]) -> bool:
    if job.get("mode") not in ("full", "resume"):
        return False
    stages = job["stages"]
    i = job["stage_index"]
    return i + 1 < len(stages) and stages[i] == 2 and stages[i + 1] == 3


def try_load_parallel_cache(
    job: dict[str, Any], state: WorkflowState
) -> dict[int, Any] | None:
    r2 = try_load_cached_stage(job, 2, state)
    r3 = try_load_cached_stage(job, 3, state)
    if r2 is not None and r3 is not None:
        return {2: r2, 3: r3}
    return None
