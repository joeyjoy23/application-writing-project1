"""侧边栏 Stage 1–4 索引：点击滚动到主区对应块。"""

from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components

from services.workflow_progress import stage_has_content
from workflow import WorkflowState

STAGE_NAV_ITEMS: tuple[tuple[int, str, str], ...] = (
    (1, "Stage 1", "审题结构分析"),
    (2, "Stage 2", "PEEL 与范文"),
    (3, "Stage 3", "句型与词汇"),
    (4, "Stage 4", "教学指南"),
)


def main_area_shows_stage_panels() -> bool:
    """主区是否正在展示四阶段占位（新建页或历史详情）。"""
    mode = st.session_state.get("app_mode", "新建")
    if mode in ("新建", "新建分析"):
        return True
    if mode in ("历史", "查看历史"):
        return st.session_state.get("history_view_id") is not None
    return False


def _nav_button_states(
    state: WorkflowState | None, *, running: set[int]
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for num, title, subtitle in STAGE_NAV_ITEMS:
        has = bool(state and stage_has_content(state, num))
        is_running = num in running
        if is_running:
            status, clickable = "running", True
        elif has:
            status, clickable = "done", True
        else:
            status, clickable = "idle", False
        rows.append(
            {
                "num": num,
                "title": title,
                "subtitle": subtitle,
                "status": status,
                "clickable": clickable,
            }
        )
    return rows


def render_stage_index_nav(
    state: WorkflowState | None, *, running_stages: set[int] | None = None
) -> None:
    """渲染可点击的 Stage 目录（主区无阶段块时整组禁用）。"""
    running = running_stages or set()
    panels_visible = main_area_shows_stage_panels()
    rows = _nav_button_states(state, running=running)
    if not panels_visible:
        for row in rows:
            row["clickable"] = False

    st.markdown('<p class="sidebar-section-label">内容索引</p>', unsafe_allow_html=True)
    payload = json.dumps(rows, ensure_ascii=False)
    components.html(
        f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0;
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: transparent;
  }}
  .nav-list {{
    display: flex;
    flex-direction: column;
    gap: 0.28rem;
    padding: 0 0 0.1rem;
  }}
  .nav-btn {{
    width: 100%;
    text-align: left;
    border: 1px solid #e8e4df;
    border-radius: 8px;
    background: #fefdfb;
    padding: 0.32rem 0.5rem 0.34rem;
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }}
  .nav-btn:hover:not(:disabled) {{
    border-color: #9a8fa8;
    background: #f3f0ec;
  }}
  .nav-btn:disabled {{
    opacity: 0.42;
    cursor: not-allowed;
    background: #f8f6f3;
  }}
  .nav-btn.running {{
    border-color: #c4b8a8;
    background: #faf6f0;
  }}
  .nav-btn.done .nav-title {{
    color: #3a3540;
  }}
  .nav-title {{
    font-size: 0.82rem;
    font-weight: 600;
    color: #5c5668;
    line-height: 1.25;
  }}
  .nav-sub {{
    font-size: 0.72rem;
    color: #8a8494;
    line-height: 1.2;
    margin-top: 0.1rem;
  }}
  .nav-hint {{
    font-size: 0.7rem;
    color: #8a8494;
    margin: 0 0 0.2rem;
    line-height: 1.35;
  }}
</style>
</head>
<body>
  <p class="nav-hint">点击跳转到主区对应 Stage</p>
  <div class="nav-list" id="list"></div>
  <script>
  (function () {{
    const rows = {payload};
    const list = document.getElementById("list");
    function parentDoc() {{
      try {{ return window.parent.document; }} catch (e) {{ return document; }}
    }}
    function scrollToStage(n) {{
      const doc = parentDoc();
      const el = doc.getElementById("stage-panel-" + n);
      if (!el) return;
      const main =
        doc.querySelector('[data-testid="stAppViewContainer"] section.main') ||
        doc.querySelector("section.main");
      if (main) {{
        const top =
          el.getBoundingClientRect().top -
          main.getBoundingClientRect().top +
          main.scrollTop -
          12;
        main.scrollTo({{ top: Math.max(0, top), behavior: "smooth" }});
      }} else {{
        el.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}
    }}
    rows.forEach((row) => {{
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "nav-btn " + row.status;
      btn.disabled = !row.clickable;
      btn.innerHTML =
        '<div class="nav-title"></div><div class="nav-sub"></div>';
      btn.querySelector(".nav-title").textContent = row.title;
      btn.querySelector(".nav-sub").textContent =
        row.status === "running"
          ? row.subtitle + " · 生成中"
          : row.status === "done"
            ? row.subtitle
            : row.subtitle + " · 暂无内容";
      if (row.clickable) {{
        btn.addEventListener("click", () => scrollToStage(row.num));
      }}
      list.appendChild(btn);
    }});
  }})();
  </script>
</body>
</html>
        """,
        height=198,
        scrolling=False,
    )
