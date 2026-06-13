"""新建页辅助逻辑测试。"""

from unittest.mock import patch

from ui.new_page import question_results_stale
from workflow import Stage1Result, WorkflowState


def test_question_results_stale_when_question_changed():
    state = WorkflowState(question="old")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="s")
    ss = {
        "last_question": "旧题目",
        "workflow_state": state,
    }
    with patch("ui.new_page.st.session_state", ss):
        assert question_results_stale("新题目") is True
        assert question_results_stale("旧题目") is False


def test_question_results_stale_false_without_results():
    ss = {"last_question": "题", "workflow_state": None}
    with patch("ui.new_page.st.session_state", ss):
        assert question_results_stale("另一题") is False
