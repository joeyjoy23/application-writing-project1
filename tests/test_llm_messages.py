"""LLM messages 构造测试。"""

import os

from utils.llm_messages import build_chat_messages, prompt_cache_layout_enabled


def test_build_chat_messages_cache_layout(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "1")
    msgs = build_chat_messages(
        system_base="SYS",
        stage_prompt="STAGE",
        user_parts=["Q1", "Q2"],
    )
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "SYS"
    assert any("STAGE" in m.get("content", "") for m in msgs if m["role"] == "user")


def test_build_chat_messages_legacy_layout(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "0")
    msgs = build_chat_messages(
        system_base="SYS",
        stage_prompt="STAGE",
        user_parts=["Q1"],
    )
    assert len(msgs) == 2
    assert "STAGE" in msgs[0]["content"]


def test_prompt_cache_layout_disabled_values(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "false")
    assert not prompt_cache_layout_enabled()


def test_build_chat_messages_stage_prompt_before_variable_parts(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "1")
    msgs = build_chat_messages(
        system_base="SYS",
        stage_prompt="STAGE_PROMPT",
        user_parts=["VAR_A", "VAR_B"],
        tail_instruction="TAIL",
    )
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[1]["role"] == "user"
    assert "STAGE_PROMPT" in msgs[1]["content"]
    assert "VAR_A" not in msgs[1]["content"]
    assert msgs[2]["content"] == "VAR_A"
    assert msgs[3]["content"] == "VAR_B"
    assert msgs[4]["content"] == "TAIL"


def test_format_stage1_json_sort_keys():
    from utils.llm_messages import format_stage1_json

    a = format_stage1_json({"z": 1, "a": 2})
    b = format_stage1_json({"a": 2, "z": 1})
    assert a == b
    assert '"a"' in a and a.index('"a"') < a.index('"z"')


def test_build_stage1_image_user_part():
    from utils.llm_messages import build_stage1_image_user_part

    part = build_stage1_image_user_part(
        data_uri="data:image/jpeg;base64,abc",
        hint="【原题图片】请识别图中题目。",
    )
    assert part[0]["type"] == "image_url"
    assert part[0]["image_url"]["url"] == "data:image/jpeg;base64,abc"
    assert part[1]["type"] == "text"


def test_build_chat_messages_accepts_multimodal_user_part(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "1")
    multimodal = [{"type": "text", "text": "see image"}]
    msgs = build_chat_messages(
        system_base="SYS",
        stage_prompt="P",
        user_parts=[multimodal],
        tail_instruction="TAIL",
    )
    assert msgs[2]["content"] == multimodal
