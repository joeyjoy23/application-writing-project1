"""侧边栏 Stage 1–4 索引：点击锚点跳转到主区对应块。"""

from __future__ import annotations

import streamlit as st

from services.workflow_progress import stage_has_content
from workflow import WorkflowState

STAGE_NAV_ITEMS: tuple[tuple[int, str, str], ...] = (
    (1, "Stage 1", "审题"),
    (2, "Stage 2", "PEEL"),
    (3, "Stage 3", "句型词汇"),
    (4, "Stage 4", "教学"),
)


def main_area_shows_stage_panels() -> bool:
    mode = st.session_state.get("app_mode", "新建")
    if mode in ("新建", "新建分析"):
        return True
    if mode in ("历史", "查看历史"):
        return st.session_state.get("history_view_id") is not None
    return False


def render_stage_index_nav(
    state: WorkflowState | None, *, running_stages: set[int] | None = None
) -> None:
    """已生成内容索引（紧挨 API 区下方，无 iframe，一屏可见）。"""
    running = running_stages or set()
    panels_visible = main_area_shows_stage_panels()
    items: list[str] = []
    for num, title, subtitle in STAGE_NAV_ITEMS:
        has = bool(state and stage_has_content(state, num))
        is_running = num in running
        if not panels_visible:
            cls, hint = "stage-nav-item is-disabled", "不可用"
        elif is_running:
            cls, hint = "stage-nav-item is-running", "生成中"
        elif has:
            cls, hint = "stage-nav-item is-ready", subtitle
        else:
            cls, hint = "stage-nav-item is-disabled", "暂无"
        if panels_visible and (has or is_running):
            inner = (
                f'<a class="stage-nav-link" href="#stage-panel-{num}" '
                f'target="_self" title="跳转到{title}">'
                f"<span class=\"stage-nav-title\">{title}</span>"
                f'<span class="stage-nav-sub">{hint}</span></a>'
            )
        else:
            inner = (
                f'<span class="stage-nav-link stage-nav-link-disabled">'
                f"<span class=\"stage-nav-title\">{title}</span>"
                f'<span class="stage-nav-sub">{hint}</span></span>'
            )
        items.append(f'<div class="{cls}">{inner}</div>')

    st.markdown(
        '<p class="sidebar-section-label sidebar-generated-index-label">已生成内容索引</p>'
        '<div class="stage-nav-grid">'
        + "".join(items)
        + "</div>",
        unsafe_allow_html=True,
    )
