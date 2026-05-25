"""SQLite 历史记录：备课包自动存档与检索。"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from utils.config import get_project_root

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


def init_db() -> None:
    """首次运行时创建 history 表。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        _ensure_schema(conn)
        conn.commit()


def save_record(
    topic: str,
    model: str,
    content: str,
    *,
    word_count: int | None = None,
    stages_mask: str = "0000",
) -> int:
    """保存一条备课包记录，返回新记录 id。"""
    init_db()
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    wc = word_count if word_count is not None else len(content)
    mask = stages_mask if len(stages_mask) == 4 else "0000"
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO history (created_at, topic, model_name, full_content, word_count, stages_mask)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (created_at, topic.strip(), model.strip(), content, wc, mask),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_all_records(
    keyword: str | None = None,
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
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        sql += " WHERE topic LIKE ? OR model_name LIKE ?"
        params.extend([kw, kw])
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def count_records(keyword: str | None = None) -> int:
    """符合条件的记录总数（用于「加载更多」）。"""
    init_db()
    sql = "SELECT COUNT(*) FROM history"
    params: list[Any] = []
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
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
        return cur.rowcount > 0


def format_stages_mask(mask: str | None) -> str:
    """将 1010 转为 S1✓ S2· S3✓ S4· 便于列表展示。"""
    m = (mask or "0000").ljust(4, "0")[:4]
    parts = []
    for i, ch in enumerate(m, start=1):
        parts.append(f"S{i}{'✓' if ch == '1' else '·'}")
    return " ".join(parts)
