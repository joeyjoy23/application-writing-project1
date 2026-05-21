"""
高考英语应用文 AI 分析系统 — Streamlit 入口
多阶段工作流，非聊天机器人。
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

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


def _make_export_word_filename(model: str) -> str:
    """Word 导出文件名：应用文分析_YYYY-MM-DD_模型名.docx"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    safe_model = re.sub(r'[<>:"/\\|?*]', "-", (model or "").strip()) or "model"
    return f"应用文分析_{date_str}_{safe_model}.docx"


from llm.client import LLMClient
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
from workflow import GaokaoWritingWorkflow, WorkflowState

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
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def get_workflow() -> GaokaoWritingWorkflow:
    settings = build_settings(
        st.session_state.provider,
        api_key=st.session_state.api_key,
        model=st.session_state.model,
    )
    return GaokaoWritingWorkflow(client=LLMClient(settings))


def api_key_configured() -> bool:
    return bool(resolve_api_key(st.session_state.provider, st.session_state.api_key))


def render_sidebar() -> bool:
    """渲染侧边栏；返回 True 表示 API 已配置。"""
    with st.sidebar:
        st.header("⚙️ API 设置")

        st.session_state.provider = st.selectbox(
            "模型提供商",
            options=PROVIDER_OPTIONS,
            format_func=lambda p: PROVIDER_LABELS.get(p, p),
            index=PROVIDER_OPTIONS.index(
                st.session_state.provider
                if st.session_state.provider in PROVIDER_OPTIONS
                else "deepseek"
            ),
            help="支持 OpenAI 兼容接口的常用服务",
        )

        model_options = PROVIDER_MODELS.get(
            st.session_state.provider, ["deepseek-chat"]
        )
        current = st.session_state.model
        model_index = model_options.index(current) if current in model_options else 0
        st.session_state.model = st.selectbox(
            "模型",
            options=model_options,
            index=model_index,
            format_func=lambda m: format_model_label(st.session_state.provider, m),
            help=(
                "百炼：最新旗舰优先排序；识图仍自动使用 qwen-vl-max"
                if st.session_state.provider == "dashscope"
                else None
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
                        "若长时间停在 Calling API，可改选 qwen-plus 或 deepseek-v4-flash 试跑。"
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

**Stage 2** — PEEL 与三版范文  

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
    st.markdown('<span class="stage-badge stage-2">Stage 2</span> PEEL 与多版范文', unsafe_allow_html=True)
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
    2: '<span class="stage-badge stage-2">Stage 2</span> PEEL 与多版范文',
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

    def __init__(self) -> None:
        self.progress = st.progress(0, text="等待开始…")
        self.status = st.status("运行状态", expanded=True)
        self._steps: list[str] = []
        self._step_area = self.status.empty()
        self._live_line = st.empty()
        self._preview_title = st.empty()
        self._preview_body = st.empty()
        self._last_stream_total = 0
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


def _stage_callbacks(ui: RunUI, stage: int):
    def on_progress(msg: str) -> None:
        ui.log(msg)
        ui.set_progress(8 + stage * 18, text=f"Stage {stage} · Calling API…")

    def on_stream(_delta: str, total: int, full: str) -> None:
        ui.update_stream(stage, total, full)

    return on_progress, on_stream


def _run_stage1(wf: GaokaoWritingWorkflow, state: WorkflowState, question: str, ui: RunUI) -> None:
    on_progress, on_stream = _stage_callbacks(ui, 1)
    ui.log(LOADING_PROMPT)
    ui.log(stage_load_prompt(1))
    ui.set_progress(10, text="Stage 1 · 加载提示词…")
    ui.log(CALLING_API)
    ui.log(stage_call_api(1))
    state.stage1 = wf.run_stage1(
        question, on_progress=on_progress, on_stream=on_stream
    )
    ui.clear_stream_preview()
    ui.log(PARSING_RESPONSE)
    ui.set_progress(22, text="Stage 1 · 解析完成")


def _run_stage2(wf: GaokaoWritingWorkflow, state: WorkflowState, question: str, ui: RunUI) -> None:
    on_progress, on_stream = _stage_callbacks(ui, 2)
    ui.log(LOADING_PROMPT)
    ui.log(stage_load_prompt(2))
    ui.set_progress(28, text="Stage 2 · 加载提示词…")
    ui.log(CALLING_API)
    ui.log(stage_call_api(2))
    state.stage2 = wf.run_stage2(
        question,
        state.stage1.structured_json,  # type: ignore[union-attr]
        on_progress=on_progress,
        on_stream=on_stream,
    )
    ui.clear_stream_preview()
    ui.log(PARSING_RESPONSE)
    ui.set_progress(45, text="Stage 2 · 解析完成")


def _run_stage3(wf: GaokaoWritingWorkflow, state: WorkflowState, question: str, ui: RunUI) -> None:
    on_progress, on_stream = _stage_callbacks(ui, 3)
    ui.log(LOADING_PROMPT)
    ui.log(stage_load_prompt(3))
    ui.set_progress(50, text="Stage 3 · 加载提示词…")
    ui.log(CALLING_API)
    ui.log(stage_call_api(3))
    state.stage3 = wf.run_stage3(
        question,
        state.stage1.structured_json,  # type: ignore[union-attr]
        on_progress=on_progress,
        on_stream=on_stream,
    )
    ui.clear_stream_preview()
    ui.log(PARSING_RESPONSE)
    ui.set_progress(68, text="Stage 3 · 解析完成")


def _run_stage4(wf: GaokaoWritingWorkflow, state: WorkflowState, ui: RunUI) -> None:
    on_progress, on_stream = _stage_callbacks(ui, 4)
    ui.log(LOADING_PROMPT)
    ui.log(stage_load_prompt(4))
    ui.set_progress(72, text="Stage 4 · 加载提示词…")
    ui.log(CALLING_API)
    ui.log(stage_call_api(4))
    state.stage4 = wf.run_stage4(
        state.stage1.structured_json,  # type: ignore[union-attr]
        state.stage2.raw,  # type: ignore[union-attr]
        state.stage3.raw,  # type: ignore[union-attr]
        on_progress=on_progress,
        on_stream=on_stream,
    )
    ui.clear_stream_preview()
    ui.log(PARSING_RESPONSE)
    ui.set_progress(92, text="Stage 4 · 解析完成")


def run_workflow(
    mode: str,
    question: str,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    if st.session_state.is_running:
        st.warning("正在分析中，请勿重复点击")
        return
    if not api_key_configured():
        st.error("请先在侧边栏配置 API Key")
        return

    wf = get_workflow()
    state: WorkflowState = st.session_state.workflow_state or WorkflowState(
        question=question
    )
    state.question = question

    ui = RunUI()
    ui.log(APP_START)
    ui.log(PREPARING)
    st.session_state.is_running = True

    _sync_slots_from_state(state, slots)

    try:
        if mode == "full":
            ui.log("Running full pipeline (4 stages)…")
            try:
                _run_stage1(wf, state, question, ui)
                _flush_stage(state, 1, slots, ui)

                _run_stage2(wf, state, question, ui)
                _flush_stage(state, 2, slots, ui)

                _run_stage3(wf, state, question, ui)
                _flush_stage(state, 3, slots, ui)

                _run_stage4(wf, state, ui)
                _flush_stage(state, 4, slots, ui)

                ui.set_progress(100, text="全部完成")
                ui.log(PIPELINE_DONE)
                ui.status.update(label="✅ 完整流程已完成", state="complete")
            except Exception as e:
                ui.status.update(label="流程中断", state="error")
                ui.log(f"❌ 错误: {e}")
                state.errors.append(str(e))
                st.session_state.workflow_state = state
                _sync_slots_from_state(state, slots)

        elif mode == "stage1":
            _run_stage1(wf, state, question, ui)
            _flush_stage(state, 1, slots, ui)
            ui.set_progress(100, text="Stage 1 完成")
            ui.status.update(label="✅ Stage 1 完成", state="complete")

        elif mode == "stage2":
            if not state.stage1:
                st.error("请先运行 Stage 1")
                return
            _run_stage2(wf, state, question, ui)
            _flush_stage(state, 2, slots, ui)
            ui.set_progress(100, text="Stage 2 完成")
            ui.status.update(label="✅ Stage 2 完成", state="complete")

        elif mode == "stage3":
            if not state.stage1:
                st.error("请先运行 Stage 1")
                return
            _run_stage3(wf, state, question, ui)
            _flush_stage(state, 3, slots, ui)
            ui.set_progress(100, text="Stage 3 完成")
            ui.status.update(label="✅ Stage 3 完成", state="complete")

        elif mode == "stage4":
            if not state.stage1 or not state.stage2 or not state.stage3:
                st.error("请先完成 Stage 1、Stage 2 与 Stage 3")
                return
            _run_stage4(wf, state, ui)
            _flush_stage(state, 4, slots, ui)
            ui.set_progress(100, text="Stage 4 完成")
            ui.status.update(label="✅ Stage 4 完成", state="complete")

    except Exception as e:
        ui.status.update(label="执行失败", state="error")
        ui.log(f"❌ {e}")
        st.session_state.workflow_state = state
        _sync_slots_from_state(state, slots)
        return
    finally:
        st.session_state.is_running = False

    st.session_state.workflow_state = state
    if state.errors:
        for err in state.errors:
            st.warning(err)


def main() -> None:
    st.set_page_config(
        page_title="高考英语应用文 AI 分析",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_css()
    init_session()
    api_ready = render_sidebar()

    st.title("高考英语应用文 AI 分析系统")

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
            disabled=running,
        )
    with col2:
        btn_s1 = st.button("Stage 1", use_container_width=True, disabled=running)
    with col3:
        btn_s2 = st.button("Stage 2", use_container_width=True, disabled=running)
    with col4:
        btn_s3 = st.button("Stage 3", use_container_width=True, disabled=running)
    with col5:
        btn_s4 = st.button("Stage 4", use_container_width=True, disabled=running)

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
    if running or clicked_mode:
        st.caption(
            "实时日志：Analyzing text → Calling API → "
            "每完成一个 Stage 立即在下方对应区域显示，无需等待全部完成。"
        )

    stage_slot1 = st.empty()
    stage_slot2 = st.empty()
    stage_slot3 = st.empty()
    stage_slot4 = st.empty()
    stage_slots = (stage_slot1, stage_slot2, stage_slot3, stage_slot4)

    if clicked_mode:
        run_workflow(clicked_mode, question, stage_slots)
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

    # 导出
    if state.stage1:
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
        try:
            word_bytes = export_workflow_to_word(
                question=state.question,
                stage1_summary=state.stage1.human_summary,
                stage2_raw=state.stage2.raw if state.stage2 else None,
                stage3_raw=state.stage3.raw if state.stage3 else None,
                stage4_raw=state.stage4.raw if state.stage4 else None,
            )
            word_name = _make_export_word_filename(st.session_state.model)
        except Exception as e:
            word_bytes = None
            st.error(f"Word 生成失败: {e}")

        col_json, col_word = st.columns(2)
        with col_json:
            st.download_button(
                "下载 JSON",
                data=json.dumps(export, ensure_ascii=False, indent=2),
                file_name="gaokao_writing_analysis.json",
                mime="application/json",
                use_container_width=True,
            )
        with col_word:
            if word_bytes:
                st.download_button(
                    "一键导出 Word",
                    data=word_bytes,
                    file_name=word_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type="primary",
                    use_container_width=True,
                    help="含题目、四阶段完整内容；标题/表格/列表已排版，便于阅读与打印",
                )


if __name__ == "__main__":
    main()
