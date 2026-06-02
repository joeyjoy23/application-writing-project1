"""运行中 Stage 占位逻辑（无 Streamlit）。"""

from ui.run_manager import _running_stages_for_job
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


class _AliveThread:
    def is_alive(self) -> bool:
        return True
