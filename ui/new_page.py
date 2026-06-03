"""新建分析页 + 历史页 + 导出按钮。"""

from __future__ import annotations

import hashlib
import json
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
    toggle_star,
    using_postgres,
)
from services.workflow_progress import (
    get_next_stage,
    resume_label,
    stage_has_content,
)
from utils.datetime_util import format_created_at_display
from services.workflow_storage import (
    make_export_word_filename,
    resolve_raw_input,
    workflow_state_from_json,
)
from utils.config import resolve_api_key
from utils.export_word import export_workflow_to_word
from workflow import WorkflowState

from ui.history import auto_save_history, history_resume_hint, load_history_into_session
from ui.run_manager import advance_run_job, try_start_run_job
from ui.sidebar import api_key_configured, clear_checkpoint
from ui.share_controls import ensure_history_record_id, render_share_controls
from ui.stage_display import render_all_stages, sync_slots_from_state


def maybe_clear_checkpoint_if_question_changed(question: str) -> None:
    """仅在即将开始新的生成时检测题目是否变更。"""
    cached_question = st.session_state.last_question
    cached_state = st.session_state.workflow_state
    if not cached_question or not cached_state or not cached_state.stage1:
        return
    if question.strip() != cached_question.strip():
        clear_checkpoint()
        st.toast("题目已变更，已清除上次缓存", icon="🔄")


