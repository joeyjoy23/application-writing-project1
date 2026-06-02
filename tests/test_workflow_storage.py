"""WorkflowState 序列化往返测试。"""

import json

from services.workflow_storage import (
    make_export_word_filename,
    resolve_raw_input,
    workflow_content_length,
    workflow_state_from_json,
    workflow_state_payload,
    workflow_state_to_json,
    workflow_stages_mask,
)
from workflow import Stage1Result, Stage2Result, WorkflowState


def _sample_state() -> WorkflowState:
    state = WorkflowState(question="假定你是李华…")
    state.stage1 = Stage1Result(
        raw="",
        structured_json={"genre": "建议信"},
        human_summary="体裁：建议信",
    )
    state.stage2 = Stage2Result(raw="PEEL 范文…")
    return state


def test_workflow_stages_mask():
    state = _sample_state()
    assert workflow_stages_mask(state) == "1100"


def test_workflow_roundtrip_json():
    state = _sample_state()
    blob = workflow_state_to_json(
        state, provider="deepseek", model="deepseek-v4-pro", raw_input="原题全文"
    )
    restored = workflow_state_from_json(blob, raw_input="原题全文")
    assert restored.question == "原题全文"
    assert restored.stage1 is not None
    assert restored.stage1.structured_json["genre"] == "建议信"
    assert restored.stage2 is not None
    assert restored.stage2.raw == "PEEL 范文…"


def test_workflow_payload_provider_model_required():
    payload = workflow_state_payload(
        _sample_state(), provider="zhipu", model="glm-5.1"
    )
    assert payload["provider"] == "zhipu"
    assert payload["model"] == "glm-5.1"


def test_resolve_raw_input_prefers_column():
    record = {
        "raw_input": "  存档题目  ",
        "full_content": json.dumps({"question": "旧字段"}),
        "topic": "摘要",
    }
    assert resolve_raw_input(record) == "存档题目"


def test_resolve_raw_input_from_stage1_json():
    record = {
        "full_content": json.dumps(
            {
                "stage1_json": {
                    "original_text": "Line1",
                    "sentence2": "Line2",
                }
            }
        ),
        "topic": "摘要",
    }
    assert resolve_raw_input(record) == "Line1\n\nLine2"


def test_make_export_word_filename_sanitizes_model():
    name = make_export_word_filename('bad<>model', "2026-06-02")
    assert name.endswith("_bad--model.docx")
    assert "2026-06-02" in name


def test_workflow_content_length():
    state = _sample_state()
    assert workflow_content_length(state) > len(state.question)
