"""Neon / PostgreSQL 历史库（Streamlit Cloud 持久化）。"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from contextlib import contextmanager
from datetime import datetime

from utils.datetime_util import utc_now_str
from typing import Any, Iterator

from db.common import make_question_hash, topic_summary

logger = logging.getLogger("app.db.postgres")

# Cloud 多 worker / 多会话并发跑 DDL 时易死锁，用进程内锁 + PG advisory lock
_schema_ensured = False
_init_lock = threading.Lock()
_ADVISORY_LOCK_KEY = 873421905

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
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
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_history_owner_created ON history (owner_id, id DESC)",
    "CREATE INDEX IF NOT EXISTS idx_history_created_at ON history (created_at DESC)",
    "ALTER TABLE history ADD COLUMN IF NOT EXISTS is_starred INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE history ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE history ADD COLUMN IF NOT EXISTS completion_tokens INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE history ADD COLUMN IF NOT EXISTS cached_tokens INTEGER NOT NULL DEFAULT 0",
    """
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
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_llm_cache_owner ON llm_cache (owner_id, updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS share_links (
        token TEXT PRIMARY KEY,
        history_id BIGINT NOT NULL,
        owner_id TEXT NOT NULL,
        snapshot_json TEXT NOT NULL,
        topic TEXT NOT NULL,
        model_name TEXT NOT NULL,
        stages_mask CHAR(4) NOT NULL DEFAULT '0000',
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        revoked INTEGER NOT NULL DEFAULT 0,
        view_count INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_share_history_owner ON share_links (history_id, owner_id)",
)


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


def _is_retryable_db_exc(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("DeadlockDetected", "LockNotAvailable", "SerializationFailure"):
        return True
    cause = getattr(exc, "__cause__", None)
    return _is_retryable_db_exc(cause) if cause else False


def _apply_schema(conn: Any) -> None:
    conn.execute("SELECT pg_advisory_lock(%s)", (_ADVISORY_LOCK_KEY,))
    try:
        for stmt in _SCHEMA_STATEMENTS:
            conn.execute(stmt.strip())
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (_ADVISORY_LOCK_KEY,))


def init_db() -> None:
    global _schema_ensured
    if _schema_ensured:
        return
    with _init_lock:
        if _schema_ensured:
            return
        last_err: BaseException | None = None
        for attempt in range(5):
            try:
                with _connect() as conn:
                    _apply_schema(conn)
                    conn.commit()
                _schema_ensured = True
                logger.info("PostgreSQL history 表已就绪")
                return
            except Exception as exc:
                last_err = exc
                if _is_retryable_db_exc(exc) and attempt < 4:
                    wait = 0.15 * (2**attempt)
                    logger.warning(
                        "PostgreSQL 建表冲突，%ss 后重试 (%d/5): %s",
                        wait,
                        attempt + 1,
                        type(exc).__name__,
                    )
                    time.sleep(wait)
                    continue
                raise
        if last_err:
            raise last_err


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
    usage: dict[str, int] | None = None,
) -> int:
    init_db()
    created_at = utc_now_str()
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    raw = (raw_input if raw_input is not None else topic).strip()
    q_hash = make_question_hash(raw)
    pt = int((usage or {}).get("prompt_tokens") or 0)
    ct = int((usage or {}).get("completion_tokens") or 0)
    cat = int((usage or {}).get("cached_tokens") or 0)
    with _connect() as conn:
        row = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input, owner_id,
                prompt_tokens, completion_tokens, cached_tokens
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                pt, ct, cat,
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
    usage: dict[str, int] | None = None,
) -> tuple[int, bool]:
    init_db()
    raw = (raw_input if raw_input is not None else question).strip()
    q_hash = make_question_hash(raw)
    model_name = model.strip()
    topic = topic_summary(raw or question)
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    now = utc_now_str()
    pt = int((usage or {}).get("prompt_tokens") or 0)
    ct = int((usage or {}).get("completion_tokens") or 0)
    cat = int((usage or {}).get("cached_tokens") or 0)

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
                    stages_mask = %s, question_hash = %s, raw_input = %s,
                    prompt_tokens = %s, completion_tokens = %s, cached_tokens = %s
                WHERE id = %s AND owner_id = %s
                """,
                (now, topic, content, wc, mask, q_hash, raw, pt, ct, cat, record_id, owner_id),
            )
            conn.commit()
            logger.info("备课包已更新 #%d", record_id)
            return record_id, False

        row = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input, owner_id,
                prompt_tokens, completion_tokens, cached_tokens
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (now, topic, model_name, content, wc, mask, q_hash, raw, owner_id, pt, ct, cat),
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
        "SELECT id, created_at, topic, model_name, word_count, stages_mask, owner_id, is_starred, "
        "prompt_tokens, completion_tokens, cached_tokens "
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
    now = utc_now_str()
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


def _fetch_history_for_share(
    conn: Any, history_id: int, *, viewer_owner_id: str, admin: bool
) -> dict[str, Any] | None:
    """管理员可分享任意历史；普通用户仅能分享本人记录。"""
    if admin:
        row = conn.execute(
            "SELECT * FROM history WHERE id = %s",
            (history_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM history WHERE id = %s AND owner_id = %s",
            (history_id, viewer_owner_id),
        ).fetchone()
    return dict(row) if row else None


def get_active_share_token(history_id: int) -> str | None:
    """未撤销且未过期的分享令牌（按 history_id，全局唯一）。"""
    from utils.share_util import is_share_expired

    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT token, expires_at, revoked
            FROM share_links
            WHERE history_id = %s AND revoked = 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (history_id,),
        ).fetchone()
    if not row:
        return None
    if int(row["revoked"]) or is_share_expired(str(row["expires_at"])):
        return None
    return str(row["token"])


def create_or_refresh_share_link(
    history_id: int, *, viewer_owner_id: str, admin: bool = False
) -> str | None:
    from utils.share_util import expires_at_from_now, is_share_expired

    init_db()
    with _connect() as conn:
        record = _fetch_history_for_share(
            conn, history_id, viewer_owner_id=viewer_owner_id, admin=admin
        )
        if not record:
            return None
        record_owner = str(record["owner_id"])
        topic = str(record.get("topic") or "")
        model_name = str(record.get("model_name") or "")
        snapshot = str(record.get("full_content") or "")
        mask = str(record.get("stages_mask") or "0000")
        now = utc_now_str()
        expires = expires_at_from_now()

        row = conn.execute(
            """
            SELECT token, expires_at, revoked
            FROM share_links
            WHERE history_id = %s AND revoked = 0
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (history_id,),
        ).fetchone()

        if row and not int(row["revoked"]) and not is_share_expired(str(row["expires_at"])):
            token = str(row["token"])
            conn.execute(
                """
                UPDATE share_links
                SET snapshot_json = %s, topic = %s, model_name = %s, stages_mask = %s,
                    expires_at = %s, created_at = %s, owner_id = %s
                WHERE token = %s
                """,
                (snapshot, topic, model_name, mask, expires, now, record_owner, token),
            )
        else:
            token = secrets.token_urlsafe(24)
            conn.execute(
                """
                INSERT INTO share_links (
                    token, history_id, owner_id, snapshot_json, topic, model_name,
                    stages_mask, created_at, expires_at, revoked, view_count
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0)
                """,
                (
                    token,
                    history_id,
                    record_owner,
                    snapshot,
                    topic,
                    model_name,
                    mask,
                    now,
                    expires,
                ),
            )
        conn.commit()
        logger.info("分享链接已就绪 history=#%d token=%s…", history_id, token[:8])
        return token


def get_public_share(token: str) -> dict[str, Any] | None:
    from utils.share_util import is_share_expired

    if not token:
        return None
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM share_links WHERE token = %s",
            (token,),
        ).fetchone()
        if not row or int(row["revoked"]):
            return None
        if is_share_expired(str(row["expires_at"])):
            return None
        conn.execute(
            "UPDATE share_links SET view_count = view_count + 1 WHERE token = %s",
            (token,),
        )
        conn.commit()
    return dict(row)