# ── 导出按钮 ──

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
            saved_at_utc=created_at,
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
    st.markdown('<p class="section-label">历史备课包</p>', unsafe_allow_html=True)
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

    # 收藏筛选
    starred_only = st.checkbox("只看收藏", key="history_starred_only", value=False)
    
    page_size = int(st.session_state.get("history_page_size") or HISTORY_PAGE_SIZE)
    total = count_records(keyword or "", owner_id, admin)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = int(st.session_state.get("history_page") or 1)
    page = max(1, min(page, total_pages))
    st.session_state.history_page = page

    offset = (page - 1) * page_size
    # 需要修改 get_all_records 支持 starred_only 参数
    # 暂时先获取全部，前端筛选
    all_records = get_all_records(
        keyword or "", owner_id, admin, limit=page_size, offset=offset
    )
    if starred_only:
        records = [r for r in all_records if r.get("is_starred")]
        if not records and all_records:
            st.info("当前筛选条件下无收藏记录")
            return
    else:
        records = all_records

    if not records and total == 0:
        st.info("暂无历史记录，请在「新建」模式中生成备课包。")
        return

    st.caption(
        f"共 {total} 条 · 第 {page}/{total_pages} 页（每页 {page_size} 条，支持按题目或模型搜索）"
    )

    header = st.columns([2, 3, 2, 2, 1, 2, 0.5, 0.5])
    header[0].markdown("**生成时间**")
    header[1].markdown("**题目摘要**")
    header[2].markdown("**模型**")
    header[3].markdown("**阶段**")
    header[4].markdown("**字数**")
    header[5].markdown("**操作**")
    header[6].markdown("**收藏**")
    header[7].markdown("**删除**")

    for rec in records:
        rid = rec["id"]
        cols = st.columns([2, 3, 2, 2, 1, 2, 0.5, 0.5])
        cols[0].write(format_created_at_display(rec["created_at"]))
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
                st.toast(history_resume_hint(st.session_state.workflow_state), icon="📂")
                st.rerun()
            else:
                st.error(err)
        # 收藏切换按钮
        is_starred = rec.get("is_starred", 0)
        star_label = "⭐" if is_starred else "☆"
        if cols[6].button(
            star_label,
            key=f"hist_star_{rid}",
            use_container_width=True,
            help="点击切换收藏状态",
        ):
            toggle_star(rid, not is_starred, owner_id=owner_id, admin=admin)
            st.rerun()
        if cols[7].button("🗑", key=f"hist_del_{rid}", use_container_width=True):
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
                st.toast(history_resume_hint(st.session_state.workflow_state), icon="📂")
                st.rerun()
            else:
                st.error(err)
    with col_meta:
        st.caption(
            f"生成时间：{format_created_at_display(record['created_at'])}（北京时间） · "
            f"模型：{record['model_name']} · "
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
    st.markdown('<p class="section-label">备课包内容</p>', unsafe_allow_html=True)
    slot1, slot2, slot3, slot4 = st.empty(), st.empty(), st.empty(), st.empty()
    render_all_stages(state, (slot1, slot2, slot3, slot4))

    render_export_buttons(
        state,
        model_name=record["model_name"],
        created_at=record["created_at"],
        key_prefix=f"hist_{record_id}",
    )
    render_share_controls(record_id, key_prefix=f"hist_share_{record_id}")


def render_history_page() -> None:
    """查看历史模式主界面。"""
    ensure_guest_id()
    view_id = st.session_state.history_view_id
    if view_id is not None:
        render_history_detail(view_id)
    else:
        render_history_list()


# ── 新建分析页 ──

# 运行方式区：第一行 4 等分 Stage；第二行 2 等分（完整流程 | 清空），与上行左右对齐
_RUN_STAGE_COLS = 4
_RUN_ACTION_COLS = 2


def render_new_analysis(api_ready: bool) -> None:
    """新建分析模式：输入题目与运行流程。"""
    st.markdown('<p class="section-label">题目输入</p>', unsafe_allow_html=True)

    question = st.text_area(
        "题目内容",
        value=st.session_state.question,
        height=140,
        placeholder="例如：假定你是李华，校英文报正在开展…请写一封建议信…",
        key="question_editor",
        label_visibility="collapsed",
    )
    st.session_state.question = question

    # 快捷难度切换按钮
    st.markdown(
        '<p class="section-label">学生水平'
        '<span class="section-hint"> · 仅影响 Stage 4</span></p>',
        unsafe_allow_html=True,
    )
    _current = st.session_state.get("student_level", "中等")
    col_level1, col_level2, col_level3 = st.columns(3)
    with col_level1:
        if st.button(
            "● 基础" if _current == "基础" else "○ 基础",
            type="primary" if _current == "基础" else "secondary",
            use_container_width=True,
        ):
            st.session_state.student_level = "基础"
    with col_level2:
        if st.button(
            "● 中等" if _current == "中等" else "○ 中等",
            type="primary" if _current == "中等" else "secondary",
            use_container_width=True,
        ):
            st.session_state.student_level = "中等"
    with col_level3:
        if st.button(
            "● 进阶" if _current == "进阶" else "○ 进阶",
            type="primary" if _current == "进阶" else "secondary",
            use_container_width=True,
        ):
            st.session_state.student_level = "进阶"

    running = st.session_state.is_running

    # ── 按钮区：两行共用 4 列 CSS Grid 对齐（见 custom.css） ──
    st.markdown('<p class="section-label">运行方式</p>', unsafe_allow_html=True)
    st.markdown('<span class="run-mode-grid-start" aria-hidden="true"></span>', unsafe_allow_html=True)
    _s1, _s2, _s3, _s4 = st.columns(_RUN_STAGE_COLS)
    with _s1:
        btn_s1 = st.button(
            "Stage 1",
            use_container_width=True,
            help="审题与结构分析：体裁、时态、人称、要点分级、结构规划",
        )
    with _s2:
        btn_s2 = st.button(
            "Stage 2",
            use_container_width=True,
            help="PEEL 写作策略卡与多版范文生成",
        )
    with _s3:
        btn_s3 = st.button(
            "Stage 3",
            use_container_width=True,
            help="功能句型包与话题词汇整理",
        )
    with _s4:
        btn_s4 = st.button(
            "Stage 4",
            use_container_width=True,
            help="教学指南与易错预警（受学生水平影响）",
        )

    _f1, _f2 = st.columns(_RUN_ACTION_COLS)
    with _f1:
        btn_full = st.button(
            "完整流程",
            type="primary",
            use_container_width=True,
            help="依次运行 Stage 1→2→3→4，已完成的阶段自动跳过",
        )
    with _f2:
        if st.button(
            "清空结果",
            key="btn_clear_results",
            help="清除当前所有阶段的生成结果（保留题目与学生水平）",
            use_container_width=True,
        ):
            st.session_state._confirm_clear = True
            st.rerun()

    # 清空确认
    if st.session_state.get("_confirm_clear"):
        st.markdown(
            '<div class="clear-confirm-box">'
            '<p class="clear-confirm-title">确认清空生成结果？</p>'
            '<p class="clear-confirm-desc">将清除 Stage 1–4 的全部输出，题目与学生水平设置保留。此操作不可撤销。</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        _cc1, _cc2, _, _ = st.columns(_RUN_STAGE_COLS)
        with _cc1:
            if st.button("确认清空", type="primary", key="btn_confirm_clear", use_container_width=True):
                clear_checkpoint()
                st.rerun()
        with _cc2:
            if st.button("取消", key="btn_cancel_clear", use_container_width=True):
                st.session_state._confirm_clear = False
                st.rerun()

    if not question.strip():
        st.warning("请先输入题目内容")
        return

    if not api_ready:
        st.info("请先在左侧边栏选择 API 提供商并填写 Key")
        return

    # ── 断点续传 ──
    _cached = st.session_state.workflow_state
    _next_stage = get_next_stage(_cached) if _cached and _cached.stage1 else None
    _failed = st.session_state.failed_stage

    if _next_stage is not None and not running and not st.session_state.run_job:
        _r1, _r2 = st.columns(_RUN_ACTION_COLS)
        with _r1:
            if st.button(
                resume_label(_next_stage),
                type="primary",
                use_container_width=True,
                key="btn_resume",
            ):
                maybe_clear_checkpoint_if_question_changed(question)
                if try_start_run_job("resume", question):
                    st.rerun()
        with _r2:
            _done = sum(1 for s in range(1, 5) if stage_has_content(_cached, s))
            st.caption(f"已完成 {_done}/4 个阶段，点击可从 Stage {_next_stage} 继续生成")

    if _failed is not None and not running and not st.session_state.run_job:
        _t1, _t2 = st.columns(_RUN_ACTION_COLS)
        with _t1:
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
        with _t2:
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
    st.markdown('<p class="section-label">运行与结果</p>', unsafe_allow_html=True)
    if running or clicked_mode or st.session_state.run_job:
        st.caption(
            "运行中可在侧边栏切换模型以**自动停止**当前请求；"
            "停止后请重新点击 Stage。生成内容会逐块显示在下方。"
        )

    # 导出按钮提前显示
    _early_state = st.session_state.workflow_state
    if _early_state and _early_state.stage1:
        render_export_buttons(_early_state)
        _hist_id = ensure_history_record_id(_early_state)
        render_share_controls(_hist_id, key_prefix="new_share")

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

    # 单独重跑已完成的 Stage
    if not running and not st.session_state.run_job:
        _ws = st.session_state.workflow_state
        if _ws and _ws.stage1:
            st.divider()
            st.caption("单独重跑某个 Stage（不影响其他已完成阶段）：")
            _rr1, _rr2, _rr3, _rr4 = st.columns(_RUN_STAGE_COLS)
            _rerun_cols = (_rr1, _rr2, _rr3, _rr4)
            _stage_names = {1: "Stage 1 审题", 2: "Stage 2 PEEL", 3: "Stage 3 句型词汇", 4: "Stage 4 教学指南"}
            for _sn in range(1, 5):
                with _rerun_cols[_sn - 1]:
                    if stage_has_content(_ws, _sn):
                        if st.button(
                            f"🔄 {_stage_names[_sn]}",
                            key=f"rerun_stage_{_sn}",
                            use_container_width=True,
                        ):
                            st.session_state._rerun_stage_mode = f"stage{_sn}"
                            st.rerun()
            if st.session_state.get("_rerun_stage_mode"):
                _mode = st.session_state.pop("_rerun_stage_mode")
                maybe_clear_checkpoint_if_question_changed(question)
                if try_start_run_job(_mode, question):
                    st.rerun()

    state = st.session_state.workflow_state
    if not state:
        return

    if state.errors:
        for err in state.errors:
            st.error(err)
