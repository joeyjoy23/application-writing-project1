"""LLM 阶段缓存对外 API。"""

from __future__ import annotations

import logging
from typing import Any

from db.identity import ensure_guest_id
from db.llm_cache_store import deserialize_stage_result, serialize_stage_result
from utils.llm_cache_keys import (
    make_cache_key,
    upstream_hash_stage1,
    upstream_hash_stage4,
)
from utils.prompt_rev import get_prompt_rev

logger = logging.getLogger("app.llm_cache")


def _backend():
    import os

    if (os.getenv("DATABASE_URL") or "").strip():
        from db import postgres_backend

        return postgres_backend
    from db import sqlite_backend

    return sqlite_backend


def _owner_id() -> str:
    return ensure_guest_id()


def cache_key_for_stage(
    *,
    provider: str,
    model: str,
    stage: int,
    question: str,
    stage1_json: dict[str, Any] | None = None,
    stage2_raw: str = "",
    stage3_raw: str = "",
) -> str:
    upstream = ""
    if stage >= 2:
        upstream = upstream_hash_stage1(stage1_json)
    if stage == 4:
        upstream = upstream_hash_stage4(
            stage1_json or {}, stage2_raw, stage3_raw
        )
    return make_cache_key(
        owner_id=_owner_id(),
        provider=provider,
        model=model,
        stage=stage,
        question=question,
        upstream_hash=upstream,
    )


def get_cached_stage_result(
    *,
    provider: str,
    model: str,
    stage: int,
    question: str,
    stage1_json: dict[str, Any] | None = None,
    stage2_raw: str = "",
    stage3_raw: str = "",
) -> Any | None:
    key = cache_key_for_stage(
        provider=provider,
        model=model,
        stage=stage,
        question=question,
        stage1_json=stage1_json,
        stage2_raw=stage2_raw,
        stage3_raw=stage3_raw,
    )
    raw = _backend().get_llm_cache(key, owner_id=_owner_id())
    if not raw:
        return None
    try:
        return deserialize_stage_result(stage, raw)
    except Exception as exc:
        logger.warning("LLM 缓存反序列化失败 stage=%s: %s", stage, exc)
        return None


def save_cached_stage_result(
    *,
    provider: str,
    model: str,
    stage: int,
    question: str,
    result: Any,
    stage1_json: dict[str, Any] | None = None,
    stage2_raw: str = "",
    stage3_raw: str = "",
) -> None:
    key = cache_key_for_stage(
        provider=provider,
        model=model,
        stage=stage,
        question=question,
        stage1_json=stage1_json,
        stage2_raw=stage2_raw,
        stage3_raw=stage3_raw,
    )
    payload = serialize_stage_result(stage, result)
    _backend().upsert_llm_cache(
        key,
        owner_id=_owner_id(),
        provider=provider,
        model=model,
        stage=stage,
        prompt_rev=get_prompt_rev(),
        result_json=payload,
    )
