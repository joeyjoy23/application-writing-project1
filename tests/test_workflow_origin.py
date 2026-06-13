"""换模型后是否应重跑 workflow 的判定。"""

import json
from unittest.mock import MagicMock, patch

from services.workflow_origin import (
    ensure_workflow_origin_from_history,
    job_llm_settings_changed,
    llm_selection_mismatch,
    origin_fields_from_record,
    resolved_llm,
    sync_workflow_origin_from_record,
)
from workflow import Stage1Result, WorkflowState


def test_resolved_llm_normalizes_deepseek_alias():
    p, m = resolved_llm("deepseek", "deepseek-chat")
    assert p == "deepseek"
    assert m == "deepseek-v4-pro"


def test_llm_selection_mismatch_when_model_changes():
    assert llm_selection_mismatch(
        "deepseek",
        "deepseek-v4-pro",
        "zhipu",
        "glm-5.1",
    )


def test_llm_selection_mismatch_false_when_same_model():
    assert not llm_selection_mismatch(
        "deepseek",
        "deepseek-v4-pro",
        "deepseek",
        "deepseek-v4-pro",
    )


def test_llm_selection_mismatch_false_without_origin():
    assert not llm_selection_mismatch(None, None, "deepseek", "deepseek-v4-pro")


def test_job_llm_settings_changed_false_when_sidebar_uses_resolvable_alias():
    """别名解析后与 locked_model 相同，不应误判为换模型。"""
    job = {"locked_provider": "deepseek", "locked_model": "deepseek-v4-pro"}
    assert not job_llm_settings_changed(
        job,
        current_provider="deepseek",
        current_model="deepseek-chat",
    )


def test_job_llm_settings_changed_false_when_resolved_same():
    job = {"locked_provider": "deepseek", "locked_model": "deepseek-v4-pro"}
    assert not job_llm_settings_changed(
        job,
        current_provider="deepseek",
        current_model="deepseek-v4-pro",
    )


def test_job_llm_settings_changed_when_provider_changes():
    job = {"locked_provider": "deepseek", "locked_model": "deepseek-v4-pro"}
    assert job_llm_settings_changed(
        job,
        current_provider="zhipu",
        current_model="glm-5.1",
    )


def test_origin_fields_from_record_uses_model_name_column():
    data = {"provider": "deepseek", "stage1_summary": "x"}
    record = {"model_name": "deepseek-v4-pro"}
    provider, model = origin_fields_from_record(data, record)
    assert provider == "deepseek"
    assert model == "deepseek-v4-pro"


def test_origin_fields_from_record_prefers_json_model():
    data = {"provider": "zhipu", "model": "glm-5.1"}
    record = {"model_name": "glm-4.7"}
    provider, model = origin_fields_from_record(data, record)
    assert provider == "zhipu"
    assert model == "glm-5.1"


def test_sync_workflow_origin_from_record_sets_session():
    data = {"provider": "deepseek", "model": "deepseek-v4-pro"}
    record = {"model_name": "deepseek-v4-pro"}
    ss = MagicMock()
    ss.get = lambda key, default=None: {
        "workflow_source_provider": None,
        "workflow_source_model": None,
    }.get(key, default)
    with patch("services.workflow_origin.st.session_state", ss):
        ok = sync_workflow_origin_from_record(data, record, record_id=99)
    assert ok is True
    assert ss.workflow_source_provider == "deepseek"
    assert ss.workflow_source_model == "deepseek-v4-pro"
    assert ss.current_history_record_id == 99


def test_ensure_workflow_origin_from_history_uses_current_record_id():
    state = WorkflowState(question="q")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    record = {
        "full_content": json.dumps(
            {"provider": "zhipu", "model": "glm-5.1"},
            ensure_ascii=False,
        ),
        "model_name": "glm-5.1",
    }
    ss = MagicMock()
    ss.get = lambda key, default=None: {
        "workflow_source_provider": None,
        "workflow_source_model": None,
        "workflow_state": state,
        "current_history_record_id": 42,
        "history_view_id": 99,
    }.get(key, default)
    with patch("services.workflow_origin.st.session_state", ss):
        with patch("db.get_record_by_id", return_value=record) as get_rec:
            ensure_workflow_origin_from_history()
            get_rec.assert_called_once_with(42)
    assert ss.workflow_source_provider == "zhipu"
    assert ss.workflow_source_model == "glm-5.1"


def test_ensure_workflow_origin_skips_history_view_without_record_id():
    state = WorkflowState(question="q")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    ss = MagicMock()
    ss.get = lambda key, default=None: {
        "workflow_source_provider": None,
        "workflow_source_model": None,
        "workflow_state": state,
        "current_history_record_id": None,
        "history_view_id": 99,
    }.get(key, default)
    with patch("services.workflow_origin.st.session_state", ss):
        with patch("db.get_record_by_id") as get_rec:
            ensure_workflow_origin_from_history()
            get_rec.assert_not_called()
