"""历史库 starred 筛选测试（SQLite backend）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from db import sqlite_backend


@pytest.fixture
def temp_sqlite_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_history.db"
    monkeypatch.setattr(sqlite_backend, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_backend, "_schema_ensured", False)
    sqlite_backend.init_db()
    yield db_path


def _insert(owner_id: str, topic: str, *, starred: bool = False) -> int:
    with sqlite3.connect(sqlite_backend.DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO history (
                owner_id, created_at, topic, model_name, full_content,
                word_count, stages_mask, question_hash, raw_input, is_starred
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_id,
                "2026-01-01T00:00:00Z",
                topic,
                "test-model",
                "{}",
                0,
                "1000",
                f"hash-{topic}",
                topic,
                1 if starred else 0,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def test_count_records_starred_only(temp_sqlite_db):
    owner = "guest-test-1"
    _insert(owner, "题目A")
    _insert(owner, "题目B", starred=True)

    assert sqlite_backend.count_records("", owner_id=owner, admin=False) == 2
    assert sqlite_backend.count_records("", owner_id=owner, admin=False, starred_only=True) == 1


def test_get_all_records_starred_only(temp_sqlite_db):
    owner = "guest-test-2"
    _insert(owner, "普通")
    starred_id = _insert(owner, "收藏", starred=True)

    rows = sqlite_backend.get_all_records(
        "",
        limit=20,
        offset=0,
        owner_id=owner,
        admin=False,
        starred_only=True,
    )
    assert len(rows) == 1
    assert rows[0]["id"] == starred_id
    assert rows[0]["is_starred"] == 1
