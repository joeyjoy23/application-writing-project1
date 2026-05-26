"""新建分析页 + 历史页 + Stage 渲染 + 导出按钮 + 断点续传辅助。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

import streamlit as st

from db import (
    count_records,
    delete_record,
    ensure_guest_id,
    format_stages_mask,
    get_all_records,
    get_record_by_id,
    history_scope,
    upsert_record,
    using_postgres,
)
from utils.config import PROVIDER_OPTIONS, resolve_api_key
from utils.export_word import export_workflow_to_word
from utils.image_ocr import extract_question_from_image_with_ui_settings
from workflow import (
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    WorkflowState,
)

from ui.sidebar import api_key_configured, clear_checkpoint, stage_has_content
from ui.run_manager import (
    advance_run_job,
    try_start_run_job,
)


# ── 序列化 / 反序列化 ──


def make_export_word_filename(model: str, date_str: str | None = None) -> str:
    """Word 导出文件名：应用文分析_YYYY-MM-DD_模型名.docx"""
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    else:
        date_str = date_str.strip()[:10]
    safe_model = re.sub(r'[<>:"/\\|?*]', "-", (model or "").strip()) or "model"
    return f"应用文分析_{date_str}_{safe_model}.docx"


def workflow_state_to_json(
    state: WorkflowState,
    *,
    provider: str | None = None,
    model: str | None = None,
    raw_input: str | None = None,
) -> str:
    """将备课包序列化为 JSON 字符串存入数据库。"""
    raw = (raw_input if raw_input is not None else state.question or "").strip()
    payload = {
        "raw_input": raw,
        "question": raw,
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


def resolve_raw_input(record: dict[str, Any], data: dict[str, Any] | None = None) -> str:
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
        for key in ("original_text", "sentence1", "sentence2", "prompt_text", "full_prompt"):
            val = s1.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
        if parts:
            return "\n\n".join(parts)
    return (record.get("topic") or "").strip()


def workflow_state_from_json(content: str, *, raw_input: str | None = None) -> WorkflowState:
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


def _workflow_content_length(state: WorkflowState) -> int:
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


def auto_save_history(
    state: WorkflowState,
    *,
    provider: str | None = None,
    model: str | None = None,
    raw_input: str | None = None,
    notify: bool = True,
    notify_updates: bool = False,
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
        content = workflow_state_to_json(
            state, provider=provider, model=model, raw_input=raw
        )
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if st.session_state.get("_last_save_fingerprint") == fingerprint:
            return None
        actual_model = model or st.session_state.model
        record_id, is_new = upsert_record(
            raw or state.question,
            actual_model,
            content,
            raw_input=raw,
            word_count=_workflow_content_length(state),
            stages_mask=_workflow_stages_mask(state),
        )
        st.session_state._last_save_fingerprint = fingerprint
        if notify:
            if is_new:
                st.toast(
                    f"已保存到历史（#{record_id}，模型：{actual_model}）",
                    icon="💾",
                )
            elif notify_updates:
                st.toast(
                    f"历史已更新（#{record_id}，同题同模型已合并）",
                    icon="💾",
                )
        return record_id
    except Exception as e:
        if notify:
            st.toast(f"历史保存失败：{e}", icon="⚠️")
        return None


# ── 历史载入 ──


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
    st.session_state.run_job = None
    st.session_state.is_running = False
    st.session_state.run_cancelled = False
    st.session_state._last_save_fingerprint = None
    st.session_state._confirm_clear = False
    st.session_state.history_view_id = None
    st.session_state.app_mode = "新建"

    saved_provider = data.get("provider")
    saved_model = (data.get("model") or "").strip()
    if saved_provider in PROVIDER_OPTIONS:
        st.session_state["_pending_provider"] = saved_provider
    if saved_model:
        st.session_state["_pending_model"] = saved_model

    return True, ""


def _history_resume_hint(state: WorkflowState) -> str:
    nxt = get_next_stage(state)
    if nxt is None:
        return "四阶段已全部完成，可在新建页查看、导出或清空后重跑。"
    done = sum(1 for s in range(1, 5) if stage_has_content(state, s))
    return f"已载入断点（{done}/4），切换到「新建」后点击「{resume_label(nxt).replace('▶ ', '')}」即可续跑。"


# ── 断点续传辅助 ──


def get_next_stage(state: WorkflowState) -> int | None:
    """推断下一个待运行的 Stage（1-4），全完成返回 None。"""
    if not state.stage1:
        return 1
    if not state.stage2:
        return 2
    if not state.stage3:
        return 3
    if not state.stage4:
        return 4
    return None


def maybe_clear_checkpoint_if_question_changed(question: str) -> None:
    """仅在即将开始新的生成时检测题目是否变更。"""
    cached_question = st.session_state.last_question
    cached_state = st.session_state.workflow_state
    if not cached_question or not cached_state or not cached_state.stage1:
        return
    if question.strip() != cached_question.strip():
        clear_checkpoint()
        st.toast("题目已变更，已清除上次缓存", icon="🔄")


def resume_label(next_stage: int | None) -> str:
    """根据下一步 Stage 生成用户友好的按钮文案。"""
    if next_stage is None:
        return "✅ 全部已完成"
    labels = {
        1: "▶ 继续生成（从 Stage 1 开始）",
        2: "▶ 继续生成（从 Stage 2 开始）",
        3: "▶ 继续生成（从 Stage 3 开始）",
        4: "▶ 继续生成（从 Stage 4 开始）",
    }
    return labels.get(next_stage, "继续生成")


# ── 长文本展示 ──

FOLD_CHAR_THRESHOLD = 5000
FOLD_PREVIEW_CHARS = 1000


def render_foldable_markdown(text: str) -> None:
    """超过阈值时折叠：外侧预览 + expander 内全文。"""
    if not text or not text.strip():
        return
    if len(text) <= FOLD_CHAR_THRESHOLD:
        st.markdown(text)
        return
    st.markdown(text[:FOLD_PREVIEW_CHARS])
    st.caption(f"共 {len(text)} 字，点击展开查看完整内容")
    with st.expander("查看完整内容", expanded=False):
        st.markdown(text)


# ── Stage 渲染 ──


def render_stage1(state: WorkflowState) -> None:
    st.markdown('<span class="stage-badge stage-1">Stage 1</span> 审题结构分析', unsafe_allow_html=True)
    if not state.stage1:
        st.info("尚未运行 Stage 1")
        return
    s1 = state.stage1
    if s1.human_summary.strip():
        render_foldable_markdown(s1.human_summary)
    else:
        st.info("暂无审题总结内容")


def render_stage2(state: WorkflowState) -> None:
    st.markdown('<span class="stage-badge stage-2">Stage 2</span> PEEL 写作策略卡与多版范文', unsafe_allow_html=True)
    if not state.stage2:
        st.info("尚未运行 Stage 2（需先完成 Stage 1）")
        return
    render_foldable_markdown(state.stage2.raw)


def render_stage3(state: WorkflowState) -> None:
    st.markdown(
        '<span class="stage-badge stage-3">Stage 3</span> 功能句型包与话题词汇',
        unsafe_allow_html=True,
    )
    if not state.stage3:
        st.info("尚未运行 Stage 3（需先完成 Stage 1）")
        return
    render_foldable_markdown(state.stage3.raw)


def render_stage4(state: WorkflowState) -> None:
    st.markdown(
        '<span class="stage-badge stage-4">Stage 4</span> 教学指南与易错预警',
        unsafe_allow_html=True,
    )
    if not state.stage4:
        st.info("尚未运行 Stage 4（需先完成 Stage 2 与 Stage 3）")
        return
    render_foldable_markdown(state.stage4.raw)


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

_STAGE_BADGE_TITLES = {
    1: '<span class="stage-badge stage-1">Stage 1</span> 审题结构分析',
    2: '<span class="stage-badge stage-2">Stage 2</span> PEEL 写作策略卡与多版范文',
    3: '<span class="stage-badge stage-3">Stage 3</span> 功能句型包与话题词汇',
    4: '<span class="stage-badge stage-4">Stage 4</span> 教学指南与易错预警',
}


def render_one_stage(slot: st.empty, state: WorkflowState, stage_num: int) -> None:
    """仅更新单个 Stage 占位。"""
    with slot.container():
        _STAGE_RENDERERS[stage_num](state)


def render_stage_placeholder(slot: st.empty, stage_num: int) -> None:
    with slot.container():
        st.markdown(_STAGE_BADGE_TITLES[stage_num], unsafe_allow_html=True)
        st.info(_STAGE_WAITING[stage_num])


def sync_slots_from_state(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    """按当前状态刷新各占位。"""
    for n, slot in enumerate(slots, start=1):
        if stage_has_content(state, n):
            render_one_stage(slot, state, n)
        else:
            render_stage_placeholder(slot, n)


def render_all_stages(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    """页面加载时展示各阶段。"""
    sync_slots_from_state(state, slots)


# ── 导出按钮 ──


def render_export_buttons(
    state: WorkflowState,
    *,
    model_name: str | None = None,
    created_at: str | None = None,
    key_prefix: str = "export",
) -> None:
    """导出 JSON / Word（新建页与历史详情共用）。"""
    if not state.stage1:
        return
    st.markdown(
        '<div class="export-section">'
        '<div class="export-section-title">'
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">'
        '<path d="M2 4v9a1 1 0 001 1h10a1 1 0 001-1V4"/>'
        '<path d="M1 4h14"/><path d="M5 1h6v3H5z"/>'
        '</svg>导出报告</div>',
        unsafe_allow_html=True,
    )
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
        word_name = make_export_word_filename(model, created_at)
    except Exception as e:
        word_bytes = None
        st.error(f"Word 生成失败: {e}")

    if key_prefix.startswith("hist_"):
        key_base = key_prefix
    else:
        key_base = (
            f"{key_prefix}_"
            f"{hashlib.sha256(json.dumps(export, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}"
        )

    col_word, col_json = st.columns([3, 2])
    with col_word:
        if word_bytes:
            word_label = "📥 导出 Word" if key_prefix.startswith("hist_") else "📥 一键导出 Word"
            st.download_button(
                word_label,
                data=word_bytes,
                file_name=word_name,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
                use_container_width=True,
                help="含题目、四阶段完整内容；标题/表格/列表已排版，便于阅读与打印",
                key=f"{key_base}_word",
            )
    with col_json:
        st.download_button(
            "📋 下载 JSON",
            data=json.dumps(export, ensure_ascii=False, indent=2),
            file_name="gaokao_writing_analysis.json",
            mime="application/json",
            use_container_width=True,
            key=f"{key_base}_json",
        )
    st.markdown("</div>", unsafe_allow_html=True)


# ── 历史页 ──


HISTORY_PAGE_SIZE = 20


def render_history_list() -> None:
    """历史列表：搜索、表格、查看/删除、分页。"""
    ensure_guest_id()
    owner_id, admin = history_scope()
    st.subheader("📚 历史备课包")
    if using_postgres() and not admin:
        st.caption("云端保存；换浏览器或清缓存后仅能看到本机新记录")
    st.caption(
        "每完成一个 Stage 会自动写入历史（同题同模型合并为一条）；"
        "失败或停止后也可在「历史」中载入续跑。"
    )
    keyword = st.text_input(
        "搜索题目",
        value=st.session_state.history_search_keyword,
        placeholder="输入关键词模糊匹配题目摘要…",
        key="history_search_input",
    )
    prev_keyword = st.session_state.get("_history_search_applied", "")
    if keyword != prev_keyword:
        st.session_state.history_page = 1
        st.session_state._history_search_applied = keyword
    st.session_state.history_search_keyword = keyword

    page_size = int(st.session_state.get("history_page_size") or HISTORY_PAGE_SIZE)
    total = count_records(keyword or "", owner_id, admin)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = int(st.session_state.get("history_page") or 1)
    page = max(1, min(page, total_pages))
    st.session_state.history_page = page

    offset = (page - 1) * page_size
    records = get_all_records(
        keyword or "", owner_id, admin, limit=page_size, offset=offset
    )

    if not records and total == 0:
        st.info("暂无历史记录，请在「新建」模式中生成备课包。")
        return

    st.caption(
        f"共 {total} 条 · 第 {page}/{total_pages} 页（每页 {page_size} 条，支持按题目或模型搜索）"
    )

    header = st.columns([2, 3, 2, 2, 1, 2, 1])
    header[0].markdown("**生成时间**")
    header[1].markdown("**题目摘要**")
    header[2].markdown("**模型**")
    header[3].markdown("**阶段**")
    header[4].markdown("**字数**")
    header[5].markdown("**操作**")
    header[6].markdown("")

    for rec in records:
        rid = rec["id"]
        cols = st.columns([2, 3, 2, 2, 1, 2, 1])
        cols[0].write(rec["created_at"])
        topic_show = rec["topic"]
        if len(topic_show) > 50:
            topic_show = topic_show[:50] + "…"
        cols[1].write(topic_show)
        cols[2].write(rec["model_name"])
        cols[3].caption(format_stages_mask(rec.get("stages_mask")))
        cols[4].write(rec.get("word_count", "—"))
        act_view, act_load = cols[5].columns(2)
        if act_view.button("查看", key=f"hist_view_{rid}", use_container_width=True):
            st.session_state.history_view_id = rid
            st.session_state.history_confirm_delete_id = None
            st.rerun()
        if act_load.button("载入", key=f"hist_load_{rid}", use_container_width=True):
            ok, err = load_history_into_session(rid)
            if ok:
                st.toast(_history_resume_hint(st.session_state.workflow_state), icon="📂")
                st.rerun()
            else:
                st.error(err)
        if cols[6].button("删", key=f"hist_del_{rid}", use_container_width=True):
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

    nav_prev, nav_info, nav_next = st.columns([1, 2, 1])
    with nav_prev:
        if st.button(
            "上一页",
            use_container_width=True,
            disabled=page <= 1,
            key="history_page_prev",
        ):
            st.session_state.history_page = page - 1
            st.rerun()
    with nav_info:
        st.markdown(
            f"<div style='text-align:center;padding:0.4rem 0'>第 **{page}** / **{total_pages}** 页</div>",
            unsafe_allow_html=True,
        )
    with nav_next:
        if st.button(
            "下一页",
            use_container_width=True,
            disabled=page >= total_pages,
            key="history_page_next",
        ):
            st.session_state.history_page = page + 1
            st.rerun()


def render_history_detail(record_id: int) -> None:
    """历史详情：完整备课包 + 导出 Word + 载入续跑 + 返回列表。"""
    ensure_guest_id()
    record = get_record_by_id(record_id)
    if not record:
        st.error("记录不存在或已被删除")
        if st.button("返回列表"):
            st.session_state.history_view_id = None
            st.rerun()
        return

    try:
        data = json.loads(record["full_content"])
    except json.JSONDecodeError:
        st.error("记录内容损坏，无法解析")
        if st.button("返回列表", key="hist_bad_back"):
            st.session_state.history_view_id = None
            st.rerun()
        return

    raw = resolve_raw_input(record, data)
    state = workflow_state_from_json(record["full_content"], raw_input=raw)
    next_stage = get_next_stage(state)

    col_back, col_load, col_meta = st.columns([1, 1, 3])
    with col_back:
        if st.button("← 返回列表", use_container_width=True):
            st.session_state.history_view_id = None
            st.rerun()
    with col_load:
        load_label = "📂 载入继续编辑" if next_stage else "📂 载入到新建页"
        if st.button(load_label, type="primary", use_container_width=True, key=f"hist_load_detail_{record_id}"):
            ok, err = load_history_into_session(record_id)
            if ok:
                st.toast(_history_resume_hint(st.session_state.workflow_state), icon="📂")
                st.rerun()
            else:
                st.error(err)
    with col_meta:
        st.caption(
            f"生成时间：{record['created_at']} · 模型：{record['model_name']} · "
            f"阶段：{format_stages_mask(record.get('stages_mask'))} · "
            f"约 {record.get('word_count', 0)} 字"
        )
        if next_stage:
            st.caption(f"未完成：可从 Stage {next_stage} 续跑（载入后切到「新建」模式）")

    st.markdown("#### 原始题目")
    st.text_area(
        "完整题目（存档原文）",
        value=raw,
        height=min(220, max(120, len(raw) // 4)),
        disabled=True,
        label_visibility="collapsed",
        key=f"hist_raw_{record_id}",
    )

    st.divider()
    st.subheader("备课包内容")
    slot1, slot2, slot3, slot4 = st.empty(), st.empty(), st.empty(), st.empty()
    render_all_stages(state, (slot1, slot2, slot3, slot4))

    render_export_buttons(
        state,
        model_name=record["model_name"],
        created_at=record["created_at"],
        key_prefix=f"hist_{record_id}",
    )


def render_history_page() -> None:
    """查看历史模式主界面。"""
    ensure_guest_id()
    view_id = st.session_state.history_view_id
    if view_id is not None:
        render_history_detail(view_id)
    else:
        render_history_list()


# ── 新建分析页 ──


def render_new_analysis(api_ready: bool) -> None:
    """新建分析模式：输入题目与运行流程。"""
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
            # 上传状态反馈
            _recognized = bool(st.session_state.uploaded_image_name)
            if _recognized and st.session_state.uploaded_image_name == uploaded.name:
                st.markdown(
                    '<span class="upload-status upload-status--recognized">'
                    '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm3.22 5.97l-4 4a.75.75 0 01-1.06 0l-2-2a.75.75 0 111.06-1.06L6.72 8.94l3.47-3.47a.75.75 0 111.06 1.06z"/></svg>'
                    f'已识别：{uploaded.name}</span>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<span class="upload-status upload-status--ready">'
                    '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 1a7 7 0 100 14A7 7 0 008 1zm0 3a.75.75 0 01.75.75v2.5h2.5a.75.75 0 010 1.5h-2.5v2.5a.75.75 0 01-1.5 0v-2.5h-2.5a.75.75 0 010-1.5h2.5v-2.5A.75.75 0 018 4z"/></svg>'
                    f'已上传：{uploaded.name}，点击下方按钮识别</span>',
                    unsafe_allow_html=True,
                )
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

    # ── 按钮区 ──
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

    # 清空结果：空行间隔 + 低视觉权重
    st.write("")
    _clear_col1, _clear_col2 = st.columns([1, 8])
    with _clear_col1:
        if st.button(
            "🗑 清空结果",
            key="btn_clear_results",
            help="清除当前所有阶段的生成结果",
        ):
            st.session_state._confirm_clear = True
            st.rerun()
    with _clear_col2:
        pass

    # 清空确认弹层
    if st.session_state.get("_confirm_clear"):
        st.warning("⚠️ 确认清空所有生成结果？此操作不可撤销。")
        _cc1, _cc2 = st.columns([1, 3])
        with _cc1:
            if st.button("确认清空", type="primary", key="btn_confirm_clear"):
                clear_checkpoint()
                st.rerun()
        with _cc2:
            if st.button("取消", key="btn_cancel_clear"):
                st.session_state._confirm_clear = False
                st.rerun()

    if not question.strip():
        st.warning("请先输入题目，或在「图片识题」中上传真题并点击「识别题目文字」")
        return

    if not api_ready:
        st.info("请先在左侧边栏选择 API 提供商并填写 Key")
        return

    # ── 断点续传 ──
    _cached = st.session_state.workflow_state
    _next_stage = get_next_stage(_cached) if _cached and _cached.stage1 else None
    _failed = st.session_state.failed_stage

    if _next_stage is not None and not running and not st.session_state.run_job:
        _resume_col1, _resume_col2 = st.columns([1, 2])
        with _resume_col1:
            if st.button(
                resume_label(_next_stage),
                type="primary",
                use_container_width=True,
                key="btn_resume",
            ):
                maybe_clear_checkpoint_if_question_changed(question)
                if try_start_run_job("resume", question):
                    st.rerun()
        with _resume_col2:
            _done = sum(1 for s in range(1, 5) if stage_has_content(_cached, s))
            st.caption(f"已完成 {_done}/4 个阶段，点击可从 Stage {_next_stage} 继续生成")

    if _failed is not None and not running and not st.session_state.run_job:
        _retry_col1, _retry_col2 = st.columns([1, 2])
        with _retry_col1:
            if st.button(
                f"🔄 重试 Stage {_failed}",
                type="secondary",
                use_container_width=True,
                key="btn_retry_failed",
            ):
                maybe_clear_checkpoint_if_question_changed(question)
                _mode_map = {1: "stage1", 2: "stage2", 3: "stage3", 4: "stage4"}
                if try_start_run_job(_mode_map.get(_failed, "full"), question):
                    st.rerun()
        with _retry_col2:
            st.caption(f"Stage {_failed} 上次生成失败，点击可重新尝试")

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

    # 导出按钮提前显示
    _early_state = st.session_state.workflow_state
    if _early_state and _early_state.stage1:
        render_export_buttons(_early_state)

    stage_slot1 = st.empty()
    stage_slot2 = st.empty()
    stage_slot3 = st.empty()
    stage_slot4 = st.empty()
    stage_slots = (stage_slot1, stage_slot2, stage_slot3, stage_slot4)

    if st.session_state.run_job:
        advance_run_job(question, stage_slots)
    elif clicked_mode:
        maybe_clear_checkpoint_if_question_changed(question)
        if try_start_run_job(clicked_mode, question):
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
