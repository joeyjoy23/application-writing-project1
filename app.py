"""
高考英语应用文 AI 分析系统 — Streamlit 入口
多阶段工作流，非聊天机器人。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv


def _ensure_utf8_environment() -> None:
    """Windows 下避免中文环境导致 HTTP 头 ASCII 编码失败。"""
    os.environ.setdefault("PYTHONUTF8", "1")
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8")
                except Exception:
                    pass


_ensure_utf8_environment()


def _make_export_word_filename(model: str, date_str: str | None = None) -> str:
    """Word 导出文件名：应用文分析_YYYY-MM-DD_模型名.docx"""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        date_str = date_str.strip()[:10]
    safe_model = re.sub(r'[<>:"/\\|?*]', "-", (model or "").strip()) or "model"
    return f"应用文分析_{date_str}_{safe_model}.docx"


from db import (
    count_records,
    delete_record,
    format_stages_mask,
    get_all_records,
    get_record_by_id,
    init_db,
    save_record,
)
from llm.client import LLMClient, RunCancelled
from utils.config import (
    PROVIDER_LABELS,
    PROVIDER_MODELS,
    PROVIDER_OPTIONS,
    build_settings,
    format_model_label,
    get_project_root,
    resolve_api_key,
)
from utils.export_word import export_workflow_to_word
from utils.image_ocr import extract_question_from_image_with_ui_settings
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
from workflow import (
    GaokaoWritingWorkflow,
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    WorkflowState,
)

load_dotenv(get_project_root() / ".env", encoding="utf-8")

ROOT = get_project_root()
CSS_PATH = ROOT / "styles" / "custom.css"


def load_css() -> None:
    if CSS_PATH.is_file():
        st.markdown(
            f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True,
        )


def init_session() -> None:
    defaults = {
        "workflow_state": None,
        "question": "",
        "is_running": False,
        "provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "model": os.getenv("LLM_MODEL", ""),
        "api_key": "",
        "uploaded_image_name": None,
        "app_mode": "新建",
        "history_view_id": None,
        "history_confirm_delete_id": None,
        "history_list_limit": 20,
        "history_search_keyword": "",
        "_last_save_fingerprint": None,
        "run_job": None,
        "run_cancelled": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _on_settings_changed() -> None:
    """侧边栏切换提供商/模型时，若正在运行则取消当前 API。"""
    job = st.session_state.get("run_job")
    if not st.session_state.get("is_running") or not job:
        return
    if (
        st.session_state.provider != job["locked_provider"]
        or st.session_state.model != job["locked_model"]
    ):
        job["cancel_event"].set()
        st.session_state.run_cancelled = True


def _clear_run_job() -> None:
    st.session_state.run_job = None
    st.session_state.is_running = False
    st.session_state.run_cancelled = False


def _sync_cancel_from_settings(job: dict[str, Any]) -> None:
    if (
        st.session_state.provider != job["locked_provider"]
        or st.session_state.model != job["locked_model"]
    ):
        job["cancel_event"].set()
        st.session_state.run_cancelled = True


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


def api_key_configured() -> bool:
    return bool(resolve_api_key(st.session_state.provider, st.session_state.api_key))


def workflow_state_to_json(
    state: WorkflowState,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> str:
    """将备课包序列化为 JSON 字符串存入数据库。"""
    payload = {
        "question": state.question,
        "provider": provider or st.session_state.provider,
        "model": model or st.session_state.model,
        "stage1_summary": state.stage1.human_summary if state.stage1 else None,
        "stage1_json": state.stage1.structured_json if state.stage1 else None,
        "stage2": state.stage2.raw if state.stage2 else None,
        "stage3": state.stage3.raw if state.stage3 else None,
        "stage4": state.stage4.raw if state.stage4 else None,
        "errors": state.errors,
    }
    return json.dumps(payload, ensure_ascii=False)


def _workflow_stages_mask(state: WorkflowState) -> str:
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


def workflow_state_from_json(content: str) -> WorkflowState:
    """从数据库记录还原 WorkflowState。"""
    data = json.loads(content)
    state = WorkflowState(question=data.get("question") or "")
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


def _workflow_content_length(state: WorkflowState) -> int:
    """统计备课包各阶段文本总字数（用于历史记录展示）。"""
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


def _auto_save_history(
    state: WorkflowState,
    *,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """生成完成后写入 SQLite；相同内容不重复存档。"""
    if not state.stage1:
        return
    try:
        content = workflow_state_to_json(state, provider=provider, model=model)
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if st.session_state.get("_last_save_fingerprint") == fingerprint:
            return
        actual_model = model or st.session_state.model
        topic = (state.question or "（无题目）").strip().replace("\n", " ")[:100]
        record_id = save_record(
            topic,
            actual_model,
            content,
            word_count=_workflow_content_length(state),
            stages_mask=_workflow_stages_mask(state),
        )
        st.session_state._last_save_fingerprint = fingerprint
        st.toast(f"备课包已自动保存至历史（#{record_id}）", icon="💾")
    except Exception as e:
        st.toast(f"历史保存失败：{e}", icon="⚠️")


def _render_export_buttons(
    state: WorkflowState,
    *,
    model_name: str | None = None,
    created_at: str | None = None,
    key_prefix: str = "export",
) -> None:
    """导出 JSON / Word（新建页与历史详情共用）。"""
    if not state.stage1:
        return
    st.divider()
    st.markdown("#### 导出报告")
    export = {
        "question": state.question,
        "stage1_json": state.stage1.structured_json,
        "stage1_summary": state.stage1.human_summary,
        "stage2": state.stage2.raw if state.stage2 else None,
        "stage3": state.stage3.raw if state.stage3 else None,
        "stage4": state.stage4.raw if state.stage4 else None,
    }
    model = model_name or st.session_state.model
    try:
        word_bytes = export_workflow_to_word(
            question=state.question,
            stage1_summary=state.stage1.human_summary,
            stage2_raw=state.stage2.raw if state.stage2 else None,
            stage3_raw=state.stage3.raw if state.stage3 else None,
            stage4_raw=state.stage4.raw if state.stage4 else None,
        )
        word_name = _make_export_word_filename(model, created_at)
    except Exception as e:
        word_bytes = None
        st.error(f"Word 生成失败: {e}")

    # 用内容哈希作为 key 后缀，确保内容更新后 download_button 的 key 随之变化，
    # 避免 Streamlit 缓存旧 widget state 导致按钮点击后无法再次下载。
    _content_hash = hashlib.md5(
        (state.question + (state.stage1.human_summary or "")).encode("utf-8")
    ).hexdigest()[:8]
    _dynamic_key = f"{key_prefix}_{_content_hash}"

    col_json, col_word = st.columns(2)
    with col_json:
        st.download_button(
            "下载 JSON",
            data=json.dumps(export, ensure_ascii=False, indent=2),
            file_name="gaokao_writing_analysis.json",
            mime="application/json",
            use_container_width=True,
            key=f"{_dynamic_key}_json",
        )
    with col_word:
        if word_bytes:
            word_label = "导出 Word" if key_prefix.startswith("hist_") else "一键导出 Word"
            st.download_button(
                word_label,
                data=word_bytes,
                file_name=word_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
                help="含题目、四阶段完整内容；标题/表格/列表已排版，便于阅读与打印",
                key=f"{_dynamic_key}_word",
            )


def render_sidebar() -> bool:
    """渲染侧边栏；返回 True 表示 API 已配置。"""
    with st.sidebar:
        st.header("📂 工作区")
        mode_options = ["新建", "历史"]
        current_mode = st.session_state.get("app_mode", "新建")
        if current_mode == "新建分析":
            current_mode = "新建"
        if current_mode == "查看历史":
            current_mode = "历史"
        mode_index = mode_options.index(current_mode) if current_mode in mode_options else 0
        st.session_state.app_mode = st.selectbox(
            "模式",
            mode_options,
            index=mode_index,
            help="新建：输入题目并运行备课流程；历史：查看、搜索、导出已保存的备课包",
        )
        try:
            total_hist = count_records()
            st.caption(f"历史记录：共 {total_hist} 条")
        except Exception:
            pass
        if st.session_state.app_mode == "历史":
            if st.button("刷新历史列表", use_container_width=True):
                st.session_state.history_list_limit = 20
                st.rerun()
        st.divider()
        st.header("⚙️ API 设置")

        if st.session_state.is_running:
            st.info(
                "运行中可切换下方模型；**切换后将自动停止**当前请求，"
                "再点击 Stage 按钮用新模型重跑。"
            )
            if st.button("停止当前运行", use_container_width=True, key="btn_stop_run"):
                job = st.session_state.get("run_job")
                if job:
                    job["cancel_event"].set()
                st.session_state.run_cancelled = True
                _clear_run_job()
                st.warning("已停止。请确认模型后重新点击 Stage。")
                st.rerun()

        st.selectbox(
            "模型提供商",
            options=PROVIDER_OPTIONS,
            format_func=lambda p: PROVIDER_LABELS.get(p, p),
            index=PROVIDER_OPTIONS.index(
                st.session_state.provider
                if st.session_state.provider in PROVIDER_OPTIONS
                else "deepseek"
            ),
            key="provider",
            on_change=_on_settings_changed,
            help="支持 OpenAI 兼容接口的常用服务；运行中切换会停止当前请求",
        )

        model_options = PROVIDER_MODELS.get(
            st.session_state.provider, ["deepseek-chat"]
        )
        current = st.session_state.model
        model_index = model_options.index(current) if current in model_options else 0
        st.selectbox(
            "模型",
            options=model_options,
            index=model_index,
            format_func=lambda m: format_model_label(st.session_state.provider, m),
            key="model",
            on_change=_on_settings_changed,
            help=(
                "百炼：最新旗舰优先排序；识图仍自动使用 qwen-vl-max。"
                "运行中切换会停止当前请求。"
                if st.session_state.provider == "dashscope"
                else "运行中切换会停止当前请求"
            ),
        )

        key_label = {
            "deepseek": "DeepSeek API Key",
            "openai": "OpenAI API Key",
            "gemini": "Gemini API Key",
            "dashscope": "阿里云百炼 API Key",
        }.get(st.session_state.provider, "API Key")

        st.session_state.api_key = st.text_input(
            key_label,
            value=st.session_state.api_key,
            type="password",
            help="留空则尝试从 .env 读取对应环境变量",
        )

        if api_key_configured():
            try:
                s = build_settings(
                    st.session_state.provider,
                    api_key=st.session_state.api_key,
                    model=st.session_state.model,
                )
                st.success("API Key 已配置")
                st.caption(f"模型: {s.model}")
                st.caption(
                    f"接口: {s.base_url[:36]}…"
                    if len(s.base_url) > 36
                    else f"接口: {s.base_url}"
                )
                if st.session_state.provider == "dashscope":
                    st.caption(
                        "若长时间停在 Calling API：优先试 **qwen-plus** 或 **deepseek-v4-flash**；"
                        "旗舰预览模型（如 qwen3.6-max-preview）首包可能很慢。"
                    )
            except ValueError as e:
                st.error(str(e))
                return False
        else:
            env_name = {
                "deepseek": "DEEPSEEK_API_KEY",
                "openai": "OPENAI_API_KEY",
                "gemini": "GEMINI_API_KEY",
                "dashscope": "DASHSCOPE_API_KEY",
            }.get(st.session_state.provider, "OPENAI_API_KEY")
            st.warning(f"请在上方输入 Key，或在 .env 配置 {env_name}")
            return False

        st.divider()
        st.header("工作流说明")
        st.markdown(
            """
