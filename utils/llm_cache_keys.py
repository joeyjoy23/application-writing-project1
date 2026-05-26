"""LLM 阶段结果缓存键（与 db.llm_cache 表配合）。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from db.common import make_question_hash
from utils.prompt_rev import get_prompt_rev


def _digest(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def upstream_hash_stage1(stage1_json: dict[str, Any] | None) -> str:
    if not stage1_json:
        return ""
    payload = json.dumps(stage1_json, ensure_ascii=False, sort_keys=True)
    return _digest(payload)


def upstream_hash_stage4(
    stage1_json: dict[str, Any],
    stage2_raw: str,
    stage3_raw: str,
) -> str:
    """Stage4 依赖上游压缩摘要键（与 workflow Stage4 输入一致）。"""
    from utils.stage4_input import build_stage4_upstream_digest

    return build_stage4_upstream_digest(stage1_json, stage2_raw, stage3_raw)


def make_cache_key(
    *,
    owner_id: str,
    provider: str,
    model: str,
    stage: int,
    question: str,
    upstream_hash: str = "",
) -> str:
    q_hash = make_question_hash(question)
    parts = [
        owner_id,
        provider.lower(),
        model.strip(),
        get_prompt_rev(),
        str(stage),
        q_hash,
        upstream_hash,
    ]
    return _digest("|".join(parts))
