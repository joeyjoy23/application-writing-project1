"""Neon / PostgreSQL 历史库（Streamlit Cloud 持久化）。"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from db.common import make_question_hash, topic_summary

logger = logging.getLogger("app.db.postgres")

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS history (
    id BIGSERIAL PRIMARY KEY,
    owner_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    topic TEXT NOT NULL,
    model_name TEXT NOT NULL,
    full_content TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0,
    stages_mask CHAR(4) NOT NULL DEFAULT '0000',
    question_hash TEXT NOT NULL DEFAULT '',
    raw_input TEXT NOT NULL DEFAULT '',
    is_starred INTEGER NOT NULL DEFAULT 0,
    UNIQUE (owner_id, question_hash, model_name)
);
CREATE INDEX IF NOT EXISTS idx_history_owner_created ON history (owner_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC);
ALTER TABLE history ADD COLUMN IF NOT EXISTS is_starred INTEGER NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    stage INTEGER NOT NULL,
    prompt_rev TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_cache_owner ON llm_cache (owner_id, updated_at DESC);
"""


def database_url() -> str:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        raise RuntimeError("未配置 DATABASE_URL，无法连接 Neon")
    return url


@contextmanager
def _connect() -> Iterator[Any]:
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(database_url(), row_factory=dict_row) as conn:
        yield conn


def init_db() -> None:
    with _connect() as conn:
        for stmt in _SCHEMA_SQL.split(";"):
            s = stmt.strip()
            if s:
                conn.execute(s)
        conn.commit()
    logger.info("PostgreSQL history 表已就绪")


def _owner_filter(owner_id: str, admin: bool) -> tuple[str, list[Any]]:
    if admin:
        return "", []
    return " AND owner_id = %s", [owner_id]


def save_record(
    topic: str,
    model: str,
    content: str,
    *,
    owner_id: str,
    raw_input: str | None = None,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> int:
    init_db()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    raw = (raw_input if raw_input is not None else topic).strip()
    q_hash = make_question_hash(raw)
    with _connect() as conn:
        row = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input, owner_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                created_at,
                topic.strip(),
                model.strip(),
                content,
                wc,
                mask,
                q_hash,
                raw,
                owner_id,
            ),
        ).fetchone()
        conn.commit()
        record_id = int(row["id"])
        logger.info("备课包已保存 #%d owner=%s", record_id, owner_id[:8])
        return record_id


def upsert_record(
    question: str,
    model: str,
    content: str,
    *,
    owner_id: str,
    raw_input: str | None = None,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> tuple[int, bool]:
    init_db()
    raw = (raw_input if raw_input is not None else question).strip()
    q_hash = make_question_hash(raw)
    model_name = model.strip()
    topic = topic_summary(raw or question)
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM history
            WHERE owner_id = %s AND question_hash = %s AND model_name = %s
            ORDER BY id DESC LIMIT 1
            """,
            (owner_id, q_hash, model_name),
        ).fetchone()

        if existing:
            record_id = int(existing["id"])
            conn.execute(
                """
                UPDATE history
                SET created_at = %s, topic = %s, full_content = %s, word_count = %s,
                    stages_mask = %s, question_hash = %s, raw_input = %s
                WHERE id = %s AND owner_id = %s
                """,
                (now, topic, content, wc, mask, q_hash, raw, record_id, owner_id),
            )
            conn.commit()
            logger.info("备课包已更新 #%d", record_id)
            return record_id, False

        row = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input, owner_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (now, topic, model_name, content, wc, mask, q_hash, raw, owner_id),
        ).fetchone()
        conn.commit()
        record_id = int(row["id"])
        logger.info("备课包已新建 #%d owner=%s", record_id, owner_id[:8])
        return record_id, True


def get_all_records(
    keyword: str,
    *,
    limit: int,
    offset: int,
    owner_id: str,
    admin: bool,
    starred_only: bool = False,
) -> list[dict[str, Any]]:
    init_db()
    sql = (
        "SELECT id, created_at, topic, model_name, word_count, stages_mask, owner_id, is_starred "
        "FROM history WHERE 1=1"
    )
    params: list[Any] = []
    owner_sql, owner_params = _owner_filter(owner_id, admin)
    sql += owner_sql
    params.extend(owner_params)
    if starred_only:
        sql += " AND is_starred = 1"
    kw = (keyword or "").strip()
    if kw:
        sql += " AND (topic ILIKE %s OR model_name ILIKE %s)"
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql += " ORDER BY id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def count_records(keyword: str, *, owner_id: str, admin: bool, starred_only: bool = False) -> int:
    init_db()
    sql = "SELECT COUNT(*) AS c FROM history WHERE 1=1"
    params: list[Any] = []
    owner_sql, owner_params = _owner_filter(owner_id, admin)
    sql += owner_sql
    params.extend(owner_params)
    if starred_only:
        sql += " AND is_starred = 1"
    kw = (keyword or "").strip()
    if kw:
        sql += " AND (topic ILIKE %s OR model_name ILIKE %s)"
        params.extend([f"%{kw}%", f"%{kw}%"])
    with _connect() as conn:
        row = conn.execute(sql, params).fetchone()
    return int(row["c"])


def get_record_by_id(
    record_id: int, *, owner_id: str, admin: bool
) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        if admin:
            row = conn.execute(
                "SELECT * FROM history WHERE id = %s",
                (record_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM history WHERE id = %s AND owner_id = %s",
                (record_id, owner_id),
            ).fetchone()
    return dict(row) if row else None


def toggle_star(record_id: int, starred: bool, *, owner_id: str, admin: bool) -> bool:
    """切换收藏（is_starred 字段）。"""
    init_db()
    with _connect() as conn:
        if admin:
            cur = conn.execute(
                "UPDATE history SET is_starred = %s WHERE id = %s",
                (1 if starred else 0, record_id),
            )
        else:
            cur = conn.execute(
                "UPDATE history SET is_starred = %s WHERE id = %s AND owner_id = %s",
                (1 if starred else 0, record_id, owner_id),
            )
        conn.commit()
        return cur.rowcount > 0


def delete_record(record_id: int, *, owner_id: str, admin: bool) -> bool:
    init_db()
    with _connect() as conn:
        if admin:
            cur = conn.execute("DELETE FROM history WHERE id = %s", (record_id,))
        else:
            cur = conn.execute(
                "DELETE FROM history WHERE id = %s AND owner_id = %s",
                (record_id, owner_id),
            )
        conn.commit()
        ok = cur.rowcount > 0
        if ok:
            logger.info("删除历史记录 #%d", record_id)
        return ok


def get_llm_cache(cache_key: str, *, owner_id: str) -> str | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT result_json FROM llm_cache WHERE cache_key = %s AND owner_id = %s",
            (cache_key, owner_id),
        ).fetchone()
    return str(row["result_json"]) if row else None


def upsert_llm_cache(
    cache_key: str,
    *,
    owner_id: str,
    provider: str,
    model: str,
    stage: int,
    prompt_rev: str,
    result_json: str,
) -> None:
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_cache (
                cache_key, owner_id, provider, model_name, stage,
                prompt_rev, result_json, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cache_key) DO UPDATE SET
                result_json = EXCLUDED.result_json,
                updated_at = EXCLUDED.updated_at,
                model_name = EXCLUDED.model_name,
                provider = EXCLUDED.provider,
                stage = EXCLUDED.stage,
                prompt_rev = EXCLUDED.prompt_rev
            """,
            (
                cache_key,
                owner_id,
                provider.lower(),
                model.strip(),
                stage,
                prompt_rev,
                result_json,
                now,
                now,
            ),
        )
        conn.commit()
