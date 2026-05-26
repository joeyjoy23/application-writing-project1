"""构造利于厂商 Prompt Cache 的 messages 列表。"""

from __future__ import annotations

import os
from typing import Any


def prompt_cache_layout_enabled() -> bool:
    return os.getenv("ENABLE_PROMPT_CACHE_LAYOUT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def build_chat_messages(
    *,
    system_base: str,
    stage_prompt: str,
    user_parts: list[str],
) -> list[dict[str, Any]]:
    """
    稳定前缀在前：system 仅放通用教研规则；stage 说明与可变内容放在 user 消息末尾。
    关闭 ENABLE_PROMPT_CACHE_LAYOUT 时回退为单 system + 单 user。
    """
    if not prompt_cache_layout_enabled():
        user_body = "\n\n".join(p for p in user_parts if p.strip())
        return [
            {
                "role": "system",
                "content": f"{system_base}\n\n---\n\n{stage_prompt}",
            },
            {"role": "user", "content": user_body},
        ]

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_base},
    ]
    for part in user_parts:
        if part.strip():
            messages.append({"role": "user", "content": part.strip()})
    if stage_prompt.strip():
        messages.append(
            {
                "role": "user",
                "content": f"【本阶段任务说明】\n\n{stage_prompt.strip()}",
            }
        )
    return messages


def shared_question_context(question: str, stage1_json_text: str) -> str:
    """Stage2/3 共享的 user 前缀（原题 + Stage1 JSON）。"""
    return (
        f"【原题】\n\n{question.strip()}\n\n"
        f"【Stage1 JSON】\n\n```json\n{stage1_json_text}\n```"
    )
