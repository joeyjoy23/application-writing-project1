"""Build Plan B classroom HTML deck: Humanize AST + Architecture V1 content fill.

Pipeline:
  1. Humanize slide_plan.json — per-module audience state transfer (AST)
  2. Architecture V1 70min — page allocation + export-data + stage3 full content
  3. ecc-frontend-slides HTML — viewport-safe, click-reveal, speaker-notes.html

Student projection only; teacher guidance lives in speaker notes (S key).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.architecture_v1 import build_full_deck_from_export
from scripts.classroom_content_filter import is_teacher_only_line, sanitize_student_text
from scripts.essay_format import classroom_essay_plain_text, prepare_classroom_essay_display
from scripts.humanize_classroom_ast import (
    classroom_ast_header,
    enrich_specs_with_ast,
    speaker_note_entries,
)

MAX_BULLETS_PER_SLIDE = 6
_VOCAB_COL_LABELS = {"english": "英文", "chinese": "中文", "example": "例句"}


class _RevealSeq:
    """Assign monotonic data-reveal indices within one slide."""

    def __init__(self) -> None:
        self._n = 0

    def mark(self, extra_class: str = "") -> str:
        i = self._n
        self._n += 1
        cls = f"{extra_class} reveal".strip()
        return f' class="{cls}" data-reveal="{i}"'


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _tag_for_spec(spec: dict[str, Any]) -> str:
    title = spec.get("title", "")
    if title.startswith("导入"):
        return "导入"
    if title.startswith("审题"):
        return "Stage 1"
    if title.startswith("思维"):
        return "Stage 1"
    if "PEEL" in title or "范文" in title or "三版" in title or "升级" in title:
        return "Stage 2"
    if title.startswith("功能句型") or title.startswith("话题词块"):
        return "Stage 3"
    if "易错" in title or "讲评" in title or "迁移" in title:
        return "Stage 4"
    if "小结" in title or "课后" in title:
        return "总结"
    kind = spec.get("type", "")
    if kind in ("phrase_table", "vocab_table"):
        return "Stage 3"
    if kind == "essay":
        return "Stage 2"
    if kind == "peel":
        return "Stage 2"
    return "课堂"


def _split_bullets(bullets: list[str], *, max_n: int = MAX_BULLETS_PER_SLIDE) -> list[list[str]]:
    if not bullets:
        return []
    return [bullets[i : i + max_n] for i in range(0, len(bullets), max_n)]


def _stage1_self_checks(stage1: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(
        r"^\d+\.\s+(.+?)\s*[—–-]\s*(.+)$",
        stage1,
        flags=re.MULTILINE,
    ):
        out.append(f"{m.group(1).strip()} — {m.group(2).strip()}")
    return out


def _stage1_insight(stage1: str) -> str:
    m = re.search(r"💡\s*一句大实话\s*\n+(.+?)(?=\n\n|\n2\.)", stage1, flags=re.DOTALL)
    return m.group(1).strip() if m else ""


def _stage1_conclusion(stage1: str) -> list[str]:
    out: list[str] = []
    for key in ("体裁", "时态", "人称", "语气"):
        m = re.search(rf"^-\s+{key}[：:]\s*(.+)$", stage1, flags=re.MULTILINE)
        if m:
            out.append(f"{key}：{m.group(1).strip()}")
    return out


def _stage1_comm_goals(stage1: str) -> list[str]:
    m = re.search(
        r"2\.4\s*交际目的拆解\s*(.*?)(?=3\.\s*审题结论|$)",
        stage1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return []
    out: list[str] = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line.startswith("- ") or is_teacher_only_line(line):
            continue
        out.append(line[2:].strip())
    return out


def _stage1_dimensions(stage1: str) -> list[tuple[str, list[str]]]:
    dims: list[tuple[str, list[str]]] = []
    for m in re.finditer(
        r"维度(\d+)\s*[·•]\s*(.+?)\n(.*?)(?=维度\d+|6\.\s*要点|$)",
        stage1,
        flags=re.DOTALL,
    ):
        name = m.group(2).strip()
        bullets: list[str] = []
        for line in m.group(3).splitlines():
            line = line.strip()
            if line.startswith("- ") and not is_teacher_only_line(line):
                bullets.append(line[2:].strip())
            elif line.startswith("💡"):
                bullets.append(line.strip())
        if bullets:
            dims.append((name, bullets))
    return dims


def _stage1_structure(stage1: str) -> list[str]:
    m = re.search(
        r"6\.\s*要点与结构规划\s*(.*?)(?=\Z)",
        stage1,
        flags=re.DOTALL,
    )
    if not m:
        return []
    out: list[str] = []
    section = ""
    for line in m.group(1).splitlines():
        line = line.strip()
        if line in ("开头段", "主体段", "结尾段"):
            section = line
            continue
        if line.startswith("- ") and section:
            out.append(f"{section} · {line[2:].strip()}")
        elif line.startswith("📌") and section:
            out.append(f"{section} · {line.strip()}")
    return out


def _stage1_easy_mistakes(stage1: str) -> list[str]:
    m = re.search(r"2\.2\s*易错提醒\s*(.*?)(?=2\.3|$)", stage1, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    out: list[str] = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- ") and not is_teacher_only_line(line):
            out.append(line[2:].strip())
    return out


def stage1_supplement_specs(export_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Full Stage1 blocks not covered by Architecture V1 slot summaries."""
    stage1 = (export_data.get("stage1") or "").strip()
    qtype = export_data.get("question_type_label") or "应用文"
    if not stage1:
        return []

    specs: list[dict[str, Any]] = []
    insight = _stage1_insight(stage1)
    start_bullets = [f"题目类型：{qtype}"]
    if insight:
        start_bullets.append(f"💡 {insight}")
    specs.append(
        {
            "type": "content",
            "title": "审题 · 起点与洞察",
            "bullets": start_bullets,
        }
    )

    checks = _stage1_self_checks(stage1)
    for chunk in _split_bullets(checks):
        specs.append(
            {
                "type": "content",
                "title": "审题 · 动笔前自检",
                "bullets": chunk,
            }
        )

    easy = _stage1_easy_mistakes(stage1)
    for chunk in _split_bullets(easy):
        specs.append(
            {
                "type": "content",
                "title": "审题 · 易错提醒（全文）",
                "bullets": chunk,
            }
        )

    conclusion = _stage1_conclusion(stage1)
    if conclusion:
        specs.append(
            {"type": "content", "title": "审题 · 结论", "bullets": conclusion}
        )

    goals = _stage1_comm_goals(stage1)
    for chunk in _split_bullets(goals):
        specs.append(
            {"type": "content", "title": "审题 · 交际目的", "bullets": chunk}
        )

    for dim_name, dim_bullets in _stage1_dimensions(stage1):
        for chunk in _split_bullets(dim_bullets):
            specs.append(
                {
                    "type": "content",
                    "title": f"思维 · {dim_name}",
                    "bullets": chunk,
                }
            )

    structure = _stage1_structure(stage1)
    for chunk in _split_bullets(structure):
        specs.append(
            {
                "type": "content",
                "title": "思维 · 要点与结构",
                "bullets": chunk,
            }
        )
    return specs


