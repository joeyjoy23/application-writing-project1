"""新建页辅助逻辑测试。"""

from unittest.mock import patch

from ui.new_page import _current_question_text
from ui.stale_results import question_results_stale
from workflow import Stage1Result, WorkflowState


def test_current_question_text_prefers_run_job() -> None:
    ss = {
        "run_job": {"question": "  from job  "},
        "question": "from session",
    }
    with patch("ui.new_page.st.session_state", ss):
        assert _current_question_text() == "from job"


def test_current_question_text_falls_back_to_editor() -> None:
    ss = {"question_editor": "editor text", "question": ""}
    with patch("ui.new_page.st.session_state", ss):
        assert _current_question_text() == "editor text"


def test_question_results_stale_when_question_changed():
    state = WorkflowState(question="old")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="s")
    ss = {
        "last_question": "旧题目",
        "workflow_state": state,
    }
    with patch("ui.stale_results.st.session_state", ss):
        assert question_results_stale("新题目") is True
        assert question_results_stale("旧题目") is False


def test_question_results_stale_false_without_results():
    ss = {"last_question": "题", "workflow_state": None}
    with patch("ui.stale_results.st.session_state", ss):
        assert question_results_stale("另一题") is False


def test_question_results_stale_false_when_editor_empty_but_workflow_matches():
    state = WorkflowState(question="识别后的题目\n[图：海报]")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="s")
    ss = {
        "last_question": "识别后的题目\n[图：海报]",
        "workflow_state": state,
        "question_image": {"b64": "x", "mime": "image/jpeg"},
    }
    with patch("ui.stale_results.st.session_state", ss):
        assert question_results_stale("") is False


def test_resolve_effective_question_image_with_stage1():
    from utils.question_input import resolve_effective_question

    assert resolve_effective_question(
        "",
        {"b64": "x", "mime": "image/jpeg"},
        workflow_question="真题文本",
        last_question="真题文本",
    ) == "真题文本"
