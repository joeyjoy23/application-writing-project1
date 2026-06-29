"""Parse Joyverse classroom slide HTML (section.slide) into structured slides."""

from __future__ import annotations

import html as html_module
import re
from pathlib import Path
from typing import Any


def is_classroom_html(path: Path) -> bool:
    if path.suffix.lower() != ".html":
        return False
    head = path.read_text(encoding="utf-8")[:8000]
    return 'class="slide"' in head and "section-body" not in head[:4000]


def is_analysis_export_html(path: Path) -> bool:
    if path.suffix.lower() != ".html":
        return False
    head = path.read_text(encoding="utf-8")[:8000]
    return 'class="section"' in head and "section-body" in head


def resolve_analysis_export(classroom_or_export: Path) -> Path:
    """If path is 课件 HTML, prefer sibling analysis HTML for full Stage1–4 text."""
    p = classroom_or_export.expanduser().resolve()
    if not p.is_file():
        return p
    if is_analysis_export_html(p):
        return p
    if is_classroom_html(p):
        sibling = p.parent / p.name.replace("-课件", "")
        if sibling.is_file() and is_analysis_export_html(sibling):
            return sibling
    return p


def _strip_tags(fragment: str) -> str:
    s = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    s = re.sub(r"(?i)</p\s*>", "\n", s)
    s = re.sub(r"(?i)</li\s*>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html_module.unescape(s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _first(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    return _strip_tags(m.group(1)) if m else ""


def _all_li(text: str) -> list[str]:
    items: list[str] = []
    for m in re.finditer(r"(?i)<li[^>]*>(.*?)</li>", text, flags=re.DOTALL):
        line = _strip_tags(m.group(1))
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            items.append(line)
    return items


def _table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    headers: list[str] = []
    rows: list[list[str]] = []
    thead = re.search(r"(?i)<thead>(.*?)</thead>", text, flags=re.DOTALL)
    if thead:
        headers = [
            _strip_tags(th)
            for th in re.findall(r"(?i)<th[^>]*>(.*?)</th>", thead.group(1), re.DOTALL)
        ]
    tbody = re.search(r"(?i)<tbody>(.*?)</tbody>", text, flags=re.DOTALL)
    body = tbody.group(1) if tbody else text
    for tr in re.finditer(r"(?i)<tr[^>]*>(.*?)</tr>", body, flags=re.DOTALL):
        cells = [
            _strip_tags(td)
            for td in re.findall(r"(?i)<t[dh][^>]*>(.*?)</t[dh]>", tr.group(1), re.DOTALL)
        ]
        if cells:
            rows.append(cells)
    return headers, rows


def parse_classroom_html(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    slides: list[dict[str, Any]] = []
    for m in re.finditer(
        r'<section\s+class="slide[^"]*"[^>]*data-title="([^"]*)"[^>]*>(.*?)</section>',
        raw,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        data_title = m.group(1)
        block = m.group(2)
        tag = _first(r'(?is)<span\s+class="tag"[^>]*>(.*?)</span>', block)
        h1 = _first(r"(?is)<h1[^>]*>(.*?)</h1>", block)
        h2 = _first(r"(?is)<h2[^>]*>(.*?)</h2>", block)
        subtitle = _first(r'(?is)<p\s+class="subtitle"[^>]*>(.*?)</p>', block)
        quote = _first(r'(?is)<p\s+class="quote"[^>]*>(.*?)</p>', block)
        en = _first(r'(?is)<p\s+class="en"[^>]*>(.*?)</p>', block)
        card_ps = [
            _strip_tags(p)
            for p in re.findall(r'(?is)<div\s+class="card"[^>]*>(.*?)</div>', block)
        ]
        bullets = _all_li(block)
        headers, rows = _table_rows(block)
        slides.append(
            {
                "data_title": data_title,
                "tag": tag,
                "h1": h1,
                "h2": h2,
                "subtitle": subtitle,
                "quote": quote,
                "en": en,
                "bullets": bullets,
                "cards": card_ps,
                "table_headers": headers,
                "table_rows": rows,
            }
        )
    qtype = ""
    for s in slides:
        h2 = s.get("h2", "")
        if "观点" in h2 or "题目类型" in h2:
            qtype = h2.replace("题目类型：", "").strip()
            break
    return {
        "format": "classroom_html",
        "source_path": str(path),
        "question_type_label": qtype or None,
        "slides": slides,
    }
