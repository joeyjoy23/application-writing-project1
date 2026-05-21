"""运行状态步骤文案（供 Streamlit 展示）。"""

from __future__ import annotations

APP_START = "Running app.py…"
PREPARING = "Preparing workflow…"
LOADING_PROMPT = "Analyzing text… (加载提示词)"
CALLING_API = "Calling API…"
PARSING_RESPONSE = "Parsing response…"
GENERATING_DISPLAY = "Generating report… (渲染结果)"
PIPELINE_DONE = "All 4 stages completed."

STAGE_LABELS = {
    1: "Stage 1 · 审题结构分析",
    2: "Stage 2 · PEEL 与范文",
    3: "Stage 3 · 功能句型与话题词汇",
    4: "Stage 4 · 教学指南与易错预警",
}


def stage_load_prompt(n: int) -> str:
    return f"Analyzing text… (加载 {STAGE_LABELS[n]})"


def stage_call_api(n: int) -> str:
    return f"Calling API… ({STAGE_LABELS[n]})"


def stage_complete(n: int) -> str:
    return f"✅ {STAGE_LABELS[n]} — 完成"
