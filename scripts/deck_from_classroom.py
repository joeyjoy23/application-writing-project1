"""Build V2 slide specs from parsed classroom HTML + analysis export + stage3."""

from __future__ import annotations

from typing import Any

from scripts.architecture_v1 import (
    _extract_essay_block,
    _peel_from_stage2,
    inject_module_dividers,
)
from scripts.classroom_content_filter import (
    parse_stage4_student_from_export,
    stage1_thinking_slides_from_export,
    student_bullets_from_slide,
)


def _stage_tag_module(tag: str) -> str:
    if "stage 1" in tag.lower() or "题目" in tag:
        return "B"
    if "stage 2" in tag.lower():
        return "D"
    if "stage 3" in tag.lower():
        return "E"
    if "stage 4" in tag.lower():
        return "F"
    if tag.startswith("Joyverse") or "封面" in tag:
        return "A"
    return "A"


def _content_title(slide: dict[str, Any]) -> str:
    h2 = slide.get("h2") or slide.get("h1") or slide.get("data_title", "")
    tag = slide.get("tag", "")
    if "Stage 1" in tag:
        return f"审题 · {h2}" if not h2.startswith("审题") else h2
    if "Stage 2" in tag and "PEEL" not in tag:
        return f"范文 · {h2}" if "范文" not in h2 else h2
    return h2 or slide.get("data_title", "内容")


def _essay_from_export(stage2: str, label: str) -> str:
    text = _extract_essay_block(stage2, label)
    if text:
        return text
    if label == "基础版":
        text = _extract_essay_block(stage2, "基础")
    return text


def _inject_module_c_if_missing(specs: list[dict], stage1: str) -> None:
    if any(s.get("_module") == "C" for s in specs):
        return
    insert_at = next((i for i, s in enumerate(specs) if s.get("_module") == "D"), len(specs))
    for j, slide in enumerate(stage1_thinking_slides_from_export(stage1)):
        specs.insert(insert_at + j, slide)


