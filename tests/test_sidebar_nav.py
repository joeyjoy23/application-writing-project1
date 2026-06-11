"""侧边栏 Stage 索引导航逻辑。"""

from unittest.mock import MagicMock, patch

from ui.sidebar_nav import main_area_shows_stage_panels, resolve_nav_workflow_state
from workflow import Stage1Result, WorkflowState


def test_main_area_history_detail():
    ss = {
        "app_mode": "历史",
        "history_view_id": 42,
    }
    with patch("ui.sidebar_nav.st.session_state", ss):
        assert main_area_shows_stage_panels() is True


def test_main_area_history_list_only():
    ss = {
        "app_mode": "历史",
        "history_view_id": None,
    }
    with patch("ui.sidebar_nav.st.session_state", ss):
        assert main_area_shows_stage_panels() is False


def test_resolve_nav_uses_history_state_on_detail():
    hist = WorkflowState(question="q")
    hist.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    ss = {
        "app_mode": "历史",
        "history_view_id": 1,
        "history_nav_state": hist,
        "workflow_state": None,
    }
    with patch("ui.sidebar_nav.st.session_state", ss):
        resolved = resolve_nav_workflow_state()
    assert resolved is hist
    assert resolved.stage1 is not None
