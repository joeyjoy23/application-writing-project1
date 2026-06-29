"""历史载入与清空断点时保留题目。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class _FakeSessionState(dict):
    def __getattr__(self, name: str):
        return self.get(name)

    def __setattr__(self, name: str, value) -> None:
        if name == "__dict__":
            super().__setattr__(name, value)
        else:
            self[name] = value


def test_clear_checkpoint_preserves_question_and_image() -> None:
    from ui.sidebar import clear_checkpoint

    ws = SimpleNamespace(question="假定你是李华，写建议信……")
    ss = _FakeSessionState(
        workflow_state=ws,
        question_editor="假定你是李华，写建议信……",
        question="假定你是李华，写建议信……",
        last_question="假定你是李华，写建议信……",
        question_image={"b64": "abc", "mime": "image/jpeg"},
    )

    with patch("ui.sidebar.st") as mock_st:
        mock_st.session_state = ss
        with patch(
            "services.run_recovery.clear_run_checkpoint_for_owner"
        ), patch("services.workflow_origin.clear_workflow_origin"), patch(
            "db.identity.ensure_guest_id", return_value="guest-1"
        ):
            clear_checkpoint()

    assert ss.get("question") == "假定你是李华，写建议信……"
    assert ss.get("question_editor") == "假定你是李华，写建议信……"
    assert ss.get("last_question") == "假定你是李华，写建议信……"
    assert ss.get("question_image") == {"b64": "abc", "mime": "image/jpeg"}
    assert ss.get("workflow_state") is None
