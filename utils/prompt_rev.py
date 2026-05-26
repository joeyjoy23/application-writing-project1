"""Prompt 目录版本号：prompts 变更后使 LLM 结果缓存失效。"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from utils.config import get_project_root

PROMPTS_DIR = get_project_root() / "prompts"
_PROMPT_FILES = (
    "system_prompt.md",
    "stage1_prompt.md",
    "stage2_prompt.md",
    "stage3_prompt.md",
    "stage4_prompt.md",
)


@lru_cache(maxsize=1)
def get_prompt_rev() -> str:
    """所有 prompt 文件内容拼接后的 sha256 前 16 位。"""
    h = hashlib.sha256()
    for name in sorted(_PROMPT_FILES):
        path = PROMPTS_DIR / name
        if path.is_file():
            h.update(name.encode("utf-8"))
            h.update(path.read_bytes())
    return h.hexdigest()[:16]
