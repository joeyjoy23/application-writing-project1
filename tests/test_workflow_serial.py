"""workflow.run_full_pipeline Stage 2→3 串行顺序。"""

from unittest.mock import MagicMock

from workflow import (
    GaokaoWritingWorkflow,
    Stage1Result,
    Stage2Result,
    Stage3Result,
    Stage4Result,
)


def test_run_full_pipeline_runs_stage2_before_stage3(monkeypatch):
    order: list[str] = []

    wf = GaokaoWritingWorkflow(client=MagicMock())
    s1 = Stage1Result(raw="", structured_json={"k": 1}, human_summary="ok")
    monkeypatch.setattr(wf, "run_stage1", lambda q: order.append("s1") or s1)
    monkeypatch.setattr(
        wf,
        "run_stage2",
        lambda q, j: order.append("s2") or Stage2Result(raw="s2"),
    )
    monkeypatch.setattr(
        wf,
        "run_stage3",
        lambda q, j: order.append("s3") or Stage3Result(raw="s3"),
    )
    monkeypatch.setattr(
        wf,
        "run_stage4",
        lambda *a, **k: order.append("s4") or Stage4Result(raw="s4"),
    )

    wf.run_full_pipeline("题目", student_level="中等")
    assert order == ["s1", "s2", "s3", "s4"]
