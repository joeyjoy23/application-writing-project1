"""Stage 2/3 错开并行调度测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui.run_manager import (
    _begin_parallel_23,
    _maybe_start_parallel_s3,
    _parallel_all_workers_done,
    _should_use_parallel_23,
    _stage3_parallel_delay_seconds,
)
from workflow import Stage1Result, Stage2Result, Stage3Result, WorkflowState


def test_stage3_parallel_delay_default():
    with patch.dict("os.environ", {}, clear=False):
        assert _stage3_parallel_delay_seconds() == 3.0


def test_should_use_parallel_23_when_stages_are_2_then_3():
    job = {"stage_index": 1, "stages": [1, 2, 3, 4], "parallel_23": False}
    assert _should_use_parallel_23(job) is True


def test_should_not_parallel_when_only_stage2():
    job = {"stage_index": 0, "stages": [2], "parallel_23": False}
    assert _should_use_parallel_23(job) is False


def test_begin_parallel_23_both_cached_skips_api(monkeypatch: pytest.MonkeyPatch):
    state = WorkflowState(question="Q")
    state.stage1 = Stage1Result(raw="", structured_json={"k": 1}, human_summary="s1")
    job: dict = {"phase": "api", "stage_index": 1, "stages": [1, 2, 3, 4]}
    ui = MagicMock()

    c2 = Stage2Result(raw="s2")
    c3 = Stage3Result(raw="s3")
    monkeypatch.setattr("ui.run_manager.try_load_cached_stage", lambda *a, **k: c2 if a[1] == 2 else c3)
    monkeypatch.setattr(
        "ui.run_manager.st.session_state",
        MagicMock(workflow_state=None),
    )

    assert _begin_parallel_23(job, state, ui) is True
    assert job["phase"] == "flush"
    assert job["pending_flushes"] == [2, 3]
    assert state.stage2 is c2
    assert state.stage3 is c3


def test_begin_parallel_23_s2_api_sets_s3_delay(monkeypatch: pytest.MonkeyPatch):
    state = WorkflowState(question="Q")
    state.stage1 = Stage1Result(raw="", structured_json={"k": 1}, human_summary="s1")
    job: dict = {
        "phase": "api",
        "stage_index": 1,
        "stages": [1, 2, 3, 4],
        "cancel_event": __import__("threading").Event(),
        "locked_model": "test-model",
    }
    ui = MagicMock()
    started: list[int] = []

    def fake_start(j, stage, _state):
        started.append(stage)
        w = j["parallel_workers"][stage]
        w["thread_done"] = True
        w["thread_result"] = Stage2Result(raw="s2") if stage == 2 else Stage3Result(raw="s3")

    monkeypatch.setattr("ui.run_manager.try_load_cached_stage", lambda *a, **k: None)
    monkeypatch.setattr("ui.run_manager._start_parallel_worker", fake_start)
    monkeypatch.setattr(
        "ui.run_manager.st.session_state",
        MagicMock(workflow_state=None),
    )

    t0 = 1000.0
    with patch("ui.run_manager.time.time", return_value=t0):
        assert _begin_parallel_23(job, state, ui) is True

    assert job["parallel_23"] is True
    assert started == [2]
    assert job["parallel_s3_start_at"] == t0 + 3.0


def test_begin_parallel_23_s2_cached_s3_immediate(monkeypatch: pytest.MonkeyPatch):
    state = WorkflowState(question="Q")
    state.stage1 = Stage1Result(raw="", structured_json={"k": 1}, human_summary="s1")
    job: dict = {
        "phase": "api",
        "stage_index": 1,
        "stages": [1, 2, 3, 4],
        "cancel_event": __import__("threading").Event(),
        "locked_model": "test-model",
    }
    ui = MagicMock()
    c2 = Stage2Result(raw="s2")

    monkeypatch.setattr(
        "ui.run_manager.try_load_cached_stage",
        lambda *a, **k: c2 if a[1] == 2 else None,
    )
    monkeypatch.setattr("ui.run_manager._start_parallel_worker", MagicMock())
    monkeypatch.setattr(
        "ui.run_manager.st.session_state",
        MagicMock(workflow_state=None),
    )

    t0 = 2000.0
    with patch("ui.run_manager.time.time", return_value=t0):
        assert _begin_parallel_23(job, state, ui) is True

    assert state.stage2 is c2
    assert job["parallel_s3_start_at"] == t0


def test_maybe_start_parallel_s3_waits_until_delay(monkeypatch: pytest.MonkeyPatch):
    state = WorkflowState(question="Q")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="s1")
    job = {
        "parallel_23": True,
        "parallel_workers": {
            2: {"thread_done": False, "thread": MagicMock(is_alive=lambda: True), "from_cache": False},
            3: {"thread_done": False, "thread": None, "from_cache": False},
        },
        "parallel_s3_start_at": 5000.0,
        "cancel_event": __import__("threading").Event(),
    }
    ui = MagicMock()
    start = MagicMock()
    monkeypatch.setattr("ui.run_manager._start_parallel_worker", start)

    with patch("ui.run_manager.time.time", return_value=4999.0):
        _maybe_start_parallel_s3(job, state, ui)
    start.assert_not_called()

    with patch("ui.run_manager.time.time", return_value=5000.0):
        _maybe_start_parallel_s3(job, state, ui)
    start.assert_called_once_with(job, 3, state)


def test_parallel_all_workers_done():
    job = {
        "parallel_workers": {
            2: {"thread_done": True},
            3: {"thread_done": True},
        }
    }
    assert _parallel_all_workers_done(job) is True
