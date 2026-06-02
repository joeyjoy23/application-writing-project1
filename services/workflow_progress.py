"""工作流进度推断（无 UI 依赖）。"""

from __future__ import annotations

from workflow import WorkflowState


def stage_has_content(state: WorkflowState, stage_num: int) -> bool:
    return {
        1: state.stage1,
        2: state.stage2,
        3: state.stage3,
        4: state.stage4,
    }.get(stage_num) is not None


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