def inject_stage1_supplements(
    v2_specs: list[dict[str, Any]], export_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Insert full Stage1 slides after 审题 · 易错对比."""
    supplements = stage1_supplement_specs(export_data)
    if not supplements:
        return v2_specs

    insert_at = None
    for i, spec in enumerate(v2_specs):
        if spec.get("title") == "审题 · 易错对比":
            insert_at = i + 1
            break
    if insert_at is None:
        for i, spec in enumerate(v2_specs):
            if spec.get("title", "").startswith("思维"):
                insert_at = i
                break
    if insert_at is None:
        insert_at = min(3, len(v2_specs))

    return v2_specs[:insert_at] + supplements + v2_specs[insert_at:]


def _peel_point_lines(point: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    if point.get("p"):
        lines.append(f"P · {point['p']}")
    for item in point.get("e_items") or []:
        lines.append(f"E · {item}")
    if point.get("l"):
        lines.append(f"L · {point['l']}")
    return lines


def _essay_html_text(raw: str, annotation: str = "") -> tuple[str, str]:
    if "Dear " in raw or "中文批注" in raw:
        paragraphs, ann = prepare_classroom_essay_display(
            raw, annotation_fallback=annotation or ""
        )
        return classroom_essay_plain_text(paragraphs), ann
    return raw.strip(), (annotation or "").strip()


def v2_spec_to_html_slides(spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert one V2 renderer spec → one or more viewport-safe HTML slide dicts."""
    kind = spec.get("type", "content")
    tag = _tag_for_spec(spec)
    title = spec.get("title", "")
    badge = spec.get("badge")
    base: dict[str, Any] = {"tag": tag, "title": title}
    if badge:
        base["badge"] = badge
    if spec.get("warn_panel"):
        base["warn_panel"] = True

    if kind == "title":
        body_lines = spec.get("body") or []
        if isinstance(body_lines, str):
            body_lines = [body_lines]
        return [
            {
                **base,
                "variant": "hero",
                "subtitle": spec.get("subtitle", ""),
                "bullets": body_lines,
            }
        ]

    if kind == "content":
        bullets = [
            sanitize_student_text(b)
            for b in (spec.get("bullets") or [])
            if sanitize_student_text(b)
        ]
        slides: list[dict[str, Any]] = []
        chunks = _split_bullets(bullets) or [[]]
        for i, chunk in enumerate(chunks):
            slide = {**base}
            if len(chunks) > 1:
                slide["title"] = f"{title} ({i + 1}/{len(chunks)})"
            slide["bullets"] = chunk
            slides.append(slide)
        return slides or [{**base, "bullets": []}]

    if kind == "peel":
        points = spec.get("points") or []
        if len(points) >= 2:
            return [{**base, "peel": points[:2]}]
        if points:
            return [{**base, "peel": points[:1], "peel_single": True}]
        return [{**base, "bullets": ["（见 Stage2 PEEL 策略卡）"]}]

    if kind == "essay":
        essay_text, ann = _essay_html_text(
            spec.get("essay_text") or "", spec.get("annotation") or ""
        )
        return [{**base, "essay": essay_text, "annotation": ann}]

    if kind == "table":
        headers = spec.get("headers") or []
        rows = spec.get("rows") or []
        return [{**base, "table_headers": headers, "table_rows": rows}]

    if kind == "phrase_table":
        table = spec.get("table") or {}
        part = spec.get("part", "full")
        slides: list[dict[str, Any]] = []

        if part in ("full", "body"):
            tiers = table.get("tiers") or []
            rows = [
                {
                    "tier": t.get("level", ""),
                    "en": t.get("english", ""),
                    "zh": t.get("chinese", ""),
                    "note": t.get("high_score") or "",
                }
                for t in tiers
            ]
            if rows:
                slides.append({**base, "phrase_body": rows, "table_name": table.get("name", "")})

        if part in ("full", "footer", "footer_note"):
            note = (table.get("topic_note") or "").strip()
            if note and part in ("full", "footer", "footer_note"):
                slides.append(
                    {
                        **base,
                        "title": f"{title} · 本题用法" if part == "full" else title,
                        "banner": note,
                    }
                )

        if part in ("full", "footer", "footer_fix", "footer_fix_bad", "footer_fix_good"):
            fix_bad = (table.get("fix_bad") or "").strip()
            fix_good = (table.get("fix_good") or "").strip()
            if part == "footer_fix_bad" and fix_bad:
                slides.append({**base, "fix_bad": fix_bad})
            elif part == "footer_fix_good" and fix_good:
                slides.append({**base, "fix_good": fix_good})
            elif part in ("full", "footer", "footer_fix") and (fix_bad or fix_good):
                slides.append(
                    {
                        **base,
                        "title": f"{title} · 改错" if part == "full" else title,
                        "fix_bad": fix_bad,
                        "fix_good": fix_good,
                    }
                )

        return slides or [{**base, "bullets": ["（句型表见 stage3.json）"]}]

    if kind == "vocab_table":
        columns = spec.get("columns") or ["english", "chinese", "example"]
        rows = spec.get("rows") or []
        tier = spec.get("tier") or ""
        if not rows:
            return []
        headers = [_VOCAB_COL_LABELS.get(c, c) for c in columns]
        table_rows = [[str(row.get(c, "")) for c in columns] for row in rows]
        return [
            {
                **base,
                "tier": tier,
                "table_headers": headers,
                "table_rows": table_rows,
            }
        ]

    return [{**base, "bullets": [str(spec)]}]


def build_slide_specs(
    export_data: dict[str, Any],
    *,
    stage3_path: Path | None = None,
    deck_plan_path: Path | None = None,
    slide_plan_path: Path | None = None,
    speaker_intent_path: Path | None = None,
    preset: str = "70min",
) -> list[dict[str, Any]]:
    """Humanize AST metadata + Architecture V1 content → HTML slide dicts."""
    lesson = preset if preset in ("40min", "70min", "80min") else "70min"
    if stage3_path and stage3_path.is_file():
        v2 = build_full_deck_from_export(
            export_data,
            stage3_path,
            deck_plan_path,
            preset=lesson,  # type: ignore[arg-type]
        )
    else:
        v2 = _legacy_specs_from_export(export_data)

    v2 = inject_stage1_supplements(v2, export_data)

    html_specs: list[dict[str, Any]] = []
    for spec in v2:
        html_specs.extend(v2_spec_to_html_slides(spec))

    if slide_plan_path is None and speaker_intent_path is None:
        return html_specs

    if slide_plan_path is None and speaker_intent_path:
        slide_plan_path = speaker_intent_path.parent / "slide_plan.json"
    if speaker_intent_path is None and slide_plan_path:
        candidate = slide_plan_path.parent / "speaker_intent.md"
        speaker_intent_path = candidate if candidate.is_file() else None

    enrich_specs_with_ast(
        html_specs,
        slide_plan_path=slide_plan_path,
        speaker_intent_path=speaker_intent_path,
    )
    return html_specs


def _legacy_specs_from_export(export_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Fallback when stage3.json is missing — minimal export-only deck."""
    from scripts.architecture_v1 import build_architecture_deck, inject_module_dividers

    base = build_architecture_deck(export_data, preset="80min")
    return inject_module_dividers(base)


def _render_slide(slide: dict[str, Any], index: int, total: int) -> str:
    tag = _esc(slide.get("tag", ""))
    title = _esc(slide.get("title", ""))
    variant = slide.get("variant", "")
    hero = ' data-variant="hero"' if variant == "hero" else ""
    warn = ' data-warn="1"' if slide.get("warn_panel") else ""
    intent = slide.get("speaker_intent", "")
    intent_attr = f' data-intent="{_esc(intent)}"' if intent else ""
    ast_attrs = ""
    if slide.get("one_thing"):
        ast_attrs += f' data-one-thing="{_esc(slide["one_thing"])}"'
    if slide.get("audience_in"):
        ast_attrs += f' data-audience-in="{_esc(slide["audience_in"])}"'
    if slide.get("audience_out"):
        ast_attrs += f' data-audience-out="{_esc(slide["audience_out"])}"'
    if slide.get("ast_role"):
        ast_attrs += f' data-ast-role="{_esc(slide["ast_role"])}"'
    rv = _RevealSeq()
    parts = [
        f'<section class="slide"{hero}{warn} data-index="{index}" aria-label="{title}"{intent_attr}{ast_attrs}>',
        '<header class="slide-chrome">',
        f'<span class="tag">{tag}</span>',
    ]
    if slide.get("badge"):
        parts.append(f'<span class="badge">{_esc(slide["badge"])}</span>')
    parts.append(f'<span class="progress">{index + 1} / {total}</span>')
    parts.append("</header>")
    parts.append(f'<h2 class="slide-title">{title}</h2>')

    if slide.get("tier"):
        parts.append(f"<p{rv.mark('tier-pill')}>{_esc(slide['tier'])}</p>")

    if slide.get("subtitle"):
        parts.append(f"<p{rv.mark('subtitle')}>{_esc(slide['subtitle'])}</p>")

    if slide.get("body"):
        parts.append(f"<p{rv.mark('lead')}>{_esc(slide['body'])}</p>")

    if slide.get("banner"):
        parts.append(f"<p{rv.mark('banner')}>{_esc(slide['banner'])}</p>")

    bullets = slide.get("bullets") or []
    if bullets:
        parts.append('<ul class="bullets">')
        for b in bullets:
            parts.append(f"<li{rv.mark()}>{_esc(b)}</li>")
        parts.append("</ul>")

    peel = slide.get("peel") or []
    if peel:
        single = slide.get("peel_single")
        grid_cls = "peel-grid peel-single" if single else "peel-grid"
        parts.append(f'<div class="{grid_cls}">')
        labels = ("① 选择", "② 理由")
        for j, pt in enumerate(peel):
            label = labels[j] if j < len(labels) else pt.get("label", "")
            parts.append(f'<div class="peel-card peel-{j}">')
            parts.append(f"<h3{rv.mark('peel-label')}>{_esc(label)}</h3>")
            parts.append("<ul>")
            for line in _peel_point_lines(pt):
                parts.append(f"<li{rv.mark()}>{_esc(line)}</li>")
            parts.append("</ul></div>")
        parts.append("</div>")

    if slide.get("essay"):
        paras = [p.strip() for p in slide["essay"].split("\n\n") if p.strip()]
        if len(paras) <= 1:
            parts.append(f"<pre{rv.mark('essay')}>{_esc(slide['essay'])}</pre>")
        else:
            parts.append('<div class="essay-block">')
            for para in paras:
                parts.append(f"<p{rv.mark('essay-para')}>{_esc(para)}</p>")
            parts.append("</div>")
        if slide.get("annotation"):
            parts.append(f"<p{rv.mark('annotation')}>{_esc(slide['annotation'])}</p>")

    phrase_body = slide.get("phrase_body") or []
    if phrase_body:
        parts.append('<table class="data-table"><thead><tr>')
        parts.append("<th>层级</th><th>英文句型</th><th>说明</th></tr></thead><tbody>")
        for row in phrase_body:
            zh = row.get("zh", "")
            if row.get("note"):
                zh = f"{zh} · {row['note']}" if zh else row["note"]
            parts.append(
                f"<tr{rv.mark('reveal-row')}>"
                f"<td>{_esc(row.get('tier', ''))}</td>"
                f"<td class=\"en\">{_esc(row.get('en', ''))}</td>"
                f"<td>{_esc(zh)}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    headers = slide.get("table_headers") or []
    rows = slide.get("table_rows") or []
    if headers and rows:
        parts.append('<table class="data-table"><thead><tr>')
        for h in headers:
            parts.append(f"<th>{_esc(str(h))}</th>")
        parts.append("</tr></thead><tbody>")
        for row in rows:
            parts.append(f"<tr{rv.mark('reveal-row')}>")
            for ci, cell in enumerate(row):
                cell_cls = ' class="en"' if ci == 0 or str(headers[ci]) == "英文" else ""
                parts.append(f"<td{cell_cls}>{_esc(str(cell))}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")

    if slide.get("fix_bad") or slide.get("fix_good"):
        parts.append('<div class="fix-grid">')
        if slide.get("fix_bad"):
            parts.append(
                f"<div{rv.mark('fix-card fix-bad')}>"
                f'<span class="fix-tag">别这样写</span><p>{_esc(slide["fix_bad"])}</p></div>'
            )
        if slide.get("fix_good"):
            good = slide["fix_good"].lstrip("→").strip()
            parts.append(
                f"<div{rv.mark('fix-card fix-good')}>"
                f'<span class="fix-tag">改成</span><p>{_esc(good)}</p></div>'
            )
        parts.append("</div>")

    parts.append('<footer class="slide-foot">应用文 AI 备课 · Plan B HTML · 26–32pt</footer>')
    parts.append("</section>")
    return "\n".join(parts)


def render_html(specs: list[dict[str, Any]], deck_title: str) -> str:
    total = len(specs)
    slides_html = "\n".join(_render_slide(s, i, total) for i, s in enumerate(specs))
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(deck_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Noto+Sans+SC:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --ink: #0f1419;
  --paper: #f4f1ea;
  --accent: #1a5f4a;
  --accent-soft: rgba(26, 95, 74, 0.12);
  --warn: #e85d5d;
  --serif: "Noto Serif SC", serif;
  --sans: "Noto Sans SC", sans-serif;
  --en: "Times New Roman", Times, "Noto Serif", serif;
  --mono: "IBM Plex Mono", monospace;
  --body-min: 26px;
  --body-max: 32px;
  --title-min: 36px;
  --title-max: 40px;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{
  width: 100%; height: 100%; overflow: hidden;
  background: var(--ink); color: var(--paper);
  font-family: var(--sans);
  font-size: clamp(var(--body-min), 2.5vw, var(--body-max));
  -webkit-font-smoothing: antialiased;
}}
#deck {{
  display: flex; width: {total * 100}vw; height: 100vh; height: 100dvh;
  transition: transform 0.65s cubic-bezier(0.22, 1, 0.36, 1);
  will-change: transform;
}}
.slide {{
  flex: 0 0 100vw; width: 100vw; height: 100vh; height: 100dvh;
  overflow: hidden; padding: clamp(0.8rem, 2.5vh, 1.6rem) clamp(1.2rem, 4vw, 3.5rem) clamp(0.8rem, 3vh, 2rem);
  display: flex; flex-direction: column;
  background: linear-gradient(145deg, #121820 0%, #0f1419 55%, #162028 100%);
  position: relative;
}}
.slide[data-variant="hero"] {{
  background: radial-gradient(ellipse at 20% 20%, rgba(26,95,74,.35), transparent 50%),
              linear-gradient(160deg, #0d1218, #101820 60%, #0f1419);
}}
.slide[data-warn="1"] {{ border-top: 4px solid var(--warn); }}
.slide::before {{
  content: ""; position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(180deg, rgba(255,255,255,.03), transparent 30%, transparent 70%, rgba(0,0,0,.2));
}}
.slide-chrome {{
  display: flex; justify-content: space-between; align-items: center; gap: 0.6rem;
  font-family: var(--mono); font-size: clamp(14px, 1.4vw, 18px);
  letter-spacing: 0.08em; color: rgba(244,241,234,.65);
  margin-bottom: clamp(0.5rem, 1.5vh, 1rem); flex-shrink: 0;
}}
.tag {{ border: 1px solid rgba(244,241,234,.35); padding: 0.3em 0.75em; border-radius: 999px; }}
.badge {{
  background: var(--accent-soft); border: 1px solid rgba(26,95,74,.5);
  padding: 0.25em 0.65em; border-radius: 6px; color: #b8e6d4;
}}
.slide-title {{
  font-family: var(--serif); font-weight: 700; flex-shrink: 0;
  font-size: clamp(var(--title-min), 4.5vw, var(--title-max)); line-height: 1.12;
  margin-bottom: clamp(0.4rem, 1.2vh, 0.9rem);
}}
.subtitle {{
  font-size: clamp(26px, 2.8vw, 34px); color: #6ec4a8;
  margin-bottom: 0.6rem; font-weight: 600; flex-shrink: 0;
}}
.tier-pill {{
  display: inline-block; align-self: flex-start;
  background: var(--accent-soft); border: 1px solid rgba(26,95,74,.45);
  padding: 0.25em 0.7em; border-radius: 8px; margin-bottom: 0.5rem;
  font-size: clamp(26px, 2.2vw, 28px); flex-shrink: 0;
}}
.lead, .banner {{
  font-size: clamp(var(--body-min), 2.5vw, var(--body-max)); line-height: 1.45;
  color: rgba(244,241,234,.94); margin-bottom: 0.7rem; flex-shrink: 0;
}}
.banner {{
  background: rgba(26,95,74,.18); border-left: 4px solid var(--accent);
  padding: 0.6em 0.85em; border-radius: 0 8px 8px 0;
}}
.bullets {{
  list-style: none; display: grid; gap: clamp(0.35rem, 1vh, 0.65rem);
  font-size: clamp(var(--body-min), 2.5vw, var(--body-max)); line-height: 1.42;
  flex: 1; min-height: 0; overflow: hidden;
}}
.bullets li {{ padding-left: 1.1em; position: relative; }}
.bullets li::before {{
  content: "▸"; position: absolute; left: 0; color: var(--accent);
}}
.peel-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: clamp(0.6rem, 2vw, 1.2rem);
  flex: 1; min-height: 0; overflow: hidden;
}}
.peel-grid.peel-single {{ grid-template-columns: 1fr; max-width: 72ch; }}
.peel-card {{
  background: rgba(0,0,0,.25); border: 1px solid rgba(255,255,255,.1);
  border-radius: 12px; padding: clamp(0.6rem, 1.5vh, 1rem);
  overflow: hidden;
}}
.peel-card.peel-0 {{ border-color: rgba(100,120,200,.45); }}
.peel-card.peel-1 {{ border-color: rgba(220,120,160,.45); }}
.peel-label {{
  font-size: clamp(26px, 2.4vw, 30px); font-weight: 700; margin-bottom: 0.45em;
}}
.peel-card ul {{
  list-style: none; font-size: clamp(var(--body-min), 2.3vw, 30px); line-height: 1.4;
}}
.peel-card li {{ margin-bottom: 0.35em; }}
.essay {{
  white-space: pre-wrap; font-family: var(--en);
  font-size: clamp(var(--body-min), 2.3vw, 30px); line-height: 1.45;
  background: rgba(0,0,0,.28); border: 1px solid rgba(255,255,255,.08);
  border-radius: 12px; padding: clamp(0.7rem, 1.8vh, 1.1rem);
  flex: 1; min-height: 0; overflow: hidden;
}}
.essay-block {{
  flex: 1; min-height: 0; overflow: hidden;
  display: flex; flex-direction: column; gap: clamp(0.35rem, 1vh, 0.55rem);
}}
.essay-para {{
  white-space: pre-wrap; font-family: var(--en);
  font-size: clamp(var(--body-min), 2.3vw, 30px); line-height: 1.45;
  background: rgba(0,0,0,.22); border: 1px solid rgba(255,255,255,.08);
  border-radius: 10px; padding: clamp(0.55rem, 1.4vh, 0.85rem);
}}
.annotation {{
  font-size: clamp(var(--body-min), 2.2vw, 28px); color: rgba(244,241,234,.75);
  margin-top: 0.5rem; flex-shrink: 0;
}}
.data-table {{
  width: 100%; border-collapse: collapse;
  font-size: clamp(var(--body-min), 2.2vw, 28px);
  flex: 1; min-height: 0;
}}
.data-table th, .data-table td {{
  border: 1px solid rgba(255,255,255,.12); padding: 0.4em 0.5em;
  vertical-align: top; text-align: left; line-height: 1.35;
}}
.data-table th {{ background: var(--accent-soft); color: #d8efe6; }}
.data-table td.en, .data-table td:nth-child(2) {{ font-family: var(--en); }}
.peel-card li {{ font-family: var(--en); }}
.fix-grid {{
  display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; flex: 1; min-height: 0;
}}
.fix-card {{
  border-radius: 12px; padding: clamp(0.7rem, 1.5vh, 1rem);
  font-size: clamp(var(--body-min), 2.3vw, 28px); line-height: 1.4; overflow: hidden;
}}
.fix-bad {{ background: rgba(232,93,93,.12); border: 1px solid rgba(232,93,93,.4); }}
.fix-good {{ background: rgba(26,95,74,.2); border: 1px solid rgba(26,95,74,.5); }}
.fix-tag {{ font-weight: 700; display: block; margin-bottom: 0.35em; }}
.slide-foot {{
  margin-top: auto; padding-top: 0.5rem; flex-shrink: 0;
  font-family: var(--mono); font-size: clamp(14px, 1.2vw, 16px);
  color: rgba(244,241,234,.4);
}}
.reveal, .reveal-row {{
  opacity: 0; transform: translateY(12px);
  transition: opacity .45s ease, transform .45s ease;
}}
.reveal.is-shown, .reveal-row.is-shown {{
  opacity: 1; transform: none;
}}
.slide-chrome, .slide-title, .slide-foot, .data-table thead {{
  opacity: 1 !important; transform: none !important;
}}
#hint {{
  position: fixed; bottom: 1rem; right: 1.2rem; z-index: 20;
  font-family: var(--mono); font-size: clamp(14px, 1.2vw, 16px);
  color: rgba(244,241,234,.45);
}}
@media (max-width: 900px) {{
  .peel-grid, .fix-grid {{ grid-template-columns: 1fr; }}
}}
@media (prefers-reduced-motion: reduce) {{
  #deck, .reveal, .reveal-row {{ transition: none !important; }}
  .reveal, .reveal-row {{ opacity: 1; transform: none; }}
}}
</style>
</head>
<body>
<main id="deck" aria-live="polite">
{slides_html}
</main>
<div id="hint">空格/点击 逐条呈现 · ← 上页 · →/空格 下一条 · F11 全屏 · S 讲稿</div>
<script>
(function() {{
  const deck = document.getElementById('deck');
  const hint = document.getElementById('hint');
  const slides = Array.from(deck.querySelectorAll('.slide'));
  let idx = 0;
  let notesWin = null;

  function revealItems(slide) {{
    return Array.from(slide.querySelectorAll('.reveal, .reveal-row'))
      .sort((a, b) => (+a.dataset.reveal || 0) - (+b.dataset.reveal || 0));
  }}

  function resetReveal(slide) {{
    revealItems(slide).forEach(el => el.classList.remove('is-shown'));
  }}

  function shownCount(slide) {{
    return revealItems(slide).filter(el => el.classList.contains('is-shown')).length;
  }}

  function revealNext(slide) {{
    const items = revealItems(slide);
    const next = items.find(el => !el.classList.contains('is-shown'));
    if (next) {{ next.classList.add('is-shown'); return true; }}
    return false;
  }}

  function revealPrev(slide) {{
    const items = revealItems(slide).filter(el => el.classList.contains('is-shown'));
    if (!items.length) return false;
    items[items.length - 1].classList.remove('is-shown');
    return true;
  }}

  function revealAll(slide) {{
    revealItems(slide).forEach(el => el.classList.add('is-shown'));
  }}

  function updateHint() {{
    const slide = slides[idx];
    const total = revealItems(slide).length;
    const shown = shownCount(slide);
    const left = total - shown;
    hint.textContent = left > 0
      ? '空格/点击 逐条呈现（还剩 ' + left + ' 条）· ← 回退 · → 下一条/翻页 · F11 全屏 · S 讲稿'
      : '← → 翻页 · F11 全屏 · S 讲稿';
  }}

  function go(n) {{
    idx = Math.max(0, Math.min(slides.length - 1, n));
    deck.style.transform = 'translateX(-' + (idx * 100) + 'vw)';
    slides.forEach((s, i) => s.classList.toggle('is-active', i === idx));
    resetReveal(slides[idx]);
    revealNext(slides[idx]);
    updateHint();
  }}

  function advanceOrNext() {{
    const slide = slides[idx];
    if (!revealNext(slide)) go(idx + 1);
    else updateHint();
  }}

  function retreatOrPrev() {{
    const slide = slides[idx];
    if (!revealPrev(slide)) go(idx - 1);
    else updateHint();
  }}

  function openNotes() {{
    const path = 'speaker-notes.html';
    if (notesWin && !notesWin.closed) {{ notesWin.focus(); return; }}
    notesWin = window.open(path, 'speaker-notes', 'width=520,height=720');
  }}

  function onKey(e) {{
    if (e.key === 's' || e.key === 'S') {{ e.preventDefault(); openNotes(); return; }}
    if (['ArrowRight','ArrowDown','PageDown',' '].includes(e.key)) {{
      e.preventDefault(); advanceOrNext(); return;
    }}
    if (e.key === 'Enter') {{ e.preventDefault(); advanceOrNext(); return; }}
    if (['ArrowLeft','ArrowUp','PageUp','Backspace'].includes(e.key)) {{
      e.preventDefault(); retreatOrPrev(); return;
    }}
    if (e.key === 'Home') go(0);
    if (e.key === 'End') go(slides.length - 1);
  }}

  let touchX = null;
  deck.addEventListener('click', () => advanceOrNext());
  deck.addEventListener('touchstart', e => {{ touchX = e.changedTouches[0].clientX; }}, {{passive:true}});
  deck.addEventListener('touchend', e => {{
    if (touchX == null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 40) go(idx + (dx < 0 ? 1 : -1));
    else advanceOrNext();
    touchX = null;
  }}, {{passive:true}});
  window.addEventListener('keydown', onKey);
  deck.addEventListener('wheel', e => {{
    if (Math.abs(e.deltaY) < 8) return;
    e.preventDefault();
    if (e.deltaY > 0) advanceOrNext();
    else retreatOrPrev();
  }}, {{passive:false}});
  go(0);
}})();
</script>
</body>
</html>
"""


def render_speaker_notes_html(specs: list[dict[str, Any]], deck_title: str) -> str:
    """Teacher-facing notes: AST state transfer + intent (not on student projection)."""
    header = classroom_ast_header()
    entries = speaker_note_entries(specs)
    rows: list[str] = []
    for e in entries:
        rows.append(
            f"""<article class="note" id="slide-{e['index']}">
  <header><span class="num">{e['index']}</span> <strong>{_esc(e['title'])}</strong>
    <span class="tag">{_esc(e['tag'])} · {_esc(e['role_label'])}</span></header>
  <dl>
    <dt>观众进入</dt><dd>{_esc(e['audience_in'])}</dd>
    <dt>本页一件事</dt><dd>{_esc(e['one_thing'])}</dd>
    <dt>观众带走</dt><dd>{_esc(e['audience_out'])}</dd>
  </dl>
</article>"""
        )
    body = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(deck_title)} · 讲稿</title>
<style>
:root {{ --ink:#1a1a1a; --paper:#faf8f5; --accent:#1a5f4a; --sans:"Noto Sans SC",sans-serif; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:var(--sans); background:var(--paper); color:var(--ink); padding:1.2rem; line-height:1.5; }}
h1 {{ font-size:1.35rem; margin-bottom:.5rem; }}
.arc {{ background:#eef5f2; border-left:4px solid var(--accent); padding:.75rem 1rem; margin-bottom:1.2rem; font-size:.95rem; }}
.note {{ border:1px solid #ddd; border-radius:8px; padding:.85rem 1rem; margin-bottom:.75rem; }}
.note header {{ margin-bottom:.45rem; }}
.num {{ display:inline-block; background:var(--accent); color:#fff; border-radius:999px; padding:0 .55em; font-size:.85rem; }}
.tag {{ color:#666; font-size:.85rem; margin-left:.5rem; }}
dl {{ display:grid; grid-template-columns:5.5em 1fr; gap:.25rem .6rem; font-size:.92rem; }}
dt {{ color:#666; }}
</style>
</head>
<body>
<h1>{_esc(deck_title)}</h1>
<div class="arc">
  <p><strong>观众</strong> {_esc(header['audience'])}</p>
  <p><strong>起点</strong> {_esc(header['initial_state'])} → <strong>终点</strong> {_esc(header['desired_state'])}</p>
  <p><strong>张力</strong> {_esc(header['core_tension'])}</p>
</div>
{body}
<p style="margin-top:1.5rem;color:#888;font-size:.85rem">共 {len(entries)} 页 · 与学生屏 classroom-deck.html 页序一致</p>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Build classroom HTML deck from export-data.json")
    ap.add_argument(
        "--export",
        type=Path,
        default=Path(r"D:\Downloads\ppt-work\export-data.json"),
        help="Path to export-data.json",
    )
    ap.add_argument(
        "--stage3",
        type=Path,
        default=Path(r"D:\Downloads\ppt-work\stage3.json"),
        help="Path to stage3.json (phrase/vocab tables)",
    )
    ap.add_argument(
        "--deck-plan",
        type=Path,
        default=None,
        help="Optional custom deck plan JSON",
    )
    ap.add_argument(
        "--slide-plan",
        type=Path,
        default=None,
        help="Humanize slide_plan.json (AST spine for speaker notes)",
    )
    ap.add_argument(
        "--speaker-intent",
        type=Path,
        default=None,
        help="Humanize speaker_intent.md",
    )
    ap.add_argument(
        "--preset",
        choices=("40min", "70min", "80min"),
        default="80min",
        help="Architecture V1 lesson preset (80min = full 3 essays + 高分版 B)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(r"D:\Downloads\ppt-work\humanize-run\classroom-deck.html"),
        help="Output HTML path",
    )
    ap.add_argument(
        "--notes-out",
        type=Path,
        default=None,
        help="Speaker notes HTML (default: sibling speaker-notes.html)",
    )
    args = ap.parse_args()
    data = json.loads(args.export.read_text(encoding="utf-8"))

    slide_plan = args.slide_plan
    speaker_intent = args.speaker_intent
    if slide_plan is None:
        default_plan = Path(r"D:\Downloads\ppt-work\humanize-run\slide_plan.json")
        if default_plan.is_file():
            slide_plan = default_plan
    if speaker_intent is None and slide_plan:
        candidate = slide_plan.parent / "speaker_intent.md"
        speaker_intent = candidate if candidate.is_file() else None

    specs = build_slide_specs(
        data,
        stage3_path=args.stage3 if args.stage3.is_file() else None,
        deck_plan_path=args.deck_plan,
        slide_plan_path=slide_plan,
        speaker_intent_path=speaker_intent,
        preset=args.preset,
    )

    title = specs[0]["title"] if specs else "课堂课件"
    html_out = render_html(specs, title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_out, encoding="utf-8")

    notes_path = args.notes_out or args.out.parent / "speaker-notes.html"
    notes_path.write_text(render_speaker_notes_html(specs, title), encoding="utf-8")

    print(f"Wrote {len(specs)} slides -> {args.out}")
    print(f"Wrote speaker notes -> {notes_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
