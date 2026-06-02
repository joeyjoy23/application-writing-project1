"""工作流进度推断测试。"""

from services.workflow_progress import get_next_stage, resume_label, stage_has_content
from workflow import (
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
    WorkflowState,
)


def test_get_next_stage_empty():
    assert get_next_stage(WorkflowState()) == 1


def test_get_next_stage_after_stage1():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="")
    assert get_next_stage(state) == 2


def test_get_next_stage_complete():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="")
    state.stage2 = Stage2Result(raw="x")
    state.stage3 = Stage3Result(raw="y")
    state.stage4 = Stage4Result(raw="z")
    assert get_next_stage(state) is None


def test_resume_label_complete():
    assert "已完成" in resume_label(None)


def test_stage_has_content():
    state = WorkflowState()
    assert not stage_has_content(state, 1)
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="")
    assert stage_has_content(state, 1)
