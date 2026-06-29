"""Classroom Script MVP — compile script JSON to render_v2_deck slide specs."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from scripts.architecture_v1 import (
    _closing_slides,
    _extract_essay_block,
    _peel_from_stage2,
    _poster_lines,
    _question_lines,
    _question_type_label,
    _self_check_five_slide_specs,
    _stage1_mistakes,
    _stage1_self_check_five,
    _stage1_tasks,
    _stage1_triplet,
    _stage4_migration,
    _stage4_review,
    _stage4_warn,
    _thinking_formula,
    _thinking_path,
    _topic_subtitle,
    _upgrade_bullets_from_stage2,
)

_SCHEMA_VERSION = "1.0"
_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

# Sources that may appear in multiple output slides but only once in sequence.bind
_MULTI_OUTPUT_SOURCES = frozenset({"question.visuals"})

_ARCHETYPE_TITLES: dict[str, str] = {
    "question_stem": "导入 · 真题展示",
    "visual_poster": "海报示意",
    "scenario_hook": "导入 · 情境代入",
    "triplet_review": "审题 · 三元审题",
    "self_check_five": "审题 · 动笔自检五问",
    "task_checklist": "审题 · 任务拆解",
    "thinking_core": "思维 · 审题与路径",
    "pitfall_contrast": "审题 · 易错对比",
    "thinking_path": "思维 · 高分路径",
    "thinking_formula": "思维 · 高分公式",
    "peel_skeleton": "PEEL 写作骨架",
    "essay_display": "范文",
    "essay_annotation": "范文 · 批注",
    "practice_migration": "当堂迁移",
    "summary_formula": "课堂小结 · 高分公式",
    "summary_homework": "课后任务",
    "stage4_review": "讲评活动 · 元素与逻辑",
    "stage4_warn": "动笔易错",
}

MIN_FONT_SIZE = 26
PREFERRED_FONT_SIZE = 28
ESSAY_MAX_CHARS = 1100
ESSAY_MAX_LINES = 24
TABLE_MAX_ROWS = 6
CONTENT_MAX_BULLETS = 3

_FONT_SIZE_ARCHETYPES = frozenset(
    {
        "essay_display",
        "phrase_table",
        "phrase_footer",
        "vocab_table",
        "thinking_path",
        "task_checklist",
        "thinking_core",
    }
)

_POSTER_LABEL_ONLY = re.compile(
    r"^(?:两张海报|海报)[：:]\s*$|^(?:Poster\s*\d*\s*[：:]?\s*)$",
    re.IGNORECASE,
)

_REDUNDANT_WORDS = re.compile(
    r"\b(really|very|actually|just|simply|quite|extremely|totally)\b",
    re.IGNORECASE,
)


class ClassroomScriptError(Exception):
    """Invalid script or compile failure."""


def load_classroom_script(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != _SCHEMA_VERSION:
        raise ClassroomScriptError(
            f"unsupported schema_version: {data.get('schema_version')!r} (expected {_SCHEMA_VERSION})"
        )
    if "sequence" not in data:
        raise ClassroomScriptError("classroom_script missing sequence")
    return data


def load_script_template(template_id: str) -> dict[str, Any]:
    path = _TEMPLATES_DIR / f"classroom_script_{template_id}.json"
    if not path.is_file():
        raise ClassroomScriptError(f"unknown template_id: {template_id} (no file {path})")
    return load_classroom_script(path)


def assert_source_exclusivity(sequence: list[dict[str, Any]]) -> None:
    """Each bind.source may appear once (visual_poster expands in compile)."""
    seen: set[str] = set()
    for item in sequence:
        bind = item.get("bind") or {}
        source = bind.get("source")
        if not source:
            continue
        if source in seen:
            raise ClassroomScriptError(
                f"source exclusivity conflict: {source!r} bound by more than one archetype "
                f"(id={item.get('id')})"
            )
        seen.add(source)


def _resolve_static(value: Any, script: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$lesson."):
        key = value[len("$lesson.") :]
        return (script.get("lesson") or {}).get(key, "")
    if isinstance(value, dict):
        return {k: _resolve_static(v, script) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_static(v, script) for v in value]
    return value


def resolve_source(
    source_key: str,
    export_data: dict[str, Any],
    stage3_data: dict[str, Any] | None,
) -> Any:
    question = (export_data.get("question") or "").strip()
    stage1 = (export_data.get("stage1") or "").strip()
    stage2 = (export_data.get("stage2") or "").strip()
    stage4 = (export_data.get("stage4") or "").strip()

    if source_key == "question.stem":
        return _question_lines(question)
    if source_key == "question.visuals":
        return _poster_lines(question)
    if source_key == "stage1.thinking_core":
        return _build_thinking_core(stage1)
    if source_key == "stage1.triplet":
        return _stage1_triplet(stage1)
    if source_key == "stage1.self_check_five":
        return _stage1_self_check_five(stage1)
    if source_key == "stage1.thinking_path":
        return _thinking_path(stage1)
    if source_key == "stage1.thinking_formula":
        return _thinking_formula(stage1)
    if source_key == "stage1.mistakes":
        return _stage1_mistakes(stage4, stage1)
    if source_key == "stage1.tasks":
        return _stage1_tasks(stage1)
    if source_key == "stage2.peel":
        return _peel_from_stage2(stage2)
    if source_key == "stage2.essay_basic":
        return _extract_essay_block(stage2, "基础版") or _extract_essay_block(stage2, "基础")
    if source_key == "stage2.essay_advanced_a":
        return (
            _extract_essay_block(stage2, "进阶版")
            or _extract_essay_block(stage2, "高分版 A")
            or _extract_essay_block(stage2, "高分版")
        )
    if source_key == "stage2.essay_advanced_b":
        return _extract_essay_block(stage2, "高分版 B") or _extract_essay_block(stage2, "逻辑")
    if source_key == "stage4.migration":
        return _stage4_migration(stage4, question)
    if source_key == "stage4.homework":
        _, g2 = _closing_slides(export_data)
        return g2
    if source_key == "stage4.review":
        return _stage4_review(stage4)
    if source_key == "stage4.warn":
        return _stage4_warn(stage4)
    if source_key == "stage2.upgrades":
        return _upgrade_bullets_from_stage2(stage2)
    raise ClassroomScriptError(f"unknown source key: {source_key!r}")


def _filter_poster_lines(lines: list[str]) -> list[str]:
    """Drop placeholder-only poster chunks (e.g. bare 「两张海报：」)."""
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or _POSTER_LABEL_ONLY.match(s):
            continue
        inner = re.sub(
            r"^(?:两张海报[：:]\s*|Poster\s*\d+\s*(?:是|為|为)?\s*)",
            "",
            s,
            flags=re.IGNORECASE,
        ).strip()
        if len(inner) < 6 and not re.search(r"[；;，,。]", s):
            continue
        out.append(line)
    return out


def _triplet_task_key(text: str) -> str:
    t = re.sub(r"^[①②③]\s*", "", text.strip())
    if "：" in t:
        t = t.split("：", 1)[1].strip()
    return re.sub(r"\s+", "", t.lower())


def _build_thinking_core(stage1: str) -> list[str]:
    """Merge triplet + tasks + formula + path into one non-redundant bullet chain."""
    triplet = _stage1_triplet(stage1)
    tasks = _stage1_tasks(stage1)
    formula_lines = _thinking_formula(stage1)
    path = _thinking_path(stage1)

    bullets: list[str] = list(triplet[:3])
    triplet_keys = {_triplet_task_key(t) for t in triplet}

    extra_tasks = [t for t in tasks if _triplet_task_key(t) not in triplet_keys]
    if extra_tasks:
        bullets.append("↓")
        bullets.extend(extra_tasks[:3])

    formula = (formula_lines[0] if formula_lines else "").strip()
    if formula:
        bullets.append(f"💡 高分公式：{formula}")

    path_keys = {_triplet_task_key(p) for p in path if p.strip() and p.strip() != "↓"}
    path_new = [p for p in path if p.strip() == "↓" or _triplet_task_key(p) not in triplet_keys]
    path_substance = [p for p in path_new if p.strip() != "↓"]
    if len(path_substance) >= 2 and len(bullets) < 7:
        if bullets and bullets[-1] != "↓":
            bullets.append("↓")
        bullets.extend(path_new[:4])

    return bullets[:9]


def _as_bullets(payload: Any) -> list[str]:
    if payload is None:
        return []
    if isinstance(payload, str):
        text = payload.strip()
        return [text] if text else []
    if isinstance(payload, list):
        return [str(x).strip() for x in payload if str(x).strip()]
    return []


def _payload_to_bullets(payload: Any) -> list[str]:
    if isinstance(payload, dict) and "bullets" in payload:
        return _as_bullets(payload["bullets"])
    return _as_bullets(payload)


def _is_empty_payload(payload: Any) -> bool:
    if payload is None:
        return True
    if isinstance(payload, str):
        return not payload.strip()
    if isinstance(payload, list):
        return len(_as_bullets(payload)) == 0
    if isinstance(payload, dict):
        return not payload
    return False


def _phrase_specs_interleaved(stage3_specs: list[dict]) -> list[dict]:
    """Body + footer per phrase table in deck_plan order (for immediate 改一句 practice)."""
    return [deepcopy(s) for s in stage3_specs if s.get("type") == "phrase_table"]


def _phrase_specs(stage3_specs: list[dict], part: str) -> list[dict]:
    out: list[dict] = []
    for spec in stage3_specs:
        if spec.get("type") != "phrase_table":
            continue
        p = spec.get("part") or "full"
        if part == "body" and p in ("body", "full"):
            out.append(deepcopy(spec))
        elif part == "footer" and p in (
            "footer",
            "footer_note",
            "footer_fix",
            "footer_fix_bad",
            "footer_fix_good",
        ):
            out.append(deepcopy(spec))
    return out


def archetype_to_spec(
    archetype: str,
    *,
    export_data: dict[str, Any],
    script: dict[str, Any],
    payload: Any,
    options: dict[str, Any],
    stage3_specs: list[dict],
) -> list[dict]:
    """Map one archetype instance → zero or more render-compatible slide specs."""
    opts = options or {}
    lesson = script.get("lesson") or {}
    qtype = _question_type_label(export_data)

    if archetype == "cover_meta":
        static = payload if isinstance(payload, dict) else {}
        title = static.get("title") or lesson.get("title") or f"高考英语应用文 · {qtype}"
        task_tag = static.get("task_tag") or lesson.get("task_tag") or _topic_subtitle(export_data)
        # Hero pill in renderer already shows task; empty subtitle avoids Y overlap.
        return [
            {
                "type": "title",
                "title": title,
                "subtitle": "",
                "task_tag": task_tag,
                "body": [],
            }
        ]

    if archetype == "question_stem":
        bullets = _as_bullets(payload)
        if not bullets:
            return []
        return [
            {
                "type": "content",
                "title": opts.get("title", _ARCHETYPE_TITLES["question_stem"]),
                "bullets": bullets,
                "panel": True,
            }
        ]

    if archetype == "visual_poster":
        lines = _filter_poster_lines(_as_bullets(payload))
        if not lines:
            return []
        one_per = opts.get("one_per_slide", True)
        if one_per:
            return [
                {
                    "type": "content",
                    "title": opts.get("title", _ARCHETYPE_TITLES["visual_poster"]),
                    "bullets": [line],
                    "panel": True,
                }
                for line in lines
            ]
        return [
            {
                "type": "content",
                "title": opts.get("title", _ARCHETYPE_TITLES["visual_poster"]),
                "bullets": lines,
                "panel": True,
            }
        ]

    if archetype == "essay_display":
        text = payload if isinstance(payload, str) else ""
        if not text.strip():
            return []
        from scripts.essay_format import classroom_essay_plain_text, prepare_classroom_essay_body

        paragraphs, _wc, embedded_ann = prepare_classroom_essay_body(text)
        plain = classroom_essay_plain_text(paragraphs) if paragraphs else text.strip()
        ann = (opts.get("annotation") or embedded_ann or "").strip()
        return [
            {
                "type": "essay",
                "title": opts.get("title", _ARCHETYPE_TITLES["essay_display"]),
                "essay_text": plain or text.strip(),
                "annotation": ann,
                "badge": opts.get("badge"),
            }
        ]

    if archetype == "phrase_table":
        return _phrase_specs_interleaved(stage3_specs)

    if archetype == "phrase_footer":
        return []

    if archetype == "vocab_table":
        return [deepcopy(s) for s in stage3_specs if s.get("type") == "vocab_table"]

    if archetype == "stage3_bundle":
        return [deepcopy(s) for s in stage3_specs]

    if archetype == "peel_skeleton":
        points = payload if isinstance(payload, list) else []
        if not points:
            return []
        return [
            {
                "type": "peel",
                "title": opts.get("title", _ARCHETYPE_TITLES["peel_skeleton"]),
                "points": points,
            }
        ]

    if archetype == "self_check_five":
        stage1 = (export_data.get("stage1") or "").strip()
        return _self_check_five_slide_specs(stage1, "B")

    if archetype == "thinking_core":
        bullets = _payload_to_bullets(payload)
        if not bullets:
            bullets = _build_thinking_core((export_data.get("stage1") or "").strip())
        if not bullets:
            return []
        return [
            {
                "type": "content",
                "title": opts.get("title", _ARCHETYPE_TITLES["thinking_core"]),
                "bullets": bullets,
                "panel": True,
            }
        ]

    if archetype in (
        "scenario_hook",
        "triplet_review",
        "task_checklist",
        "pitfall_contrast",
        "thinking_path",
        "thinking_formula",
        "essay_annotation",
        "practice_migration",
        "summary_formula",
        "summary_homework",
        "stage4_review",
        "stage4_warn",
    ):
        bullets = _payload_to_bullets(payload)
        if not bullets and archetype == "summary_formula":
            bullets = ["本课高分公式：观点 + 细节 + 分析 + 升华"]
        if not bullets:
            return []
        spec: dict[str, Any] = {
            "type": "content",
            "title": opts.get("title", _ARCHETYPE_TITLES.get(archetype, archetype)),
            "bullets": bullets,
        }
        if archetype in ("pitfall_contrast", "stage4_warn"):
            spec["warn_panel"] = True
        if archetype in ("scenario_hook", "practice_migration", "stage4_review"):
            spec["panel"] = True
        if archetype == "practice_migration":
            spec["badge"] = opts.get("badge", "迁移练")
        if archetype == "stage4_review":
            spec["badge"] = opts.get("badge", "当堂操练")
        if archetype == "stage4_warn":
            spec["badge"] = opts.get("badge", "动笔易错")
            spec["panel"] = True
        return [spec]

    raise ClassroomScriptError(f"unknown archetype: {archetype!r}")


def _ensure_font_size(spec: dict[str, Any], *, archetype: str | None = None) -> dict[str, Any]:
    """Inject font_size / min_font_size on specs that carry body text."""
    out = dict(spec)
    needs_font = (
        archetype in _FONT_SIZE_ARCHETYPES
        or out.get("type") in ("essay", "phrase_table", "vocab_table", "content")
    )
    if not needs_font:
        return out
    fs = out.get("font_size")
    if not isinstance(fs, (int, float)) or fs < MIN_FONT_SIZE:
        out["font_size"] = PREFERRED_FONT_SIZE
    else:
        out["font_size"] = max(int(fs), MIN_FONT_SIZE)
    out["min_font_size"] = MIN_FONT_SIZE
    return out


def _essay_line_count(text: str) -> int:
    return len([ln for ln in text.splitlines() if ln.strip()])


def _compress_essay_text(text: str) -> str:
    """Step A: trim redundant wording; keep opening, choice, body, conclusion."""
    paras = [p.strip() for p in re.split(r"\n\s*\n+", text.strip()) if p.strip()]
    if not paras:
        return text.strip()

    cleaned: list[str] = []
    for p in paras:
        c = _REDUNDANT_WORDS.sub(" ", p)
        c = re.sub(r"\s{2,}", " ", c).strip()
        cleaned.append(c)

    if len("".join(cleaned)) <= ESSAY_MAX_CHARS and sum(_essay_line_count(p) for p in cleaned) <= ESSAY_MAX_LINES:
        return "\n\n".join(cleaned)

    kept: list[str] = [cleaned[0]]
    for p in cleaned[1:]:
        if re.search(r"I'd (go|choose)|Personally|I recommend", p, re.IGNORECASE):
            kept.append(p)
            break

    body_candidates = [
        p
        for p in cleaned
        if p not in kept
        and not re.search(r"^(Good luck|Hope this|Best wishes|Yours|Looking forward)", p, re.IGNORECASE)
    ]
    kept.extend(body_candidates[:2])

    for p in reversed(cleaned):
        if re.search(r"(Overall|In conclusion|In summary|Good luck|Hope this helps)", p, re.IGNORECASE):
            if p not in kept:
                kept.append(p)
            break

    result = "\n\n".join(kept)
    return result


def _force_essay_two_parts(text: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text.strip()) if b.strip()]
    if len(blocks) >= 2:
        mid = max(1, len(blocks) // 2)
        return ["\n\n".join(blocks[:mid]), "\n\n".join(blocks[mid:])]
    mid = max(1, len(text) // 2)
    cut = text.rfind(". ", 0, mid)
    if cut < 1:
        cut = mid
    return [text[:cut].strip(), text[cut:].strip()]


def _essay_annotation_slides(base_title: str, ann: str) -> list[dict[str, Any]]:
    ann_lines = [ln.strip() for ln in re.split(r"(?<=[。；;])\s*|\n+", ann) if ln.strip()]
    if not ann_lines:
        ann_lines = [ann]
    ann_spec: dict[str, Any] = {
        "type": "content",
        "title": f"{base_title} · 批注",
        "bullets": ann_lines,
        "panel": True,
    }
    return _layout_content_spec(
        _ensure_font_size(ann_spec, archetype="essay_annotation"),
        archetype="essay_annotation",
    )


def _layout_essay_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    from scripts.ppt_layout_fit import essay_text_fits, split_essay_text

    text = (spec.get("essay_text") or "").strip()
    ann = (spec.get("annotation") or "").strip()
    if not text:
        return []

    if len(text) > ESSAY_MAX_CHARS or _essay_line_count(text) > ESSAY_MAX_LINES:
        text = _compress_essay_text(text)

    base_title = spec.get("title", "范文")
    badge = spec.get("badge")
    has_badge = bool(badge)

    if (
        essay_text_fits(text, has_badge=has_badge, has_annotation=False)
        and len(text) <= ESSAY_MAX_CHARS
    ):
        out = [
            _ensure_font_size(
                {**spec, "essay_text": text, "annotation": ""},
                archetype="essay_display",
            )
        ]
        if ann:
            out.extend(_essay_annotation_slides(base_title, ann))
        return out

    chunks = split_essay_text(text, has_badge=has_badge, has_annotation=False)
    if len(chunks) <= 1 and (
        len(text) > ESSAY_MAX_CHARS
        or not essay_text_fits(text, has_badge=has_badge, has_annotation=False)
    ):
        chunks = _force_essay_two_parts(text)

    out: list[dict[str, Any]] = []
    for idx, chunk in enumerate(chunks):
        part_spec = dict(spec)
        part_spec["essay_text"] = chunk
        part_spec["annotation"] = ""
        part_spec["badge"] = badge if idx == 0 else None
        if len(chunks) > 1:
            part_spec["title"] = f"{base_title} · Part {idx + 1}"
            part_spec["_essay_part"] = idx + 1
        out.append(_ensure_font_size(part_spec, archetype="essay_display"))

    if ann:
        out.extend(_essay_annotation_slides(base_title, ann))
    return out


def _layout_phrase_table_spec(spec: dict[str, Any], *, archetype: str) -> list[dict[str, Any]]:
    table = spec.get("table") or {}
    tiers = list(table.get("tiers") or [])
    if len(tiers) <= TABLE_MAX_ROWS:
        return [_ensure_font_size(spec, archetype=archetype)]

    out: list[dict[str, Any]] = []
    base_title = spec.get("title", "功能句型")
    for ci in range(0, len(tiers), TABLE_MAX_ROWS):
        chunk = tiers[ci : ci + TABLE_MAX_ROWS]
        part = dict(spec)
        part["table"] = {**table, "tiers": chunk}
        if len(tiers) > TABLE_MAX_ROWS:
            part["title"] = f"{base_title} ({ci // TABLE_MAX_ROWS + 1}/{(len(tiers) - 1) // TABLE_MAX_ROWS + 1})"
        out.append(_ensure_font_size(part, archetype=archetype))
    return out


def _layout_vocab_table_spec(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(spec.get("rows") or [])
    if len(rows) <= TABLE_MAX_ROWS:
        return [_ensure_font_size(spec, archetype="vocab_table")]

    out: list[dict[str, Any]] = []
    base_title = spec.get("title", "话题词块")
    for ci in range(0, len(rows), TABLE_MAX_ROWS):
        chunk = rows[ci : ci + TABLE_MAX_ROWS]
        part = dict(spec)
        part["rows"] = chunk
        if len(rows) > TABLE_MAX_ROWS:
            part["title"] = f"{base_title} ({ci // TABLE_MAX_ROWS + 1}/{(len(rows) - 1) // TABLE_MAX_ROWS + 1})"
        out.append(_ensure_font_size(part, archetype="vocab_table"))
    return out


def _layout_content_spec(spec: dict[str, Any], *, archetype: str | None) -> list[dict[str, Any]]:
    from scripts.ppt_layout_fit import expand_content_slides

    if archetype == "visual_poster":
        bullets = spec.get("bullets") or []
        if len(bullets) <= 1:
            return [_ensure_font_size(spec, archetype=archetype)]
        return [
            _ensure_font_size({**spec, "bullets": [b]}, archetype=archetype)
            for b in bullets
            if str(b).strip()
        ]

    if archetype not in _FONT_SIZE_ARCHETYPES and not spec.get("panel"):
        return [_ensure_font_size(spec, archetype=archetype)]

    expanded = expand_content_slides([spec])
    return [_ensure_font_size(s, archetype=archetype) for s in expanded]


def check_and_split_layout(spec: dict[str, Any], *, archetype: str | None = None) -> list[dict[str, Any]]:
    """Post-process slide spec: enforce min font_size and split overflowing content."""
    archetype = archetype or spec.get("_archetype")
    base = deepcopy(spec)

    if base.get("type") == "essay" or archetype == "essay_display":
        return _layout_essay_spec(base)

    if base.get("type") == "phrase_table" or archetype in ("phrase_table", "phrase_footer"):
        arch = archetype or ("phrase_footer" if base.get("part", "").startswith("footer") else "phrase_table")
        return _layout_phrase_table_spec(base, archetype=arch)

    if base.get("type") == "vocab_table" or archetype == "vocab_table":
        return _layout_vocab_table_spec(base)

    if base.get("type") == "content":
        return _layout_content_spec(base, archetype=archetype)

    return [_ensure_font_size(base, archetype=archetype)]


def compile_classroom_script(
    script: dict[str, Any],
    export_data: dict[str, Any],
    stage3_data: dict[str, Any] | None = None,
    *,
    stage3_specs: list[dict[str, Any] | None] = None,
    vocab_max_rows: int = 6,
) -> list[dict]:
    """Compile classroom_script.json → list[dict] for render_v2_deck."""
    sequence = script.get("sequence") or []
    assert_source_exclusivity(sequence)

    specs_list: list[dict] | None = stage3_specs
    if specs_list is None and stage3_data:
        from scripts.deck_plan import (
            deck_plan_from_stage3,
            refine_deck_plan,
            stage3_specs_from_plan,
        )

        plan = deck_plan_from_stage3(stage3_data, vocab_max_rows=vocab_max_rows)
        plan = refine_deck_plan(stage3_data, plan, vocab_max_rows=vocab_max_rows)
        specs_list = stage3_specs_from_plan(stage3_data, plan)
    specs_list = specs_list or []

    out: list[dict] = []
    for item in sequence:
        archetype = item.get("archetype")
        if not archetype:
            raise ClassroomScriptError(f"sequence item missing archetype: {item.get('id')}")

        bind = item.get("bind") or {}
        options = item.get("options") or {}
        skip_if_empty = bool(item.get("skip_if_empty"))

        payload: Any = None
        if "static" in bind:
            payload = _resolve_static(bind["static"], script)
        elif "source" in bind:
            if bind["source"].startswith("stage3."):
                payload = stage3_data
            else:
                payload = resolve_source(bind["source"], export_data, stage3_data)
        elif archetype in ("stage3_bundle", "vocab_table", "phrase_table", "phrase_footer"):
            payload = stage3_data
        else:
            payload = None

        if skip_if_empty and _is_empty_payload(payload) and archetype not in (
            "stage3_bundle",
            "phrase_table",
            "phrase_footer",
            "vocab_table",
        ):
            continue

        slides = archetype_to_spec(
            archetype,
            export_data=export_data,
            script=script,
            payload=payload,
            options=options,
            stage3_specs=specs_list,
        )
        for spec in slides:
            out.extend(check_and_split_layout(spec, archetype=archetype))

    if not out:
        raise ClassroomScriptError("compile produced empty slide list")
    return out
