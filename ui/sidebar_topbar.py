"""侧栏顶栏：「工作区」与收起按钮同一行。"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


def render_sidebar_workspace_topbar() -> None:
    """主文档内顶栏行 + 脚本将 << 移入该行右侧。"""
    st.markdown(
        '<div class="sidebar-workspace-row">'
        '<span class="sidebar-workspace-title">📂 工作区</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    components.html(
        """
<script>
(function () {
  function doc() {
    try { return window.parent.document; } catch (e) { return document; }
  }
  function dock() {
    const d = doc();
    const row = d.querySelector(".sidebar-workspace-row");
    const btn = d.querySelector('[data-testid="stSidebarCollapseButton"]');
    if (!row || !btn || row.contains(btn)) return;
    row.appendChild(btn);
    btn.style.cssText =
      "position:static!important;top:auto!important;right:auto!important;" +
      "left:auto!important;margin:0 0 0 auto!important;flex-shrink:0;" +
      "transform:none!important;height:auto!important;min-height:0!important;";
  }
  dock();
  setTimeout(dock, 60);
  setTimeout(dock, 250);
  setTimeout(dock, 800);
})();
</script>
        """,
        height=0,
        scrolling=False,
    )
