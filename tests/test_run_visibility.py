"""运行中 Stage 占位逻辑（无 Streamlit）。"""

from ui.run_manager import (
    _resolve_paint_mode,
    _running_stages_for_job,
    _slot_paint_plan,
)
from ui.run_cache import should_parallel_stage23
from workflow import Stage1Result, WorkflowState


def test_running_stages_parallel_23():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    job = {
        "phase": "api",
        "thread": _AliveThread(),
        "mode": "full",
        "stages": [1, 2, 3, 4],
        "stage_index": 1,
    }
    assert should_parallel_stage23(job)
    assert _running_stages_for_job(job, state) == {2, 3}


def test_running_stages_single_stage2():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    job = {
        "phase": "api",
        "thread": _AliveThread(),
        "mode": "stage2",
        "stages": [2],
        "stage_index": 0,
    }
    assert _running_stages_for_job(job, state) == {2}


def test_slot_paint_plan_incremental_skips_completed_stage1():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    plan = _slot_paint_plan(state, {2, 3}, incremental=True)
    assert plan[0] is None
    assert plan[1] == "in_progress"
    assert plan[2] == "in_progress"
    assert plan[3] is None


def test_slot_paint_plan_full_repaints_completed():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    plan = _slot_paint_plan(state, {2}, incremental=False)
    assert plan[0] == "content"
    assert plan[1] == "in_progress"


def test_resolve_paint_mode_full_after_slot_recreation():
    job: dict = {}
    slots_a = (_Slot(), _Slot(), _Slot(), _Slot())
    assert _resolve_paint_mode(slots_a, job, "incremental") == "incremental"
    slots_b = (_Slot(), _Slot(), _Slot(), _Slot())
    assert _resolve_paint_mode(slots_b, job, "incremental") == "full"


def test_resolve_paint_mode_incremental_same_slots():
    job: dict = {}
    slots = (_Slot(), _Slot(), _Slot(), _Slot())
    assert _resolve_paint_mode(slots, job, "incremental") == "incremental"
    assert _resolve_paint_mode(slots, job, "incremental") == "incremental"


class _Slot:
    pass


class _AliveThread:
    def is_alive(self) -> bool:
        return True
