"""历史原图 7 天保留与过期清理。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from db import sqlite_backend
from utils.history_image import (
    history_image_expires_at,
    history_image_retention_days,
    history_image_row_to_session,
    is_history_image_expired,
)


@pytest.fixture
def temp_sqlite_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_history.db"
    monkeypatch.setattr(sqlite_backend, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_backend, "_schema_ensured", False)
    sqlite_backend.init_db()
    yield db_path


def _insert_history(owner_id: str) -> int:
    with sqlite3.connect(sqlite_backend.DB_PATH) as conn:
        cur = conn.execute(
            """
            INSERT INTO history (
                owner_id, created_at, topic, model_name, full_content,
                word_count, stages_mask, question_hash, raw_input
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                owner_id,
                "2026-06-01 00:00:00",
                "Write a letter",
                "gpt-4o",
                "{}",
                10,
                "1000",
                "hash1",
                "Write a letter\n[图：海报]",
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def test_history_image_retention_defaults_to_seven_days():
    assert history_image_retention_days() == 7


def test_history_image_expires_at_from_base():
    exp = history_image_expires_at(from_utc="2026-06-01 00:00:00")
    assert exp == "2026-06-08 00:00:00"


def test_is_history_image_expired():
    past = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    assert is_history_image_expired(past) is True
    assert is_history_image_expired(future) is False


def test_save_and_get_history_question_image(temp_sqlite_db):
    owner = "guest-img-1"
    rid = _insert_history(owner)
    sqlite_backend.save_history_question_image(
        rid,
        owner_id=owner,
        mime="image/jpeg",
        image_b64="abc123",
    )
    row = sqlite_backend.get_history_question_image(rid, owner_id=owner, admin=False)
    assert row is not None
    assert row["image_b64"] == "abc123"
    session = history_image_row_to_session(row)
    assert session["b64"] == "abc123"
    assert session["mime"] == "image/jpeg"


def test_expired_image_removed_on_get(temp_sqlite_db):
    owner = "guest-img-2"
    rid = _insert_history(owner)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(sqlite_backend.DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO history_question_images (
                history_id, owner_id, mime, image_b64, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rid, owner, "image/jpeg", "old", past, past),
        )
        conn.commit()
    assert sqlite_backend.get_history_question_image(rid, owner_id=owner, admin=False) is None
    with sqlite3.connect(sqlite_backend.DB_PATH) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM history_question_images WHERE history_id = ?",
            (rid,),
        ).fetchone()[0]
    assert n == 0


def test_purge_expired_history_question_images(temp_sqlite_db):
    owner = "guest-img-3"
    rid = _insert_history(owner)
    past = (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")
    with sqlite3.connect(sqlite_backend.DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO history_question_images (
                history_id, owner_id, mime, image_b64, expires_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (rid, owner, "image/jpeg", "purge-me", past, past),
        )
        conn.commit()
    n = sqlite_backend.purge_expired_history_question_images()
    assert n >= 1
    assert sqlite_backend.get_history_question_image(rid, owner_id=owner, admin=False) is None


def test_delete_record_removes_image(temp_sqlite_db):
    owner = "guest-img-4"
    rid = _insert_history(owner)
    sqlite_backend.save_history_question_image(
        rid,
        owner_id=owner,
        mime="image/jpeg",
        image_b64="xyz",
    )
    assert sqlite_backend.delete_record(rid, owner_id=owner, admin=False) is True
    with sqlite3.connect(sqlite_backend.DB_PATH) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM history_question_images WHERE history_id = ?",
            (rid,),
        ).fetchone()[0]
    assert n == 0
