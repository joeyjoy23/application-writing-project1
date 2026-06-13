"""历史载入与导出 UX 文案测试。"""

from __future__ import annotations

from ui.history import history_resume_hint
from workflow import Stage1Result, Stage2Result, Stage3Result, Stage4Result, WorkflowState


def _partial_state(*, s2: bool = False, s3: bool = False, s4: bool = False) -> WorkflowState:
    state = WorkflowState(question="Q")
    state.stage1 = Stage1Result(raw="raw", structured_json={}, human_summary="s1")
    if s2:
        state.stage2 = Stage2Result(raw="s2")
    if s3:
        state.stage3 = Stage3Result(raw="s3")
    if s4:
        state.stage4 = Stage4Result(raw="s4")
    return state


def test_history_resume_hint_partial_does_not_mention_switch_mode():
    hint = history_resume_hint(_partial_state())
    assert "切换到「新建」" not in hint
    assert "继续生成" in hint


def test_history_resume_hint_complete():
    hint = history_resume_hint(_partial_state(s2=True, s3=True, s4=True))
    assert "四阶段已全部完成" in hint
