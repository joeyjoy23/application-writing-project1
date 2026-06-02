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
