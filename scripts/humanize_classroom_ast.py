"""Map Humanize PPT slide_plan + speaker_intent to 应用文 classroom HTML slides.

Architecture V1 (70min) owns page allocation and full export content.
Humanize owns per-module audience state transfer (AST) and speaker notes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# 高考英语应用文课堂 — 观众是后排学生投影，不是 Agent 开发者
CLASSROOM_AUDIENCE = "高三学生（后排投影可读）"
CLASSROOM_INITIAL_STATE = "知道题目要求，但审题不准、理由空泛、句式单一"
CLASSROOM_DESIRED_STATE = "能三元审题、PEEL 成段、背诵本题句型并完成迁移"
CLASSROOM_CORE_TENSION = "资料很全，但一页塞太多反而看不清、记不住"

ROLE_LABELS: dict[str, str] = {
    "hook": "钩子",
    "context": "背景",
    "tension": "张力",
    "method": "方法",
    "proof": "证据",
    "takeaway": "收束",
}

ROLE_LEAVE_STATE: dict[str, str] = {
    "hook": "愿意看题、进入情境",
    "context": "读懂任务与交际对象",
    "tension": "意识到易错点，想写对",
    "method": "看到 PEEL 路径与范文差异",
    "proof": "相信句型词块能直接套用",
    "takeaway": "带走高分公式，能当堂练",
}

ROLE_ORDER: tuple[str, ...] = ("hook", "context", "tension", "method", "proof", "takeaway")


def load_slide_plan(path: Path | None) -> list[dict[str, Any]]:
    if not path or not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(raw, dict):
        raw = raw.get("slides") or []
    return raw if isinstance(raw, list) else []


def parse_speaker_intent_md(path: Path | None) -> dict[str, str]:
    """Parse `## S01 Title` sections → {slide_id: intent line}."""
    if not path or not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    section_id = ""
    for line in text.splitlines():
        m = re.match(r"^##\s+(S\d+)\s+", line)
        if m:
            section_id = m.group(1).upper()
            continue
        if section_id and line.strip().startswith("- Intent:"):
            out[section_id] = line.split(":", 1)[-1].strip()
    return out


def _plan_by_role(plan: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_role: dict[str, dict[str, Any]] = {}
    for slide in plan:
        role = (slide.get("role") or "").strip()
        if role and role not in by_role:
            by_role[role] = slide
    return by_role


def _plan_by_id(plan: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        (s.get("slide_id") or "").upper(): s
        for s in plan
        if s.get("slide_id")
    }


def humanize_role_for_tag(tag: str, *, variant: str = "", title: str = "") -> str:
    """Map rendered slide tag/title → Humanize AST role."""
    if variant == "hero" or title.startswith("导入 · 真题"):
        return "hook"
    if tag == "导入":
        return "context"
    if tag == "Stage 1":
        return "tension"
    if tag == "Stage 2":
        return "method"
    if tag == "Stage 3":
        return "proof"
    if tag in ("Stage 4", "训练"):
        return "takeaway"
    if tag == "总结":
        return "takeaway"
    return "context"


def _enter_state_for_role(role: str, prev_leave: str) -> str:
    idx = ROLE_ORDER.index(role) if role in ROLE_ORDER else 0
    if idx == 0:
        return CLASSROOM_INITIAL_STATE
    prev_role = ROLE_ORDER[idx - 1]
    return ROLE_LEAVE_STATE.get(prev_role, prev_leave)


def enrich_specs_with_ast(
    specs: list[dict[str, Any]],
    *,
    slide_plan_path: Path | None = None,
    speaker_intent_path: Path | None = None,
) -> None:
    """Attach audience_in/out, one_thing, speaker_intent to each HTML slide spec."""
    plan = load_slide_plan(slide_plan_path)
    intents = parse_speaker_intent_md(speaker_intent_path)
    by_role = _plan_by_role(plan)
    by_id = _plan_by_id(plan)

    prev_leave = CLASSROOM_INITIAL_STATE
    last_role = ""

    for spec in specs:
        role = humanize_role_for_tag(
            spec.get("tag", ""),
            variant=spec.get("variant", ""),
            title=spec.get("title", ""),
        )
        macro = by_role.get(role) or {}
        slide_id = (macro.get("slide_id") or "").upper()

        audience_in = _enter_state_for_role(role, prev_leave) if role != last_role else prev_leave
        audience_out = ROLE_LEAVE_STATE.get(role, audience_in)
        one_thing = (
            macro.get("speaker_intent")
            or intents.get(slide_id, "")
            or macro.get("message", "")
            or f"完成「{ROLE_LABELS.get(role, role)}」状态转移"
        )

        spec["ast_role"] = role
        spec["ast_role_label"] = ROLE_LABELS.get(role, role)
        spec["audience_in"] = audience_in
        spec["audience_out"] = audience_out
        spec["one_thing"] = one_thing.strip()
        spec["speaker_intent"] = one_thing.strip()
        spec["humanize_slide_id"] = slide_id or role.upper()

        if role != last_role:
            prev_leave = audience_out
            last_role = role


def speaker_note_entries(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": i + 1,
            "title": s.get("title", ""),
            "tag": s.get("tag", ""),
            "role": s.get("ast_role", ""),
            "role_label": s.get("ast_role_label", ""),
            "audience_in": s.get("audience_in", ""),
            "audience_out": s.get("audience_out", ""),
            "one_thing": s.get("one_thing", ""),
            "speaker_intent": s.get("speaker_intent", ""),
        }
        for i, s in enumerate(specs)
    ]


def classroom_ast_header() -> dict[str, str]:
    return {
        "audience": CLASSROOM_AUDIENCE,
        "initial_state": CLASSROOM_INITIAL_STATE,
        "desired_state": CLASSROOM_DESIRED_STATE,
        "core_tension": CLASSROOM_CORE_TENSION,
    }
