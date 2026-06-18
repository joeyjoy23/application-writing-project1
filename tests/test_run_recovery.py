"""运行断点恢复与 guest_id 持久化。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from db import sqlite_backend
from services.api_key_persist import build_storage_payload, parse_storage_payload
from services.run_recovery import (
    persist_run_checkpoint,
    try_recover_session_from_checkpoint,
)
from workflow import Stage1Result, WorkflowState


@pytest.fixture
def temp_sqlite_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "test_recovery.db"
    monkeypatch.setattr(sqlite_backend, "DB_PATH", db_path)
    monkeypatch.setattr(sqlite_backend, "_schema_ensured", False)
    sqlite_backend.init_db()
    yield db_path


def test_guest_id_in_browser_storage_roundtrip():
    raw = build_storage_payload(
        remember=True,
        keys={"openai": "sk-test"},
        provider="openai",
        model="gpt-4o",
        guest_id="guest-abc-123",
    )
    prefs = parse_storage_payload(raw)
    assert prefs.guest_id == "guest-abc-123"


def test_run_checkpoint_persist_and_recover(temp_sqlite_db, monkeypatch: pytest.MonkeyPatch):
    import streamlit as st
    from types import SimpleNamespace

    ss = SimpleNamespace(
        run_job=None,
        _checkpoint_recovered=False,
        workflow_state=None,
        is_running=False,
        last_question="",
        question="",
        question_image=None,
        current_history_record_id=None,
    )
    ss.get = lambda key, default=None: getattr(ss, key, default)
    monkeypatch.setattr(st, "session_state", ss)

    owner = "guest-recover-1"
    state = WorkflowState(question="题目A")
    state.stage1 = Stage1Result(
        raw="",
        structured_json={"recognized_question_text": "题目A"},
        human_summary="summary",
    )
    job = {
        "question": "题目A",
        "locked_provider": "dashscope",
        "locked_model": "qwen-plus",
        "mode": "full",
        "stages": [1, 2, 3, 4],
        "stage_index": 0,
        "stream_stage": 1,
        "stream_total": 0,
        "stream_preview": "",
        "student_level": "中等",
    }
    persist_run_checkpoint(owner, job, state, run_status="running")

    row = sqlite_backend.get_run_checkpoint(owner)
    assert row is not None

    msg = try_recover_session_from_checkpoint(owner)
    assert msg is not None
    assert ss.workflow_state is not None
    assert ss.workflow_state.stage1 is not None
