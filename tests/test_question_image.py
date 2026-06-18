from utils.question_input import (
    QuestionImage,
    format_image_question_for_history,
    image_to_data_uri,
    question_input_conflict,
)
from utils.parsers import format_image_question_for_history as fmt_from_parsers


def test_question_input_conflict():
    assert question_input_conflict("hello", None) is False
    assert question_input_conflict("", {"b64": "x", "mime": "image/jpeg"}) is False
    assert question_input_conflict("text", {"b64": "x", "mime": "image/jpeg"}) is True


def test_resolve_effective_question_prefers_editor_text():
    from utils.question_input import resolve_effective_question

    assert resolve_effective_question("纯文字题", None) == "纯文字题"


def test_format_image_question_for_history():
    assert format_image_question_for_history({
        "recognized_question_text": "Write a letter...",
        "image_brief_description": "两张海报供选择",
    }) == "Write a letter...\n[图：两张海报供选择]"
    assert format_image_question_for_history({}) == "[图片题目]"


def test_image_to_data_uri():
    img = QuestionImage(mime="image/jpeg", b64="abc123", name="q.jpg")
    assert image_to_data_uri(img) == "data:image/jpeg;base64,abc123"


def test_parsers_format_image_question():
    assert fmt_from_parsers({
        "recognized_question_text": "A",
        "image_brief_description": "B",
    }) == "A\n[图：B]"


def test_run_stage1_with_image_sends_multimodal(monkeypatch):
    from unittest.mock import MagicMock

    from workflow import GaokaoWritingWorkflow

    captured: dict = {}

    def fake_call(self, messages, **kwargs):
        captured["messages"] = messages
        return (
            "# PART A：STRUCTURED_JSON\n```json\n{}\n```\n"
            "# PART B：HUMAN_READABLE_SUMMARY\n\nok"
        )

    wf = GaokaoWritingWorkflow(client=MagicMock())
    monkeypatch.setattr(GaokaoWritingWorkflow, "_call", fake_call)

    wf.run_stage1(
        "[图片题目]",
        question_image={"mime": "image/jpeg", "b64": "abc123"},
    )
    user_msg = captured["messages"][2]["content"]
    assert isinstance(user_msg, list)
    assert user_msg[0]["type"] == "image_url"
    assert "abc123" in user_msg[0]["image_url"]["url"]