**Stage 1** — 审题结构分析  

**Stage 2** — PEEL 写作策略卡与范文  

**Stage 3** — 功能句型包 + 话题词汇  

**Stage 4** — 教学指南与易错预警
            """
        )
    return True


def render_stage1(state: WorkflowState) -> None:
    st.markdown('<span class="stage-badge stage-1">Stage 1</span> 审题结构分析', unsafe_allow_html=True)
    if not state.stage1:
        st.info("尚未运行 Stage 1")
        return

    s1 = state.stage1
    if s1.human_summary.strip():
        st.markdown(s1.human_summary)
    else:
        st.info("暂无审题总结内容")


def render_stage2(state: WorkflowState) -> None:
    st.markdown('<span class="stage-badge stage-2">Stage 2</span> PEEL 写作策略卡与多版范文', unsafe_allow_html=True)
    if not state.stage2:
        st.info("尚未运行 Stage 2（需先完成 Stage 1）")
        return
    raw = state.stage2.raw
    if len(raw) > 24000:
        st.caption(f"Stage 2 共约 {len(raw)} 字，以下显示前 12000 字，完整内容请导出 Word/JSON。")
        st.markdown(raw[:12000] + "\n\n…（后文已省略）")
    else:
        st.markdown(raw)


def render_stage3(state: WorkflowState) -> None:
    st.markdown(
        '<span class="stage-badge stage-3">Stage 3</span> 功能句型包与话题词汇',
        unsafe_allow_html=True,
    )
    if not state.stage3:
        st.info("尚未运行 Stage 3（需先完成 Stage 1）")
        return
    raw = state.stage3.raw
    if len(raw) > 18000:
        st.caption(f"Stage 3 共约 {len(raw)} 字，以下显示前 10000 字，完整内容请导出 Word/JSON。")
        st.markdown(raw[:10000] + "\n\n…（后文已省略）")
    else:
        st.markdown(raw)


def render_stage4(state: WorkflowState) -> None:
    st.markdown(
        '<span class="stage-badge stage-4">Stage 4</span> 教学指南与易错预警',
        unsafe_allow_html=True,
    )
    if not state.stage4:
        st.info("尚未运行 Stage 4（需先完成 Stage 2 与 Stage 3）")
        return
    raw = state.stage4.raw
    if len(raw) > 20000:
        st.caption(f"Stage 4 共约 {len(raw)} 字，以下显示前 10000 字，完整内容请导出 Word/JSON。")
        st.markdown(raw[:10000] + "\n\n…（后文已省略）")
    else:
        st.markdown(raw)


_STAGE_RENDERERS = {
    1: render_stage1,
    2: render_stage2,
    3: render_stage3,
    4: render_stage4,
}

_STAGE_WAITING = {
    1: "尚未运行 Stage 1",
    2: "尚未运行 Stage 2（需先完成 Stage 1）",
    3: "尚未运行 Stage 3（需先完成 Stage 1）",
    4: "尚未运行 Stage 4（需先完成 Stage 2 与 Stage 3）",
}


def _stage_has_content(state: WorkflowState, stage_num: int) -> bool:
    return {
        1: state.stage1,
        2: state.stage2,
        3: state.stage3,
        4: state.stage4,
    }.get(stage_num) is not None


def _render_one_stage(slot: st.empty, state: WorkflowState, stage_num: int) -> None:
    """仅更新单个 Stage 占位，避免重复渲染全文。"""
    with slot.container():
        _STAGE_RENDERERS[stage_num](state)


_STAGE_BADGE_TITLES = {
    1: '<span class="stage-badge stage-1">Stage 1</span> 审题结构分析',
    2: '<span class="stage-badge stage-2">Stage 2</span> PEEL 写作策略卡与多版范文',
    3: '<span class="stage-badge stage-3">Stage 3</span> 功能句型包与话题词汇',
    4: '<span class="stage-badge stage-4">Stage 4</span> 教学指南与易错预警',
}


def _render_stage_placeholder(slot: st.empty, stage_num: int) -> None:
    with slot.container():
        st.markdown(_STAGE_BADGE_TITLES[stage_num], unsafe_allow_html=True)
        st.info(_STAGE_WAITING[stage_num])


def _sync_slots_from_state(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    """按当前状态刷新各占位（已有结果则显示，否则显示等待提示）。"""
    for n, slot in enumerate(slots, start=1):
        if _stage_has_content(state, n):
            _render_one_stage(slot, state, n)
        else:
            _render_stage_placeholder(slot, n)


def render_all_stages(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    """页面加载时展示各阶段（已有结果显示内容，未运行显示提示）。"""
    for n, slot in enumerate(slots, start=1):
        if _stage_has_content(state, n):
            _render_one_stage(slot, state, n)
        else:
            _render_stage_placeholder(slot, n)


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
        total = int(job.get("stream_total") or 0)
        if total <= 0:
            return
        stage = int(job.get("stream_stage") or 1)
        preview = job.get("stream_preview") or ""
        self.update_stream(stage, total, preview)

    def persist_logs(self, job: dict[str, Any]) -> None:
        job["logs"] = list(self._steps)


def _flush_stage(
    state: WorkflowState,
    stage_num: int,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
    ui: RunUI,
) -> None:
    """保存状态并仅渲染刚完成的 Stage（不重复渲染前序大段内容）。"""
    st.session_state.workflow_state = state
    ui.clear_stream_preview()
    ui.log(f"正在显示 Stage {stage_num} 结果…")
    ui.set_progress(min(82 + stage_num * 4, 99), text=f"Stage {stage_num} · 显示结果…")
    _render_one_stage(slots[stage_num - 1], state, stage_num)
    ui.log(stage_complete(stage_num))


def _job_append_log(job: dict[str, Any], message: str) -> None:
    logs: list[str] = job.setdefault("logs", [])
    if message and message not in logs:
        logs.append(message)


def _job_on_progress(job: dict[str, Any], stage: int):
    def _cb(msg: str) -> None:
        _job_append_log(job, msg)
        job["stream_stage"] = stage

    return _cb


def _job_on_stream(job: dict[str, Any], stage: int):
    def _cb(_d: str, total: int, full: str) -> None:
        job["stream_stage"] = stage
        job["stream_total"] = total
        job["stream_preview"] = full[-2500:] if len(full) > 2500 else full

    return _cb


def _execute_stage_api(
    job: dict[str, Any], stage_num: int, state: WorkflowState
) -> Any:
    wf = get_workflow_from_job(job)
    question = job["question"]
    should_cancel = job["cancel_event"].is_set

    if stage_num == 1:
        return wf.run_stage1(
            question,
            on_progress=_job_on_progress(job, 1),
            on_stream=_job_on_stream(job, 1),
            should_cancel=should_cancel,
        )
    if stage_num == 2:
        return wf.run_stage2(
            question,
            state.stage1.structured_json,  # type: ignore[union-attr]
            on_progress=_job_on_progress(job, 2),
            on_stream=_job_on_stream(job, 2),
            should_cancel=should_cancel,
        )
    if stage_num == 3:
        return wf.run_stage3(
            question,
            state.stage1.structured_json,  # type: ignore[union-attr]
            on_progress=_job_on_progress(job, 3),
            on_stream=_job_on_stream(job, 3),
            should_cancel=should_cancel,
        )
    if stage_num == 4:
        return wf.run_stage4(
            state.stage1.structured_json,  # type: ignore[union-attr]
            state.stage2.raw,  # type: ignore[union-attr]
            state.stage3.raw,  # type: ignore[union-attr]
            on_progress=_job_on_progress(job, 4),
            on_stream=_job_on_stream(job, 4),
            should_cancel=should_cancel,
        )
    raise ValueError(f"invalid stage: {stage_num}")


_STAGE_TIMEOUT_SECONDS = 90  # 每个 Stage 的 API 超时时间（秒）


def _start_api_thread(job: dict[str, Any], stage_num: int, state: WorkflowState) -> None:
    def worker() -> None:
        try:
            timeout_msg = (
                f"Stage {stage_num} 生成超时，"
                "请切换到更快的模型（如 qwen-plus）重试，或稍后再试。"
            )
            result_holder: list[Any] = []
            error_holder: list[tuple[str, str]] = []

            def _run_once() -> None:
                """单次 API 调用，结果写入 result_holder / error_holder。"""
                try:
                    result_holder.append(_execute_stage_api(job, stage_num, state))
                except RunCancelled:
                    error_holder.append(("cancelled", "已切换模型或提供商，当前请求已停止。"))
                except Exception as e:
                    error_holder.append(("error", str(e)))

            for attempt in range(2):  # 最多尝试 2 次：初次 + 超时重试
                result_holder.clear()
                error_holder.clear()

                t = threading.Thread(target=_run_once, daemon=True)
                t.start()
                t.join(timeout=_STAGE_TIMEOUT_SECONDS)

                if not t.is_alive():
                    # 线程在超时内完成
                    if result_holder:
                        job["thread_result"] = result_holder[0]
                        return
                    if error_holder:
                        kind, msg = error_holder[0]
                        if kind == "cancelled":
                            job["thread_error"] = ("cancelled", msg)
                            return
                        # 非超时错误（如 API Key 无效），不重试
                        job["thread_error"] = ("error", msg)
                        return
                # 线程仍在运行 → 超时，尝试取消并重试
                if attempt == 0:
                    # 首次超时，准备重试
                    continue
                # 第二次也超时
                job["thread_error"] = ("timeout", timeout_msg)
                return

            # 不应到达，但保险起见
            job["thread_error"] = ("timeout", timeout_msg)
        finally:
            job["thread_done"] = True

    job["thread"] = threading.Thread(target=worker, daemon=True)
    job["thread_done"] = False
    job["thread_error"] = None
    job["thread_result"] = None
    job["stream_total"] = 0
    job["stream_preview"] = ""
    job["stream_stage"] = stage_num
    job["thread"].start()


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


def _pipeline_stages_for_mode(mode: str) -> list[int]:
    if mode == "full":
        return [1, 2, 3, 4]
    if mode == "stage1":
        return [1]
    if mode == "stage2":
        return [2]
    if mode == "stage3":
        return [3]
    if mode == "stage4":
        return [4]
    return []


def _try_start_run_job(mode: str, question: str) -> bool:
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

    stages = _pipeline_stages_for_mode(mode)
    if not stages:
        return False

    st.session_state.workflow_state = state
    st.session_state.run_job = {
        "mode": mode,
        "question": question,
        "stages": stages,
        "stage_index": 0,
        "phase": "api",
        "locked_provider": st.session_state.provider,
        "locked_model": st.session_state.model,
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
    }
    if mode == "full":
        st.session_state.run_job["logs"].append("Running full pipeline (4 stages)…")
    st.session_state.run_cancelled = False
    st.session_state.is_running = True
    return True


def _finish_job_cancelled(
    ui: RunUI,
    job: dict[str, Any],
    msg: str,
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    ui.log(f"⏹ {msg}")
    ui.status.update(label="已停止", state="error")
    ui.persist_logs(job)
    st.session_state.workflow_state = state
    _sync_slots_from_state(state, slots)
    _clear_run_job()
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
    _auto_save_history(
        state,
        provider=job.get("locked_provider"),
        model=job.get("locked_model"),
    )
    _clear_run_job()
    if state.errors:
        for err in state.errors:
            st.warning(err)


def advance_run_job(
    question: str,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    """轮询后台 API；允许侧边栏在 rerun 间切换模型并取消。"""
    job = st.session_state.run_job
    if not job:
        return

    _sync_cancel_from_settings(job)
    state: WorkflowState = st.session_state.workflow_state or WorkflowState(
        question=question
    )
    state.question = job["question"]
    _sync_slots_from_state(state, slots)

    ui = RunUI(job.get("logs"))
    stage_num = job["stages"][job["stage_index"]]

    if job["phase"] == "api":
        if job.get("thread") is None:
            _prepare_stage_api_logs(ui, stage_num)
            ui.persist_logs(job)
            _start_api_thread(job, stage_num, state)
            time.sleep(0.35)
            st.rerun()

        thread: threading.Thread = job["thread"]
        ui.sync_stream_from_job(job)
        ui.persist_logs(job)

        if thread.is_alive():
            if job["cancel_event"].is_set():
                thread.join(timeout=2.0)
                _finish_job_cancelled(
                    ui,
                    job,
                    "已切换模型或提供商，当前请求已停止。请用新模型重新点击运行。",
                    state,
                    slots,
                )
                time.sleep(0.35)
                st.rerun()
                return
            time.sleep(0.45)
            st.rerun()
            return

        err = job.get("thread_error")
        if err:
            kind, msg = err
            if kind == "cancelled":
                _finish_job_cancelled(ui, job, msg, state, slots)
                time.sleep(0.35)
                st.rerun()
                return
            if kind == "timeout":
                # 超时跳过当前 Stage，保留已有结果，继续下一个
                ui.status.update(label=f"Stage {stage_num} 超时，跳过", state="warning")
                ui.log(f"⏱️ {msg}")
                state.errors.append(msg)
                st.session_state.workflow_state = state
                ui.persist_logs(job)
                st.warning(msg)
                # 跳到下一个 Stage
                if job["stage_index"] + 1 < len(job["stages"]):
                    job["stage_index"] += 1
                    job["phase"] = "api"
                    job["thread"] = None
                    job["thread_done"] = False
                    job["thread_error"] = None
                    job["thread_result"] = None
                    job["stream_total"] = 0
                    job["stream_preview"] = ""
                    time.sleep(0.2)
                    st.rerun()
                    return
                # 已是最后一个 Stage，结束流程
                _finish_job_success(ui, job, state, slots)
                time.sleep(0.2)
                st.rerun()
                return
            else:
                ui.status.update(label="执行失败", state="error")
                ui.log(f"❌ {msg}")
                state.errors.append(msg)
                ui.persist_logs(job)
                st.session_state.workflow_state = state
                _sync_slots_from_state(state, slots)
                _clear_run_job()
                st.error(msg)
            time.sleep(0.35)
            st.rerun()
            return

        if job.get("thread_result") is not None:
            _apply_stage_result(state, stage_num, job["thread_result"])
            st.session_state.workflow_state = state
            job["phase"] = "flush"
            job["thread"] = None
            ui.clear_stream_preview()
            ui.log(PARSING_RESPONSE)
            ui.set_progress(22 + stage_num * 18, text=f"Stage {stage_num} · 解析完成")
            ui.persist_logs(job)
            time.sleep(0.2)
            st.rerun()
            return

    if job["phase"] == "flush":
        _flush_stage(state, stage_num, slots, ui)
        ui.persist_logs(job)
        if job["stage_index"] + 1 < len(job["stages"]):
            job["stage_index"] += 1
            job["phase"] = "api"
            job["thread"] = None
            time.sleep(0.2)
            st.rerun()
            return
        _finish_job_success(ui, job, state, slots)
        time.sleep(0.2)
        st.rerun()


def render_history_list() -> None:
    """历史列表：搜索、表格、查看/删除、加载更多。"""
    st.subheader("📚 历史备课包")
    keyword = st.text_input(
        "搜索题目",
        value=st.session_state.history_search_keyword,
        placeholder="输入关键词模糊匹配题目摘要…",
        key="history_search_input",
    )
    st.session_state.history_search_keyword = keyword

    limit = st.session_state.history_list_limit
    records = get_all_records(keyword or None, limit=limit, offset=0)
    total = count_records(keyword or None)

    if not records:
        st.info("暂无历史记录，请在「新建」模式中生成备课包。")
        return

    st.caption(f"共 {total} 条记录，当前显示最近 {len(records)} 条（支持按题目或模型搜索）")

    header = st.columns([2, 3, 2, 2, 1, 1, 1])
    header[0].markdown("**生成时间**")
    header[1].markdown("**题目摘要**")
    header[2].markdown("**模型**")
    header[3].markdown("**阶段**")
    header[4].markdown("**字数**")
    header[5].markdown("**操作**")
    header[6].markdown("")

    for rec in records:
        rid = rec["id"]
        cols = st.columns([2, 3, 2, 2, 1, 1, 1])
        cols[0].write(rec["created_at"])
        topic_show = rec["topic"]
        if len(topic_show) > 50:
            topic_show = topic_show[:50] + "…"
        cols[1].write(topic_show)
        cols[2].write(rec["model_name"])
        cols[3].caption(format_stages_mask(rec.get("stages_mask")))
        cols[4].write(rec.get("word_count", "—"))
        if cols[5].button("查看", key=f"hist_view_{rid}", use_container_width=True):
            st.session_state.history_view_id = rid
            st.session_state.history_confirm_delete_id = None
            st.rerun()
        if cols[6].button("删除", key=f"hist_del_{rid}", use_container_width=True):
            st.session_state.history_confirm_delete_id = rid
            st.rerun()

    confirm_id = st.session_state.history_confirm_delete_id
    if confirm_id is not None:
        target = get_record_by_id(confirm_id)
        label = (target or {}).get("topic", "")[:40] if target else str(confirm_id)
        st.warning(f"确认删除记录 #{confirm_id}？\n\n{label}")
        c1, c2 = st.columns(2)
        if c1.button("确认删除", type="primary", key="hist_del_confirm"):
            delete_record(confirm_id)
            st.session_state.history_confirm_delete_id = None
            if st.session_state.history_view_id == confirm_id:
                st.session_state.history_view_id = None
            st.success("已删除")
            st.rerun()
        if c2.button("取消", key="hist_del_cancel"):
            st.session_state.history_confirm_delete_id = None
            st.rerun()

    if len(records) < total:
        if st.button("加载更多", use_container_width=True):
            st.session_state.history_list_limit = limit + 20
            st.rerun()


def render_history_detail(record_id: int) -> None:
    """历史详情：完整备课包 + 导出 Word + 返回列表。"""
    record = get_record_by_id(record_id)
    if not record:
        st.error("记录不存在或已被删除")
        if st.button("返回列表"):
            st.session_state.history_view_id = None
            st.rerun()
        return

    col_back, col_meta = st.columns([1, 3])
    with col_back:
        if st.button("← 返回列表", use_container_width=True):
            st.session_state.history_view_id = None
            st.rerun()
    with col_meta:
        st.caption(
            f"生成时间：{record['created_at']} · 模型：{record['model_name']} · "
            f"阶段：{format_stages_mask(record.get('stages_mask'))} · "
            f"约 {record.get('word_count', 0)} 字"
        )

    st.markdown("#### 题目")
    try:
        state = workflow_state_from_json(record["full_content"])
    except json.JSONDecodeError:
        st.error("记录内容损坏，无法解析")
        return

    st.markdown(state.question or record["topic"])

    st.divider()
    st.subheader("备课包内容")
    slot1, slot2, slot3, slot4 = st.empty(), st.empty(), st.empty(), st.empty()
    render_all_stages(state, (slot1, slot2, slot3, slot4))

    _render_export_buttons(
        state,
        model_name=record["model_name"],
        created_at=record["created_at"],
        key_prefix=f"hist_{record_id}",
    )


def render_history_page() -> None:
    """查看历史模式主界面。"""
    view_id = st.session_state.history_view_id
    if view_id is not None:
        render_history_detail(view_id)
    else:
        render_history_list()


def render_new_analysis(api_ready: bool) -> None:
    """新建分析模式：原有输入与运行流程。"""
    tab_text, tab_image = st.tabs(["📝 文字输入", "🖼️ 图片识题"])

    with tab_image:
        st.caption("上传高考真题/试卷照片，自动识别题目文字后，与手动输入走相同备课流程。")
        uploaded = st.file_uploader(
            "上传真题图片",
            type=["png", "jpg", "jpeg", "webp"],
            help="支持试卷截图、拍照，请保证题目区域清晰完整",
        )
        if uploaded is not None:
            st.image(uploaded, caption=uploaded.name, use_container_width=True)
            col_ocr, _ = st.columns([1, 2])
            with col_ocr:
                btn_ocr = st.button("识别题目文字", type="secondary", use_container_width=True)
            if btn_ocr:
                if not api_ready:
                    st.error("请先在侧边栏配置 API Key")
                else:
                    with st.spinner("正在识别图片中的题目…"):
                        try:
                            image_bytes = uploaded.getvalue()
                            recognized = extract_question_from_image_with_ui_settings(
                                image_bytes,
                                st.session_state.provider,
                                api_key=st.session_state.api_key,
                                model=st.session_state.model,
                                mime_type=uploaded.type,
                                filename=uploaded.name,
                            )
                            st.session_state.question = recognized
                            st.session_state.uploaded_image_name = uploaded.name
                            st.success("识别完成，已填入下方题目框，可直接运行备课流程")
                            st.rerun()
                        except Exception as e:
                            st.error(f"识题失败: {e}")

        if st.session_state.uploaded_image_name:
            st.info(f"最近识图来源：{st.session_state.uploaded_image_name}")

    with tab_text:
        st.caption("直接粘贴或输入完整题目（含要点、字数要求）。")

    question = st.text_area(
        "题目内容（可粘贴文字，或由图片识别自动填入）",
        value=st.session_state.question,
        height=220,
        placeholder="例如：假定你是李华，校英文报正在开展…请写一封建议信…",
        key="question_editor",
    )
    st.session_state.question = question

    running = st.session_state.is_running

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        btn_full = st.button(
            "完整流程",
            type="primary",
            use_container_width=True,
        )
    with col2:
        btn_s1 = st.button("Stage 1", use_container_width=True)
    with col3:
        btn_s2 = st.button("Stage 2", use_container_width=True)
    with col4:
        btn_s3 = st.button("Stage 3", use_container_width=True)
    with col5:
        btn_s4 = st.button("Stage 4", use_container_width=True)

    if st.button("清空结果"):
        st.session_state.workflow_state = None
        st.rerun()

    if not question.strip():
        st.warning("请先输入题目，或在「图片识题」中上传真题并点击「识别题目文字」")
        return

    if not api_ready:
        st.info("请先在左侧边栏选择 API 提供商并填写 Key")
        return

    clicked_mode: str | None = None
    if btn_full:
        clicked_mode = "full"
    elif btn_s1:
        clicked_mode = "stage1"
    elif btn_s2:
        clicked_mode = "stage2"
    elif btn_s3:
        clicked_mode = "stage3"
    elif btn_s4:
        clicked_mode = "stage4"

    st.divider()
    st.subheader("运行状态与结果")
    if running or clicked_mode or st.session_state.run_job:
        st.caption(
            "运行中可在侧边栏切换模型以**自动停止**当前请求；"
            "停止后请重新点击 Stage。生成内容会逐块显示在下方。"
        )

    # 导出按钮提前到阶段展示区之前，只要有 stage1 就立即可用，不必等全部运行完
    _early_state = st.session_state.workflow_state
    if _early_state and _early_state.stage1:
        _render_export_buttons(_early_state)

    stage_slot1 = st.empty()
    stage_slot2 = st.empty()
    stage_slot3 = st.empty()
    stage_slot4 = st.empty()
    stage_slots = (stage_slot1, stage_slot2, stage_slot3, stage_slot4)

    if st.session_state.run_job:
        advance_run_job(question, stage_slots)
    elif clicked_mode:
        if _try_start_run_job(clicked_mode, question):
            st.rerun()
    else:
        cached = st.session_state.workflow_state
        if cached:
            render_all_stages(cached, stage_slots)

    state = st.session_state.workflow_state
    if not state:
        return

    if state.errors:
        for err in state.errors:
            st.error(err)


def main() -> None:
    st.set_page_config(
        page_title="高考英语应用文 AI 分析",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_css()
    init_session()
    init_db()
    api_ready = render_sidebar()

    st.title("高考英语应用文 AI 分析系统")

    if st.session_state.app_mode == "历史":
        render_history_page()
        return

    render_new_analysis(api_ready)


if __name__ == "__main__":
    main()
