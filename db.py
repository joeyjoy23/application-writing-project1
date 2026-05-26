"""SQLite 历史记录：备课包自动存档与检索。"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from datetime import datetime
from typing import Any

import streamlit as st

from utils.config import get_project_root

logger = logging.getLogger("app.db")

DB_PATH = get_project_root() / "history.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            topic TEXT NOT NULL,
            model_name TEXT NOT NULL,
            full_content TEXT NOT NULL,
            word_count INTEGER NOT NULL DEFAULT 0,
            stages_mask TEXT NOT NULL DEFAULT '0000'
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_created_at ON history(created_at DESC)"
    )
    try:
        conn.execute(
            "ALTER TABLE history ADD COLUMN stages_mask TEXT NOT NULL DEFAULT '0000'"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE history ADD COLUMN question_hash TEXT NOT NULL DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute(
            "ALTER TABLE history ADD COLUMN raw_input TEXT NOT NULL DEFAULT ''"
        )
    except sqlite3.OperationalError:
        pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_question_model "
        "ON history(question_hash, model_name)"
    )


def init_db() -> None:
    """首次运行时创建 history 表。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _ensure_schema(conn)
        conn.commit()


def make_question_hash(question: str) -> str:
    """同一道题用固定哈希，便于与模型名组合去重。"""
    normalized = (question or "").strip().replace("\r\n", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _topic_summary(question: str, *, max_len: int = 100) -> str:
    return (question or "（无题目）").strip().replace("\n", " ")[:max_len]


def save_record(
    topic: str,
    model: str,
    content: str,
    *,
    raw_input: str | None = None,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> int:
    """保存一条备课包记录，返回新记录 id。"""
    init_db()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    raw = (raw_input if raw_input is not None else topic).strip()
    q_hash = make_question_hash(raw)
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (created_at, topic.strip(), model.strip(), content, wc, mask, q_hash, raw),
        )
        conn.commit()
        record_id = int(cur.lastrowid)
        logger.info("备课包已保存 #%d topic=%s model=%s", record_id, topic[:30], model)
        _invalidate_history_cache()
        return record_id


def upsert_record(
    question: str,
    model: str,
    content: str,
    *,
    raw_input: str | None = None,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> tuple[int, bool]:
    """
    同一题目 + 同一模型：更新已有记录，不新增多条。
    同一题目 + 不同模型：各存一条。

    返回 (记录 id, 是否为新插入)。
    """
    init_db()
    raw = (raw_input if raw_input is not None else question).strip()
    q_hash = make_question_hash(raw)
    model_name = model.strip()
    topic = _topic_summary(raw or question)
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id FROM history
            WHERE question_hash = ? AND model_name = ?
            ORDER BY id DESC LIMIT 1
            """,
            (q_hash, model_name),
        ).fetchone()

        if row:
            record_id = int(row[0])
            conn.execute(
                """
                UPDATE history
                SET created_at = ?, topic = ?, full_content = ?, word_count = ?, stages_mask = ?,
                    question_hash = ?, raw_input = ?
                WHERE id = ?
                """,
                (now, topic, content, wc, mask, q_hash, raw, record_id),
            )
            conn.commit()
            logger.info("备课包已更新 #%d model=%s", record_id, model_name)
            _invalidate_history_cache()
            return record_id, False

        cur = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, topic, model_name, content, wc, mask, q_hash, raw),
        )
        conn.commit()
        record_id = int(cur.lastrowid)
        logger.info("备课包已新建 #%d topic=%s model=%s", record_id, topic[:30], model_name)
        _invalidate_history_cache()
        return record_id, True


def _normalize_keyword(keyword: str | None) -> str:
    return (keyword or "").strip()


def _invalidate_history_cache() -> None:
    get_all_records.clear()
    count_records.clear()


@st.cache_data(ttl=10, show_spinner=False)
def get_all_records(
    keyword: str = "",
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """按时间倒序返回记录；keyword 对题目摘要或模型名模糊匹配。"""
    init_db()
    sql = (
        "SELECT id, created_at, topic, model_name, word_count, stages_mask "
        "FROM history"
    )
    params: list[Any] = []
    kw_norm = _normalize_keyword(keyword)
    if kw_norm:
        kw = f"%{kw_norm}%"
        sql += " WHERE topic LIKE ? OR model_name LIKE ?"
        params.extend([kw, kw])
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


@st.cache_data(ttl=10, show_spinner=False)
def count_records(keyword: str = "") -> int:
    """符合条件的记录总数（用于分页）。"""
    init_db()
    sql = "SELECT COUNT(*) FROM history"
    params: list[Any] = []
    kw_norm = _normalize_keyword(keyword)
    if kw_norm:
        kw = f"%{kw_norm}%"
        sql += " WHERE topic LIKE ? OR model_name LIKE ?"
        params.extend([kw, kw])
    with _connect() as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def get_record_by_id(record_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM history WHERE id = ?",
            (record_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_record(record_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
        conn.commit()
        ok = cur.rowcount > 0
        if ok:
            logger.info("删除历史记录 #%d", record_id)
            _invalidate_history_cache()
        return ok


def format_stages_mask(mask: str | None) -> str:
    """将 1010 转为 S1✓ S2· S3✓ S4· 便于列表展示。"""
    m = (mask or "0000").ljust(4, "0")[:4]
    parts = []
    for i, ch in enumerate(m, start=1):
        parts.append(f"S{i}{'✓' if ch == '1' else '·'}")
    return " ".join(parts)
