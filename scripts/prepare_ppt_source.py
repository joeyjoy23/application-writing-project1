"""从应用文 HTML/Word 导出提取课堂 PPT 源稿、stage3.json 与页型蓝图。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from docx import Document

from scripts.parse_classroom_html import (
    is_classroom_html,
    parse_classroom_html,
    resolve_analysis_export,
)
from scripts.parse_stage3 import parse_stage3_markdown, write_stage3_json
from utils.export_word import STAGE_TITLES

_SECTION_QUESTION = "题目原文"
_EXPORT_DOC_TITLE = "高考英语应用文备课分析报告"

_STAGE_ORDER = [
    ("question", _SECTION_QUESTION),
    ("stage1", STAGE_TITLES[1]),
    ("stage2", STAGE_TITLES[2]),
    ("stage3", STAGE_TITLES[3]),
    ("stage4", STAGE_TITLES[4]),
]

_QTYPE_RE = re.compile(r"题目类型[：:]\s*(.+)")


def _html_to_text(fragment: str) -> str:
    """Rough HTML fragment → plain text with newlines."""
    s = fragment
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p\s*>", "\n\n", s)
    s = re.sub(r"(?i)</li\s*>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "- ", s)
    s = re.sub(r"(?i)</tr\s*>", "\n", s)
    s = re.sub(r"(?i)</t[dh]\s*>", "\t", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_export_html(path: Path) -> dict[str, str | None]:
    raw = path.read_text(encoding="utf-8")
    meta_m = re.search(
        r'<p class="doc-meta">([^<]*)</p>',
        raw,
        flags=re.IGNORECASE,
    )
    meta = html_module_unescape(meta_m.group(1).strip()) if meta_m else ""
    qtype_m = re.search(
        r'<p class="qtype">题目类型[：:]\s*([^<]+)</p>',
        raw,
        flags=re.IGNORECASE,
    )
    question_type_label = qtype_m.group(1).strip() if qtype_m else ""
    sections: dict[str, str] = {}
    for m in re.finditer(
        r'<section class="section">\s*<h2>(.*?)</h2>\s*'
        r'<div class="section-body">(.*?)</div>\s*</section>',
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        title = html_module_unescape(re.sub(r"<[^>]+>", "", m.group(1)).strip())
        body = _html_to_text(m.group(2))
        if title:
            sections[title] = body
    return _normalize_sections(sections, meta, question_type_label)


def html_module_unescape(text: str) -> str:
    import html as html_module

    return html_module.unescape(text)


def parse_export_docx(path: Path) -> dict[str, str | None]:
    doc = Document(str(path))
    sections: dict[str, list[str]] = {}
    current: str | None = None
    meta = ""
    question_type_label = ""

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            if current:
                sections.setdefault(current, []).append("")
            continue
        if text == _EXPORT_DOC_TITLE:
            continue
        if text.startswith("生成时间："):
            meta = text
            current = None
            continue
        m = _QTYPE_RE.match(text)
        if m:
            question_type_label = m.group(1).strip()
            continue
        if _is_stage_heading(para, text):
            current = text
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(text)

    flat = {k: "\n".join(v).strip() for k, v in sections.items()}
    return _normalize_sections(flat, meta, question_type_label)


def _is_stage_heading(para, text: str) -> bool:
    known = {_SECTION_QUESTION, *STAGE_TITLES.values()}
    if text in known:
        return True
    if para.runs and para.runs[0].bold and text.startswith("Stage "):
        return True
    return text in ("题目原文",)


def _empty_export_data() -> dict[str, str | None]:
    return {
        "meta": None,
        "question_type_label": None,
        "question": None,
        "stage1": None,
        "stage2": None,
        "stage3": None,
        "stage4": None,
    }


def _normalize_sections(
    sections: dict[str, str],
    meta: str,
    question_type_label: str,
) -> dict[str, str | None]:
    out: dict[str, str | None] = {
        "meta": meta or None,
        "question_type_label": question_type_label or None,
    }
    for key, section_title in _STAGE_ORDER:
        out[key] = sections.get(section_title) or None
    # fuzzy match Stage headings if spacing differs
    for sec_title, body in sections.items():
        for key, canonical in _STAGE_ORDER:
            if out.get(key):
                continue
            if canonical in sec_title or sec_title in canonical:
                out[key] = body
    return out



_ESSAY_VERSION_LABELS = ("PEEL", "基础版", "进阶版", "高分版")
_STAGE4_INTEGRATED_PLACEMENTS = (
    ("after_stage1", "动笔易错", ("易错", "预警", "避坑", "错误")),
    ("after_stage2", "讲评活动", ("活动", "教学", "讲评", "课堂")),
    ("after_stage3", "当堂迁移", ("迁移", "练习", "课后")),
)


def _trim_bullet(line: str, max_len: int = 120) -> str:
    s = re.sub(r"\s+", " ", line.strip())
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _extract_section_key_points(text: str, max_bullets: int = 5) -> list[str]:
    """Heuristic bullets from headings, list markers, and short lines."""
    if not text.strip():
        return []
    points: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"^#{1,4}\s+(.+)$", text, flags=re.MULTILINE):
        p = _trim_bullet(m.group(1))
        if p and p not in seen:
            seen.add(p)
            points.append(p)
    for m in re.finditer(r"^[-*•]\s+(.+)$", text, flags=re.MULTILINE):
        p = _trim_bullet(m.group(1))
        if p and p not in seen:
            seen.add(p)
            points.append(p)
        if len(points) >= max_bullets:
            break
    if len(points) < max_bullets:
        for m in re.finditer(r"^\d+[.)]\s+(.+)$", text, flags=re.MULTILINE):
            p = _trim_bullet(m.group(1))
            if p and p not in seen:
                seen.add(p)
                points.append(p)
            if len(points) >= max_bullets:
                break
    return points[:max_bullets]


def _essay_version_slides(stage2: str) -> list[tuple[str, list[str]]]:
    slides: list[tuple[str, list[str]]] = []
    body = stage2.strip()
    if not body:
        return slides
    lower = body.lower()
    has_peel = "peel" in lower or "PEEL" in body
    if has_peel:
        peel_pts = _extract_section_key_points(body, 4)
        slides.append(("PEEL 骨架", peel_pts or ["段意与功能句（见源稿 Stage 2）"]))
    for label in ("基础版", "进阶版", "高分版"):
        if label in body:
            slides.append(
                (
                    f"{label}范文",
                    ["含完整英文范文原文", "中文点评可拆页或缩小，英文正文不可删"],
                )
            )
    if not slides:
        slides.append(
            (
                "范文（Stage 2）",
                ["含完整英文范文原文", *_extract_section_key_points(body, 3)],
            )
        )
    return slides


def _stage3_slides(stage3: str) -> list[tuple[str, list[str]]]:
    if not stage3.strip():
        return []
    slides: list[tuple[str, list[str]]] = []
    chunks = re.split(r"\n(?=#{1,3}\s)", stage3.strip())
    if len(chunks) <= 1:
        pts = _extract_section_key_points(stage3, 5)
        slides.append(("功能句型与话题词块", pts or ["见源稿 Stage 3"]))
        return slides
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        hm = re.match(r"^#{1,3}\s+(.+)$", chunk, flags=re.MULTILINE)
        title = hm.group(1).strip() if hm else "句型与词块"
        pts = _extract_section_key_points(chunk, 4)
        slides.append((title, pts or ["见源稿 Stage 3"]))
    return slides


def _stage4_integrated_slides(stage4: str) -> list[tuple[str, str, list[str]]]:
    """Return (placement, title, bullets) for Stage4 woven into main flow."""
    if not stage4.strip():
        return []
    slides: list[tuple[str, str, list[str]]] = []
    for placement, title, keywords in _STAGE4_INTEGRATED_PLACEMENTS:
        if not any(k in stage4 for k in keywords):
            continue
        if placement == "after_stage1":
            from scripts.classroom_content_filter import parse_stage4_student_from_export

            bullets = parse_stage4_student_from_export(stage4)["warn"][:3]
            if not bullets:
                bullets = [
                    "❌ 理由空泛：未结合设计元素与主题",
                    "❌ 语气不当：过于正式，不符合交际身份",
                    "❌ 元素模糊：未具体描述海报视觉细节",
                ]
        elif placement == "after_stage2":
            from scripts.classroom_content_filter import parse_stage4_student_from_export

            bullets = parse_stage4_student_from_export(stage4)["activities"][:4]
            if not bullets:
                bullets = [
                    "元素 → 主题：用词块造句，绑定画面细节",
                    "逻辑链：Firstly / Secondly 写两个理由",
                ]
        else:
            from scripts.classroom_content_filter import parse_stage4_student_from_export

            bullets = parse_stage4_student_from_export(stage4)["migration"][:3]
            if not bullets:
                bullets = [
                    "片段升级：换主题，保持 PEEL 结构",
                    "完整迁移：环保海报选题（Lucy 两版本）",
                ]
        slides.append((placement, title, bullets))
    return slides


def build_classroom_outline(data: dict[str, str | None]) -> str:
    """Draft/fallback outline via rule-based parsing — not the primary path.

    Cursor Agent should author ``yingyongwen-outline.md`` by reading the export
    or ``yingyongwen-source.md`` and understanding content. Use ``--outline draft``
  only for offline / 快速模式 when no Agent is available.
    """
    lines = [
        "# 应用文课堂 PPT 大纲（PPT大纲）",
        "",
        "> **认知顺序**：题目 → Stage1 审题 → **动笔易错（Stage4 融入）** → Stage2 范文"
        "（**范文原文必须完整上屏**）→ **讲评活动（Stage4）** → Stage3 句型词块"
        " → **当堂迁移（Stage4）**。Stage4 与 Stage1–3 同权，**不得**堆在末尾附录。",
        "",
    ]
    if data.get("question_type_label"):
        lines.append(f"**题目类型：** {data['question_type_label']}")
        lines.append("")

    slide_no = 1

    def add_slide(title: str, bullets: list[str]) -> None:
        nonlocal slide_no
        lines.append(f"## Slide {slide_no}. {title}")
        for b in bullets:
            lines.append(f"- {b}")
        lines.append("")
        slide_no += 1

    q = (data.get("question") or "").strip()
    if q:
        first_line = _trim_bullet(q.splitlines()[0], 80)
        add_slide(
            "题目页",
            [
                first_line or "题目原文（见源稿）",
                "题型标签 + 元信息",
            ],
        )

    s1 = (data.get("stage1") or "").strip()
    if s1:
        for sub_title, default in (
            ("审题 · 题型与任务", ["写作任务", "时态人称"]),
            ("审题 · 必写要点", ["mandatory points / 硬性要点"]),
            ("审题 · 结构与避坑", ["段落规划", "一句大实话"]),
        ):
            pts = _extract_section_key_points(s1, 4)
            add_slide(sub_title, pts[:4] if pts else default)

    stage4 = (data.get("stage4") or "").strip()
    integrated = _stage4_integrated_slides(stage4)
    after_s1 = [s for s in integrated if s[0] == "after_stage1"]
    for _placement, title, bullets in after_s1:
        add_slide(title, bullets)

    s2 = (data.get("stage2") or "").strip()
    for title, bullets in _essay_version_slides(s2):
        add_slide(title, bullets)

    after_s2 = [s for s in integrated if s[0] == "after_stage2"]
    for _placement, title, bullets in after_s2:
        add_slide(title, bullets)

    s3 = (data.get("stage3") or "").strip()
    for title, bullets in _stage3_slides(s3):
        add_slide(title, bullets)

    after_s3 = [s for s in integrated if s[0] == "after_stage3"]
    for _placement, title, bullets in after_s3:
        add_slide(title, bullets)

    lines.append(
        f"**合计建议页数（含 Stage4 融入）：** 约 {max(slide_no - 1, 0)} 页（以 "
        "`yingyongwen-blueprint.json` 为准）"
    )
    lines.append("")
    return "\n".join(lines)

def build_source_markdown(data: dict[str, str | None]) -> str:
    lines = ["# 应用文备课 · 课堂 PPT 源稿", ""]
    if data.get("meta"):
        lines.extend([f"> {data['meta']}", ""])
    if data.get("question_type_label"):
        lines.extend([f"**题目类型：** {data['question_type_label']}", ""])
    labels = {
        "question": "题目原文",
        "stage1": STAGE_TITLES[1],
        "stage2": STAGE_TITLES[2],
        "stage3": STAGE_TITLES[3],
        "stage4": STAGE_TITLES[4],
    }
    for key in ("question", "stage1", "stage2", "stage3", "stage4"):
        body = (data.get(key) or "").strip()
        if not body:
            continue
        lines.extend([f"## {labels[key]}", "", body, ""])
    return "\n".join(lines).rstrip() + "\n"


def build_blueprint(data: dict[str, str | None]) -> dict:
    def _pages(key: str, default: int, extra: int = 0) -> int:
        text = (data.get(key) or "").strip()
        if not text:
            return 0
        bonus = min(extra, len(text) // 1200)
        return default + bonus

    page_types = [
        {
            "id": "A",
            "name": "题目页",
            "source": "question",
            "suggested_pages": 1 if data.get("question") else 0,
        },
        {
            "id": "B",
            "name": "审题",
            "source": "stage1",
            "suggested_pages": _pages("stage1", 3, 1),
        },
        {
            "id": "C",
            "name": "范文",
            "source": "stage2",
            "suggested_pages": _pages("stage2", 4, 2),
        },
        {
            "id": "D",
            "name": "句型词块",
            "source": "stage3",
            "role": "primary",
            "suggested_pages": _pages("stage3", 3, 1),
        },
        {
            "id": "E",
            "name": "Stage4 融入",
            "source": "stage4",
            "role": "integrated",
            "placement": [
                "after_stage1: 动笔易错",
                "after_stage2: 讲评活动",
                "after_stage3: 当堂迁移",
            ],
            "suggested_pages": min(_pages("stage4", 3, 1), 5) if data.get("stage4") else 0,
            "note": "woven into main flow; not appendix",
        },
    ]
    total = sum(p["suggested_pages"] for p in page_types)
    return {
        "page_types": page_types,
        "suggested_total_pages": max(total, 20) if total else 0,
        "target_detailed_pages": 22,
        "default_aspect": "16:9",
        "default_brand_hint": "education",
        "question_type_label": data.get("question_type_label"),
    }


def prepare_ppt_source(
    export_path: Path,
    out_dir: Path,
    outline: str = "skip",
    *,
    write_classroom_data: bool = False,
) -> tuple[Path, Path] | tuple[Path, Path, Path]:
    """Extract source markdown and blueprint JSON from an export.

    ``outline``:
    - ``skip`` (default): write source + blueprint only; Agent authors outline.
    - ``draft``: also write rule-based ``yingyongwen-outline.md`` (fallback).

    If ``export_path`` is 课件 HTML (``-课件.html``), the sibling **分析报告**
    HTML is parsed for Stage1–4; PPT structure uses Architecture V1 by default.
    Set ``write_classroom_data=True`` only with ``--classroom-html`` legacy mode.
    """
    if outline not in ("skip", "draft"):
        raise ValueError(f"outline must be 'skip' or 'draft', got: {outline}")

    suffix = export_path.suffix.lower()
    classroom_data: dict | None = None
    analysis_path: Path | None = None
    if suffix == ".html":
        if is_classroom_html(export_path):
            analysis_path = resolve_analysis_export(export_path)
            if analysis_path.is_file() and analysis_path != export_path:
                print(
                    f"课件 HTML 作输入别名 → 分析源：{analysis_path}（PPT 走 Architecture V1）"
                )
            elif analysis_path.is_file():
                print(
                    f"警告：未找到 sibling 分析 HTML，尝试解析：{analysis_path}",
                    file=sys.stderr,
                )
            else:
                print(
                    f"警告：无法解析分析 HTML（课件：{export_path}）",
                    file=sys.stderr,
                )
            if write_classroom_data:
                classroom_data = parse_classroom_html(export_path)
            data = (
                parse_export_html(analysis_path)
                if analysis_path.is_file()
                else _empty_export_data()
            )
        else:
            data = parse_export_html(export_path)
    elif suffix == ".docx":
        data = parse_export_docx(export_path)
    else:
        raise ValueError(f"Unsupported export format: {suffix} (use .html or .docx)")

    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "yingyongwen-source.md"
    json_path = out_dir / "yingyongwen-blueprint.json"
    md_path.write_text(build_source_markdown(data), encoding="utf-8")
    json_path.write_text(
        json.dumps(build_blueprint(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    export_data_path = out_dir / "export-data.json"
    export_data_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if classroom_data is not None:
        classroom_data_path = out_dir / "classroom-data.json"
        classroom_data_path.write_text(
            json.dumps(classroom_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"课件数据：{classroom_data_path}（{len(classroom_data.get('slides', []))} 页）")
    stage3_text = (data.get("stage3") or "").strip()
    if stage3_text:
        write_stage3_json(parse_stage3_markdown(stage3_text), out_dir / "stage3.json")
    if outline == "draft":
        outline_path = out_dir / "yingyongwen-outline.md"
        outline_path.write_text(build_classroom_outline(data), encoding="utf-8")
        return md_path, json_path, outline_path
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract classroom PPT source from 应用文 export")
    parser.add_argument("export_path", type=Path, help="Path to exported .html or .docx")
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        required=True,
        help="Output directory for source markdown and blueprint JSON",
    )
    parser.add_argument(
        "--outline",
        choices=("skip", "draft"),
        default="skip",
        help="Outline mode: skip (Agent writes outline; default) or draft (rule-based fallback)",
    )
    args = parser.parse_args(argv)
    if not args.export_path.is_file():
        print(f"File not found: {args.export_path}", file=sys.stderr)
        return 1
    result = prepare_ppt_source(args.export_path, args.out_dir, outline=args.outline)
    for path in result:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
