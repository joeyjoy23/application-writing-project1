"""换题后旧结果灰显（无 Streamlit 依赖的纯判断 + 注入样式）。"""

from __future__ import annotations

import streamlit as st

from workflow import WorkflowState


def question_results_stale(question: str) -> bool:
    """题目已改但本页仍显示上一题生成结果。"""
    last = (st.session_state.get("last_question") or "").strip()
    state = st.session_state.get("workflow_state")
    if not last or not state or not state.stage1:
        return False
    return question.strip() != last


def inject_stale_results_styles() -> None:
    """灰显主区内旧题导出与 Stage 面板（banner 与重跑按钮保持正常）。"""
    st.markdown(
        """
<style>
div[data-testid="stVerticalBlockBorderWrapper"]:has(.stale-results-marker) {
  opacity: 0.46;
  filter: grayscale(0.42);
  transition: opacity 0.2s ease, filter 0.2s ease;
}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.stale-results-marker) {
  border-color: rgb(180 120 40 / 0.45) !important;
  background: rgb(250 246 238 / 0.65) !important;
}
</style>
<span class="stale-results-marker" aria-hidden="true"></span>
        """,
        unsafe_allow_html=True,
    )


def render_stale_results_warning() -> None:
    st.warning(
        "题目已修改，下方为**旧题结果**（已灰显），点击运行后将重新生成。",
        icon="⚠️",
    )
