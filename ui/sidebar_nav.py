"""侧边栏 Stage 1–4 索引：点击锚点跳转到主区对应块。"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from services.workflow_progress import stage_has_content
from workflow import WorkflowState

STAGE_NAV_ITEMS: tuple[tuple[int, str, str], ...] = (
    (1, "Stage 1", "审题"),
    (2, "Stage 2", "PEEL"),
    (3, "Stage 3", "句型词汇"),
    (4, "Stage 4", "教学"),
)


def main_area_shows_stage_panels() -> bool:
    mode = st.session_state.get("app_mode", "新建分析")
    if mode in ("新建", "新建分析"):
        return True
    if mode in ("历史", "查看历史"):
        return st.session_state.get("history_view_id") is not None
    return False


def stage_nav_disabled_hint() -> str:
    """索引不可点击时，副标题文案。"""
    mode = st.session_state.get("app_mode", "新建分析")
    if mode in ("历史", "查看历史") and not st.session_state.get("history_view_id"):
        return "请打开记录"
    return "不可用"


def history_list_nav_hint() -> str | None:
    """历史列表页侧边栏索引下方的说明。"""
    mode = st.session_state.get("app_mode", "新建分析")
    if mode in ("历史", "查看历史") and not st.session_state.get("history_view_id"):
        return "打开某条记录的「只读查看」后，可在此跳转各 Stage"
    return None


def resolve_nav_workflow_state() -> WorkflowState | None:
    """主区正在展示 Stage 面板时，返回用于索引高亮/可点击的状态。"""
    if not main_area_shows_stage_panels():
        return None
    mode = st.session_state.get("app_mode", "新建分析")
    if mode in ("历史", "查看历史"):
        return st.session_state.get("history_nav_state")
    return st.session_state.get("workflow_state")


def inject_stage_nav_scroll_handler() -> None:
    """侧边栏 hash 链无法滚主区时，用 parent.document 平滑滚动到锚点。"""
    components.html(
        """
<script>
(function () {
  function doc() {
    try { return window.parent.document; } catch (e) { return document; }
  }
  function bind() {
    const d = doc();
    d.querySelectorAll('a.stage-nav-link[href^="#stage-panel-"]').forEach(function (a) {
      if (a.dataset.navBound) return;
      a.dataset.navBound = "1";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        const id = (a.getAttribute("href") || "").slice(1);
        if (!id) return;
        const el = d.getElementById(id);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }
  bind();
  setTimeout(bind, 80);
  setTimeout(bind, 350);
})();
</script>
        """,
        height=0,
        scrolling=False,
    )


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
            cls, hint = "stage-nav-item is-disabled", stage_nav_disabled_hint()
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
        '<div class="sidebar-index-block">'
        '<div class="sidebar-section-label sidebar-generated-index-label" role="heading" '
        'aria-level="3">已生成内容索引</div>'
        '<div class="stage-nav-grid">'
        + "".join(items)
        + "</div></div>",
        unsafe_allow_html=True,
    )
    nav_hint = history_list_nav_hint()
    if nav_hint:
        st.caption(nav_hint)
    if panels_visible and any(
        state and stage_has_content(state, num) for num, _, _ in STAGE_NAV_ITEMS
    ):
        inject_stage_nav_scroll_handler()
