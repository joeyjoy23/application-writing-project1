"""运行状态步骤文案（供 Streamlit 展示）。"""

from __future__ import annotations

CALLING_API = "Calling API…"
PARSING_RESPONSE = "正在解析模型输出…"
GENERATING_DISPLAY = "Generating report… (渲染结果)"
PIPELINE_FULL = "正在运行完整流程（4 个阶段）…"
PIPELINE_RESUME = "断点续传：从 Stage {n} 继续生成…"
PIPELINE_SKIP = "断点续传：跳过已完成阶段，从 Stage {n} 继续…"

STAGE_LABELS = {
    1: "Stage 1 · 审题结构分析",
    2: "Stage 2 · PEEL 与范文",
    3: "Stage 3 · 功能句型与话题词汇",
    4: "Stage 4 · 教学指南与易错预警",
}


def stage_call_api(n: int) -> str:
    return f"正在调用 API · {STAGE_LABELS[n]}"


def stage_complete(n: int) -> str:
    return f"✅ {STAGE_LABELS[n]} — 完成"


def pipeline_done() -> str:
    return "四阶段全部完成"
