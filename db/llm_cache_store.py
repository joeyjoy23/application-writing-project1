"""LLM 阶段结果缓存：序列化与反序列化。"""

from __future__ import annotations

import json
from typing import Any

from workflow import Stage1Result, Stage2Result, Stage3Result, Stage4Result


def serialize_stage_result(stage: int, result: Any) -> str:
    if stage == 1:
        assert isinstance(result, Stage1Result)
        payload = {
            "kind": "stage1",
            "raw": result.raw,
            "structured_json": result.structured_json,
            "human_summary": result.human_summary,
        }
    elif stage == 2:
        assert isinstance(result, Stage2Result)
        payload = {"kind": "stage2", "raw": result.raw}
    elif stage == 3:
        assert isinstance(result, Stage3Result)
        payload = {"kind": "stage3", "raw": result.raw}
    elif stage == 4:
        assert isinstance(result, Stage4Result)
        payload = {"kind": "stage4", "raw": result.raw}
    else:
        raise ValueError(f"invalid stage: {stage}")
    return json.dumps(payload, ensure_ascii=False)


def deserialize_stage_result(stage: int, content: str) -> Any:
    payload = json.loads(content)
    kind = payload.get("kind")
    if stage == 1 and kind == "stage1":
        return Stage1Result(
            raw=payload["raw"],
            structured_json=payload["structured_json"],
            human_summary=payload.get("human_summary", ""),
        )
    if stage == 2 and kind == "stage2":
        return Stage2Result(raw=payload["raw"])
    if stage == 3 and kind == "stage3":
        return Stage3Result(raw=payload["raw"])
    if stage == 4 and kind == "stage4":
        return Stage4Result(raw=payload["raw"])
    raise ValueError(f"缓存内容与 stage {stage} 不匹配")