def classroom_to_deck(
    classroom: dict[str, Any],
    export_data: dict[str, Any],
    stage3_specs: list[dict],
) -> list[dict]:
    """Map classroom HTML slides → V2 specs; Stage3 from stage3.json."""
    stage1 = (export_data.get("stage1") or "").strip()
    stage2 = (export_data.get("stage2") or "").strip()
    stage4 = (export_data.get("stage4") or "").strip()
    s4_student = parse_stage4_student_from_export(stage4)

    qtype = (
        export_data.get("question_type_label")
        or classroom.get("question_type_label")
        or "应用文"
    )
    specs: list[dict] = []
    skip_titles = {"句型", "词块", "结束"}

    for slide in classroom.get("slides", []):
        dt = slide.get("data_title", "")
        if dt in skip_titles or any(x in dt for x in skip_titles):
            if dt == "结束":
                specs.append(
                    {
                        "type": "content",
                        "title": "课堂小结 · 带走什么",
                        "bullets": [
                            slide.get("h1", "本课要点已覆盖：审题 → 范文 → 句型 → 迁移"),
                            "课后：背诵功能句型 + 话题词块，完成迁移练",
                        ],
                        "_module": "G",
                    }
                )
            continue

        mod = _stage_tag_module(slide.get("tag", ""))

        if dt == "封面":
            continue

        if dt == "题目":
            body = student_bullets_from_slide(slide, max_items=6)
            if not body and slide.get("cards"):
                body = [slide["cards"][0]]
            q = (export_data.get("question") or "").strip()
            if q and not body:
                body = [q.splitlines()[0][:140]]
            specs.append(
                {
                    "type": "title",
                    "title": f"高考英语应用文 · {qtype}",
                    "subtitle": slide.get("h2") or "读题 · 明确任务",
                    "body": body,
                    "_module": "A",
                }
            )
            continue

        if dt == "PEEL" or "PEEL" in slide.get("tag", ""):
            points = _peel_from_stage2(stage2) if stage2.strip() else []
            if not points or "…" in (points[0].get("p") or ""):
                points = _peel_from_slide_fallback(slide)
            specs.append(
                {
                    "type": "peel",
                    "title": slide.get("h2") or "PEEL 写作骨架",
                    "points": points,
                    "_module": "D",
                }
            )
            continue

        if dt == "基础版":
            essay = _essay_from_export(stage2, "基础版") or slide.get("en", "")
            specs.append(
                {
                    "type": "essay",
                    "title": "基础版范文 · 9分档",
                    "essay_text": essay or "（见分析报告 Stage2 基础版）",
                    "annotation": "",
                    "_module": "D",
                }
            )
            continue

        if dt == "对比" and slide.get("table_rows"):
            rows = slide.get("table_rows")
            if rows:
                specs.append(
                    {
                        "type": "table",
                        "title": slide.get("h2") or "三版对比要点",
                        "headers": ["维度", "基础版", "高分版 A", "高分版 B"],
                        "rows": [
                            [
                                "句式",
                                rows[0][1] if rows else "",
                                rows[1][1] if len(rows) > 1 else "",
                                rows[2][1] if len(rows) > 2 else "",
                            ],
                            [
                                "适合",
                                rows[0][2] if rows else "",
                                rows[1][2] if len(rows) > 1 else "",
                                rows[2][2] if len(rows) > 2 else "",
                            ],
                        ],
                        "_module": "D",
                    }
                )
            continue

        if dt in ("高分A", "高分B"):
            label = "进阶版" if dt == "高分A" else "高分版 B"
            essay = _essay_from_export(stage2, label) or _essay_from_export(stage2, "高分版")
            if essay and "Dear " in essay:
                specs.append(
                    {
                        "type": "essay",
                        "title": f"{'高分版 A' if dt == '高分A' else '高分版 B'} · {'情感共鸣' if dt == '高分A' else '逻辑思辨'}",
                        "essay_text": essay,
                        "annotation": "",
                        "_module": "D",
                    }
                )
            else:
                specs.append(
                    {
                        "type": "content",
                        "title": _content_title(slide),
                        "bullets": student_bullets_from_slide(slide),
                        "_module": "D",
                    }
                )
            continue

        if "易错" in dt or "易错" in slide.get("tag", ""):
            bullets = s4_student["warn"] or student_bullets_from_slide(
                slide, include_insight_quote=False
            )
            specs.append(
                {
                    "type": "content",
                    "title": slide.get("h2") or "动笔易错",
                    "badge": "动笔易错",
                    "warn_panel": True,
                    "panel": True,
                    "bullets": bullets,
                    "_module": "F",
                }
            )
            continue

        if "活动" in dt or "教学" in slide.get("tag", ""):
            bullets = s4_student["activities"] or student_bullets_from_slide(
                slide, include_insight_quote=False
            )
            specs.append(
                {
                    "type": "content",
                    "title": "练一练 · 元素与逻辑",
                    "badge": "当堂操练",
                    "bullets": bullets,
                    "_module": "F",
                }
            )
            continue

        if "迁移" in dt:
            bullets = s4_student["migration"] or student_bullets_from_slide(
                slide, include_insight_quote=False
            )
            specs.append(
                {
                    "type": "content",
                    "title": slide.get("h2") or "当堂迁移",
                    "badge": "迁移练",
                    "bullets": bullets,
                    "_module": "F",
                }
            )
            continue

        bullets = student_bullets_from_slide(slide)
        if not bullets:
            continue
        specs.append(
            {
                "type": "content",
                "title": _content_title(slide),
                "bullets": bullets,
                "_module": mod,
            }
        )

    _inject_module_c_if_missing(specs, stage1)

    insert_at = len(specs)
    for i, s in enumerate(specs):
        if s.get("_module") == "F" and "迁移" in s.get("title", ""):
            insert_at = i
            break
        if s.get("_module") == "F":
            insert_at = i
    for j, s3 in enumerate(stage3_specs):
        s3["_module"] = "E"
        specs.insert(insert_at + j, s3)

    return inject_module_dividers(specs)


def _peel_from_slide_fallback(slide: dict[str, Any]) -> list[dict]:
    """Fallback PEEL points from classroom HTML cards when export is empty."""
    cards = slide.get("cards") or []
    points: list[dict] = []
    for i, card in enumerate(cards[:2]):
        lines = [ln.strip() for ln in card.split("\n") if ln.strip()]
        p_text = ""
        e_items: list[str] = []
        for ln in lines:
            if ln.startswith('"') or "I'd" in ln or "The " in ln:
                p_text = ln.strip('"')
            elif "具体化" in ln or "因果" in ln:
                e_items.append(ln.split("：", 1)[-1].strip())
            elif not p_text:
                p_text = ln
            else:
                e_items.append(ln)
        points.append(
            {
                "label": f"Point {i + 1}",
                "p": p_text or (lines[0] if lines else ""),
                "e_items": e_items or lines[1:3],
                "l": "",
            }
        )
    return points or [
        {
            "label": "Point 1",
            "p": "I'd go with Poster 1.",
            "e_items": ["cracked heart + smile + slogan"],
            "l": "Here's why.",
        },
        {
            "label": "Point 2",
            "p": "The design captures the theme.",
            "e_items": ["元素 → 主题 → 共鸣"],
            "l": "Overall …",
        },
    ]
