"""本地 SQLite 历史库。"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any

from utils.config import get_project_root

from db.common import make_question_hash, topic_summary

logger = logging.getLogger("app.db.sqlite")

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
    for ddl in (
        "ALTER TABLE history ADD COLUMN stages_mask TEXT NOT NULL DEFAULT '0000'",
        "ALTER TABLE history ADD COLUMN question_hash TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE history ADD COLUMN raw_input TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE history ADD COLUMN owner_id TEXT NOT NULL DEFAULT ''",
    ):
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_question_model "
        "ON history(question_hash, model_name)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_history_owner_created "
        "ON history(owner_id, id DESC)"
    )


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _ensure_schema(conn)
        conn.commit()


def _owner_filter(owner_id: str, admin: bool) -> tuple[str, list[Any]]:
    if admin:
        return "", []
    return " AND owner_id = ?", [owner_id]


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
        cur = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input, owner_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        )
        conn.commit()
        record_id = int(cur.lastrowid)
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
        row = conn.execute(
            """
            SELECT id FROM history
            WHERE owner_id = ? AND question_hash = ? AND model_name = ?
            ORDER BY id DESC LIMIT 1
            """,
            (owner_id, q_hash, model_name),
        ).fetchone()

        if row:
            record_id = int(row[0])
            conn.execute(
                """
                UPDATE history
                SET created_at = ?, topic = ?, full_content = ?, word_count = ?,
                    stages_mask = ?, question_hash = ?, raw_input = ?
                WHERE id = ? AND owner_id = ?
                """,
                (now, topic, content, wc, mask, q_hash, raw, record_id, owner_id),
            )
            conn.commit()
            logger.info("备课包已更新 #%d", record_id)
            return record_id, False

        cur = conn.execute(
            """
            INSERT INTO history (
                created_at, topic, model_name, full_content, word_count, stages_mask,
                question_hash, raw_input, owner_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (now, topic, model_name, content, wc, mask, q_hash, raw, owner_id),
        )
        conn.commit()
        record_id = int(cur.lastrowid)
        logger.info("备课包已新建 #%d owner=%s", record_id, owner_id[:8])
        return record_id, True


def get_all_records(
    keyword: str,
    *,
    limit: int,
    offset: int,
    owner_id: str,
    admin: bool,
) -> list[dict[str, Any]]:
    init_db()
    sql = (
        "SELECT id, created_at, topic, model_name, word_count, stages_mask, owner_id "
        "FROM history WHERE 1=1"
    )
    params: list[Any] = []
    owner_sql, owner_params = _owner_filter(owner_id, admin)
    sql += owner_sql
    params.extend(owner_params)
    kw = (keyword or "").strip()
    if kw:
        sql += " AND (topic LIKE ? OR model_name LIKE ?)"
        params.extend([f"%{kw}%", f"%{kw}%"])
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def count_records(keyword: str, *, owner_id: str, admin: bool) -> int:
    init_db()
    sql = "SELECT COUNT(*) FROM history WHERE 1=1"
    params: list[Any] = []
    owner_sql, owner_params = _owner_filter(owner_id, admin)
    sql += owner_sql
    params.extend(owner_params)
    kw = (keyword or "").strip()
    if kw:
        sql += " AND (topic LIKE ? OR model_name LIKE ?)"
        params.extend([f"%{kw}%", f"%{kw}%"])
    with _connect() as conn:
        return int(conn.execute(sql, params).fetchone()[0])


def get_record_by_id(
    record_id: int, *, owner_id: str, admin: bool
) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        if admin:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ?",
                (record_id,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM history WHERE id = ? AND owner_id = ?",
                (record_id, owner_id),
            ).fetchone()
    return dict(row) if row else None


def delete_record(record_id: int, *, owner_id: str, admin: bool) -> bool:
    init_db()
    with _connect() as conn:
        if admin:
            cur = conn.execute("DELETE FROM history WHERE id = ?", (record_id,))
        else:
            cur = conn.execute(
                "DELETE FROM history WHERE id = ? AND owner_id = ?",
                (record_id, owner_id),
            )
        conn.commit()
        ok = cur.rowcount > 0
        if ok:
            logger.info("删除历史记录 #%d", record_id)
        return ok
