"""Build classroom slide plan from stage3.json (deterministic fallback)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.ppt_layout_fit import (
    LAYOUT_REGISTRY,
    fit_banner,
    fit_fix_cards,
    fit_vocab_chunk,
    phrase_table_body_heights,
)

_TIER_SLUG = {"必备级": "basic", "进阶级": "advanced", "亮点级": "highlight"}
_FIELD_SHORT = (
    ("观点", "观点表达", "opinion"),
    ("设计", "设计元素", "design"),
    ("健康", "心理健康主题", "theme"),
    ("主题", "心理健康主题", "theme"),
)
_PHRASE_COL_FRACS = [0.14, 0.52, 0.34]


def _short_field(name: str) -> tuple[str, str]:
    for key, short, slug in _FIELD_SHORT:
        if key in name:
            return short, slug
    slug = "field"
    return name[:10], slug


def _resolve_phrase(data: dict[str, Any], source: str) -> dict[str, Any]:
    m = __import__("re").match(r"phrase_tables\[(\d+)\]", source)
    if not m:
        raise ValueError(f"bad phrase source: {source}")
    return data["phrase_tables"][int(m.group(1))]


def _resolve_vocab(data: dict[str, Any], source: str) -> tuple[dict[str, Any], list[dict]]:
    m = __import__("re").match(r"vocab_fields\[(\d+)\]\.tiers\[(\d+)\]", source)
    if not m:
        raise ValueError(f"bad vocab source: {source}")
    field = data["vocab_fields"][int(m.group(1))]
    tier = field["tiers"][int(m.group(2))]
    return field, tier


def _vocab_columns(tier_level: str) -> list[str]:
    if tier_level == "必备级":
        return ["english", "example"]
    return ["english", "chinese", "example"]


def _chunk_vocab_rows(
    rows: list[dict],
    columns: list[str],
    *,
    max_rows: int = 6,
) -> list[list[dict]]:
    """Split vocab rows by layout_fit measurement, capped at max_rows per chunk."""
    if not rows:
        return [[]]
    budget = LAYOUT_REGISTRY["vocab_table"]
    chunks: list[list[dict]] = []
    current: list[dict] = []
    for row in rows:
        trial = current + [row]
        _, _, _, needs_split = fit_vocab_chunk(trial, columns, budget)
        over_cap = len(trial) > max_rows
        if (needs_split or over_cap) and current:
            chunks.append(current)
            current = [row]
        elif needs_split or over_cap:
            chunks.append([row])
            current = []
        else:
            current = trial
    if current:
        chunks.append(current)
    return chunks or [[]]


def _footer_needs_split(table: dict, *, fix_only: bool = False) -> bool:
    budget = LAYOUT_REGISTRY["phrase_table_footer"]
    if not fix_only and table.get("topic_note"):
        if fit_banner(table["topic_note"], budget).needs_split:
            return True
    if table.get("fix_bad") or table.get("fix_good"):
        left = ("别这样写\n" + table.get("fix_bad", "")).strip()
        right = ("改成\n" + table.get("fix_good", "").lstrip("→").strip()).strip()
        avail = budget.content_height(with_banner=not fix_only and bool(table.get("topic_note")))
        if fix_only:
            avail = budget.content_height(with_banner=False) + budget.key_banner
        layout = fit_fix_cards(left, right, avail_height=avail)
        if layout.mode == "needs_split":
            return True
    return False


def _footer_fix_split_parts(table: dict) -> list[str]:
    """When fix cards cannot fit even stacked, one card per slide."""
    parts: list[str] = []
    if table.get("fix_bad"):
        parts.append("fix_bad")
    if table.get("fix_good"):
        parts.append("fix_good")
    return parts


def _phrase_body_needs_split(table: dict) -> bool:
    _, _, _, split = phrase_table_body_heights(
        table.get("tiers", []),
        _PHRASE_COL_FRACS,
        LAYOUT_REGISTRY["phrase_table_body"],
    )
    return split


def validate_slide_fit(slide: dict[str, Any], data: dict[str, Any]) -> bool:
    """Return True if slide content fits its layout budget."""
    layout = slide["layout"]
    if layout == "phrase_table_body":
        table = _resolve_phrase(data, slide["source"])
        return not _phrase_body_needs_split(table)
    if layout == "phrase_table_footer":
        table = _resolve_phrase(data, slide["source"])
        return not _footer_needs_split(table)
    if layout == "vocab_table":
        rows = slide.get("rows")
        if rows is None:
            _, tier = _resolve_vocab(data, slide["source"])
            rows = tier.get("rows", [])
        cols = slide.get("columns") or _vocab_columns(
            slide.get("tier", "") or slide["title"]
        )
        _, _, _, split = fit_vocab_chunk(rows, cols, LAYOUT_REGISTRY["vocab_table"])
        return not split
    return True


def refine_deck_plan(
    data: dict[str, Any],
    plan: dict[str, Any],
    *,
    vocab_max_rows: int = 6,
) -> dict[str, Any]:
    """Re-split slides using layout_fit measurement (e.g. after overflow retry)."""
    refined: list[dict[str, Any]] = []
    for slide in plan.get("slides", []):
        layout = slide["layout"]
        if layout == "vocab_table" and slide.get("rows") is None:
            field, tier = _resolve_vocab(data, slide["source"])
            short, slug = _short_field(field["name"])
            level = tier["level"]
            cols = slide.get("columns") or _vocab_columns(level)
            chunks = _chunk_vocab_rows(tier.get("rows", []), cols, max_rows=vocab_max_rows)
            for ci, chunk in enumerate(chunks):
                suffix = f" · {level}"
                if len(chunks) > 1:
                    suffix += f" {ci + 1}/{len(chunks)}"
                refined.append(
                    {
                        "id": f"vocab_{slug}_{_TIER_SLUG.get(level, 0)}_{ci}",
                        "layout": "vocab_table",
                        "title": f"话题词块 · {short}{suffix}",
                        "source": slide["source"],
                        "columns": cols,
                        "rows": chunk,
                        "anim": slide.get("anim", "row"),
                    }
                )
        elif layout == "phrase_table_footer":
            if slide.get("footer_part"):
                refined.append(slide)
                continue
            table = _resolve_phrase(data, slide["source"])
            base = slide["title"]
            has_note = bool(table.get("topic_note"))
            has_fix = bool(table.get("fix_bad") or table.get("fix_good"))
            if has_note and has_fix and _footer_needs_split(table):
                note_slide = dict(slide)
                note_slide["id"] = slide["id"] + "_note"
                note_slide["title"] = f"{base} · 本题"
                note_slide["footer_part"] = "note"
                refined.append(note_slide)
                if _footer_needs_split(table, fix_only=True):
                    for part in _footer_fix_split_parts(table):
                        fix_slide = dict(slide)
                        fix_slide["id"] = slide["id"] + f"_{part}"
                        fix_slide["title"] = f"{base} · {'别这样写' if part == 'fix_bad' else '改成'}"
                        fix_slide["footer_part"] = part
                        refined.append(fix_slide)
                else:
                    fix_slide = dict(slide)
                    fix_slide["id"] = slide["id"] + "_fix"
                    fix_slide["title"] = f"{base} · 改错"
                    fix_slide["footer_part"] = "fix"
                    refined.append(fix_slide)
            elif has_fix and _footer_needs_split(table, fix_only=True):
                for part in _footer_fix_split_parts(table):
                    fix_slide = dict(slide)
                    fix_slide["id"] = slide["id"] + f"_{part}"
                    fix_slide["title"] = f"{base} · {'别这样写' if part == 'fix_bad' else '改成'}"
                    fix_slide["footer_part"] = part
                    refined.append(fix_slide)
            else:
                refined.append(slide)
        else:
            refined.append(slide)
    out = dict(plan)
    out["slides"] = refined
    return out


def deck_plan_from_stage3(data: dict[str, Any], *, vocab_max_rows: int = 6) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for i, table in enumerate(data.get("phrase_tables", [])):
        base = f"功能句型 · {table['name']}"
        slides.append(
            {
                "id": f"phrase_{i}_body",
                "layout": "phrase_table_body",
                "title": base,
                "source": f"phrase_tables[{i}]",
                "anim": "row",
            }
        )
        has_fix = bool(table.get("fix_bad") or table.get("fix_good"))
        has_note = bool(table.get("topic_note"))
        if has_fix:
            slides.append(
                {
                    "id": f"phrase_{i}_fix",
                    "layout": "phrase_table_footer",
                    "title": f"{base} · 改一句",
                    "source": f"phrase_tables[{i}]",
                    "footer_part": "fix",
                    "anim": "row",
                }
            )
        if has_note:
            slides.append(
                {
                    "id": f"phrase_{i}_note",
                    "layout": "phrase_table_footer",
                    "title": f"{base} · 本题",
                    "source": f"phrase_tables[{i}]",
                    "footer_part": "note",
                    "anim": "row",
                }
            )
        if not has_fix and not has_note:
            slides.append(
                {
                    "id": f"phrase_{i}_footer",
                    "layout": "phrase_table_footer",
                    "title": f"{base} · 用法与改错",
                    "source": f"phrase_tables[{i}]",
                    "anim": "row",
                }
            )
    for fi, field in enumerate(data.get("vocab_fields", [])):
        short, slug = _short_field(field["name"])
        for ti, tier in enumerate(field.get("tiers", [])):
            level = tier["level"]
            cols = _vocab_columns(level)
            rows = tier.get("rows", [])
            chunks = _chunk_vocab_rows(rows, cols, max_rows=vocab_max_rows)
            if not rows:
                chunks = [[]]
            for ci, chunk in enumerate(chunks):
                suffix = f" · {level}"
                if len(chunks) > 1:
                    suffix += f" {ci + 1}/{len(chunks)}"
                slides.append(
                    {
                        "id": f"vocab_{slug}_{_TIER_SLUG.get(level, ti)}_{ci}",
                        "layout": "vocab_table",
                        "title": f"话题词块 · {short}{suffix}",
                        "source": f"vocab_fields[{fi}].tiers[{ti}]",
                        "columns": cols,
                        "rows": chunk,
                        "anim": "row",
                    }
                )
    plan = {"version": 2, "target": "wps", "default_anim": "fade_on_click", "slides": slides}
    return refine_deck_plan(data, plan, vocab_max_rows=vocab_max_rows)


def load_deck_plan(
    path: Path | None,
    stage3_data: dict[str, Any],
    *,
    vocab_max_rows: int = 6,
) -> dict[str, Any]:
    if path and path.is_file():
        custom = json.loads(path.read_text(encoding="utf-8"))
        if custom.get("slides"):
            return refine_deck_plan(stage3_data, custom, vocab_max_rows=vocab_max_rows)
    return deck_plan_from_stage3(stage3_data, vocab_max_rows=vocab_max_rows)


def stage3_specs_from_plan(
    stage3_data: dict[str, Any], plan: dict[str, Any]
) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for slide in plan.get("slides", []):
        layout = slide["layout"]
        if layout in ("phrase_table", "phrase_table_body", "phrase_table_footer"):
            table = _resolve_phrase(stage3_data, slide["source"])
            part = "full"
            if layout == "phrase_table_body":
                part = "body"
            elif layout == "phrase_table_footer":
                part = "footer"
                footer_part = slide.get("footer_part")
                if footer_part == "note":
                    part = "footer_note"
                elif footer_part == "fix":
                    part = "footer_fix"
                elif footer_part == "fix_bad":
                    part = "footer_fix_bad"
                elif footer_part == "fix_good":
                    part = "footer_fix_good"
            specs.append(
                {
                    "type": "phrase_table",
                    "part": part,
                    "title": slide["title"],
                    "table": table,
                }
            )
        elif layout == "vocab_table":
            if slide.get("rows") is not None:
                rows = slide["rows"]
                tier_level = slide["title"].split("·")[-1].strip().split()[0]
                if "必备" in slide["title"]:
                    tier_level = "必备级"
                elif "进阶" in slide["title"]:
                    tier_level = "进阶级"
                elif "亮点" in slide["title"]:
                    tier_level = "亮点级"
                else:
                    _, tier = _resolve_vocab(stage3_data, slide["source"])
                    tier_level = tier["level"]
            else:
                _, tier = _resolve_vocab(stage3_data, slide["source"])
                rows = tier.get("rows", [])
                tier_level = tier["level"]
            cols = slide.get("columns") or _vocab_columns(tier_level)
            specs.append(
                {
                    "type": "vocab_table",
                    "title": slide["title"],
                    "tier": tier_level,
                    "rows": rows,
                    "columns": cols,
                }
            )
    return specs


def replace_stage3_in_deck(deck: list[dict], stage3_specs: list[dict]) -> list[dict]:
    """Replace slides from first 功能句型 through last 话题词块 with stage3_specs."""
    start = None
    end = None
    for i, spec in enumerate(deck):
        title = spec.get("title", "")
        if start is None and title.startswith("功能句型"):
            start = i
        if title.startswith("话题词块"):
            end = i
    if start is None:
        return deck + stage3_specs
    end = end if end is not None else start
    while end + 1 < len(deck) and deck[end + 1].get("title", "").startswith("话题词块"):
        end += 1
    return deck[:start] + stage3_specs + deck[end + 1 :]
