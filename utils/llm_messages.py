"""构造利于厂商 Prompt Cache 的 messages 列表。"""

from __future__ import annotations

import json
import os
from typing import Any


def prompt_cache_layout_enabled() -> bool:
    return os.getenv("ENABLE_PROMPT_CACHE_LAYOUT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def format_stage1_json(stage1_json: dict[str, Any]) -> str:
    return json.dumps(stage1_json, ensure_ascii=False, indent=2, sort_keys=True)


def build_stage1_image_user_part(*, data_uri: str, hint: str) -> list[dict[str, Any]]:
    return [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {"type": "text", "text": hint.strip()},
    ]


def build_chat_messages(
    *,
    system_base: str,
    stage_prompt: str,
    user_parts: list[str | list[dict[str, Any]]],
    tail_instruction: str = "",
) -> list[dict[str, Any]]:
    """
    缓存友好顺序（ENABLE_PROMPT_CACHE_LAYOUT=1）：
    system → user(stage_prompt) → user(可变…) → user(tail)

    关闭 ENABLE_PROMPT_CACHE_LAYOUT 时回退为单 system + 单 user。
    """
    if not prompt_cache_layout_enabled():
        chunks = [
            p.strip() for p in user_parts if isinstance(p, str) and p.strip()
        ]
        if tail_instruction.strip():
            chunks.append(tail_instruction.strip())
        user_body = "\n\n".join(chunks)
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": f"{system_base}\n\n---\n\n{stage_prompt}",
            },
            {"role": "user", "content": user_body},
        ]
        for part in user_parts:
            if isinstance(part, list):
                messages.append({"role": "user", "content": part})
        return messages

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_base}]
    if stage_prompt.strip():
        messages.append(
            {
                "role": "user",
                "content": f"【本阶段任务说明】\n\n{stage_prompt.strip()}",
            }
        )
    for part in user_parts:
        if isinstance(part, list):
            messages.append({"role": "user", "content": part})
        elif part.strip():
            messages.append({"role": "user", "content": part.strip()})
    if tail_instruction.strip():
        messages.append({"role": "user", "content": tail_instruction.strip()})
    return messages


def shared_question_context(question: str, stage1_json_text: str) -> str:
    """Stage2/3 共享的 user 前缀（原题 + Stage1 JSON）。"""
    return (
        f"【原题】\n\n{question.strip()}\n\n"
        f"【Stage1 JSON】\n\n```json\n{stage1_json_text}\n```"
    )
