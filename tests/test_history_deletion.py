"""历史删除后不应被 auto_save 写回。"""

from unittest.mock import patch

from ui.history import (
    allow_history_save,
    auto_save_history,
    history_record_signature,
    is_history_save_blocked,
    mark_history_deleted,
)
from workflow import Stage1Result, WorkflowState


def test_history_record_signature_stable():
    sig1 = history_record_signature("Hello\nWorld", "glm-4")
    sig2 = history_record_signature("Hello\nWorld", "glm-4")
    sig3 = history_record_signature("Hello\nWorld", "glm-5")
    assert sig1 == sig2
    assert sig1 != sig3


def test_mark_history_deleted_blocks_auto_save():
    ss = {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "student_level": "中等",
        "question": "题目A",
        "last_question": "题目A",
        "current_history_record_id": 7,
        "_last_save_fingerprint": "old",
    }
    record = {
        "id": 7,
        "model_name": "deepseek-chat",
        "raw_input": "题目A",
        "full_content": "{}",
    }
    state = WorkflowState(question="题目A")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")

    with patch("ui.history.st.session_state", ss, create=True):
        mark_history_deleted(record)
        assert ss["current_history_record_id"] is None
        assert ss["_last_save_fingerprint"] is None
        assert is_history_save_blocked("题目A", "deepseek-chat")

        with patch("ui.history.upsert_record") as upsert:
            result = auto_save_history(state, notify=False)
            upsert.assert_not_called()
            assert result is None

        allow_history_save("题目A", "deepseek-chat")
        assert not is_history_save_blocked("题目A", "deepseek-chat")
