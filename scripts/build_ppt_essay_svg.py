#!/usr/bin/env python
"""Generate ppt-master essay slide SVGs with layout engine (same rules as V1)."""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from essay_format import classroom_body_paragraphs

FONT_ESSAY = 37  # SVG px → ~27.75pt in PPT ( classroom min ~26pt )
FONT_FOOTER = 35  # annotation slightly smaller than body
FONT_TITLE = 51
X0 = 56
X_INDENT = 88
X_RIGHT = 56  # right margin
Y_START = 172  # below badge (pill ends ~128) + clear gap
Y_MAX = 678
FOOTER_MAX_Y = 700
FOOTER_GAP = 28
# Times New Roman 37px average char width on 1280 canvas
CHAR_PX = 16.5


def _wrap_widths() -> tuple[int, int]:
    """Continuation line vs first-line (indented) max chars from pixel budget."""
    right = 1280 - X_RIGHT
    wrap_full = int((right - X0) / CHAR_PX)
    wrap_indent = int((right - X_INDENT) / CHAR_PX)
    return max(52, wrap_full), max(48, wrap_indent)


def _wrap_paragraph(block: str, wrap_indent: int, wrap_full: int) -> list[str]:
    """Wrap one paragraph; first line uses narrower budget (indent offset)."""
    words = block.strip().split()
    if not words:
        return []
    lines: list[str] = []
    current: list[str] = []
    limit = wrap_indent

    for word in words:
        trial = " ".join(current + [word]) if current else word
        if len(trial) <= limit:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
            limit = wrap_full
    if current:
        lines.append(" ".join(current))
    return lines

DEFAULT_PROJECT = Path(
    r"C:\Users\Joey\tools\ppt-master\projects\yingyongwen-mental-health-v3_ppt169_20260620"
)

ESSAY_OUTPUTS = (
    "09_essay_basic.svg",
    "10_essay_advanced_a.svg",
    "11_essay_advanced_b.svg",
)


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _word_count(paragraphs: list[str]) -> int:
    return len(re.findall(r"\b[\w']+\b", " ".join(paragraphs)))


def _footer_annotation(annotation: str, word_count: int) -> str:
    """Footer uses same word count as badge (on-screen body, not full letter)."""
    ann = annotation.strip().strip("（）()")
    rest = re.sub(r"^\d+\s*words\s*(?:·\s*)?", "", ann, flags=re.IGNORECASE).strip()
    if rest:
        return f"{word_count} words · {rest}"
    return f"{word_count} words"


def _badge_path(width: int) -> str:
    w = max(200, min(420, width))
    return (
        f"M56,92 H{56 + w} A8,8 0 0 1 {64 + w},100 V120 A8,8 0 0 1 {56 + w},128 "
        f"H56 A8,8 0 0 1 48,120 V100 A8,8 0 0 1 56,92 Z"
    )


def _layout_metrics(paragraphs: list[str]) -> tuple[int, int, int, int]:
    """Return (line_dy, para_gap, wrap_full, wrap_indent) from essay length."""
    wrap_full, wrap_indent = _wrap_widths()
    total_chars = sum(len(p) for p in paragraphs)
    if total_chars >= 650:
        return 36, 14, wrap_full, wrap_indent
    if total_chars >= 450:
        return 38, 14, wrap_full, wrap_indent
    return 40, 16, wrap_full, wrap_indent


def layout_essay_lines(
    paragraphs: list[str],
) -> tuple[list[tuple[str, int, int]], int]:
    """Return ([(text, x, y), ...], last_body_y)."""
    line_dy, para_gap, wrap_full, wrap_indent = _layout_metrics(paragraphs)

    for _ in range(16):
        lines: list[tuple[str, int, int]] = []
        y = Y_START
        for pi, block in enumerate(paragraphs):
            wrapped = _wrap_paragraph(block, wrap_indent, wrap_full)
            for li, line in enumerate(wrapped):
                x = X_INDENT if li == 0 else X0
                lines.append((line, x, y))
                y += line_dy
            if pi < len(paragraphs) - 1:
                y += para_gap
        last_y = lines[-1][2] if lines else Y_START
        if last_y <= Y_MAX:
            return lines, last_y
        if wrap_full < 82:
            wrap_full += 2
            wrap_indent = min(wrap_indent + 2, wrap_full - 2)
        elif line_dy > 30:
            line_dy -= 2
            para_gap = max(8, para_gap - 2)
        else:
            return lines, last_y

    return lines, lines[-1][2] if lines else Y_START


def build_essay_svg(
    *,
    title: str,
    badge_label: str,
    essay_text: str,
    annotation: str,
) -> str:
    paragraphs = classroom_body_paragraphs(essay_text)
    if len(paragraphs) != 3:
        raise ValueError(f"expected 3 body paragraphs, got {len(paragraphs)}: {title}")

    lines, last_y = layout_essay_lines(paragraphs)
    reveal_parts: list[str] = []
    for idx, (line, x, y) in enumerate(lines, start=1):
        reveal_parts.append(
            f'  <g id="reveal-{idx:02d}">\n'
            f'    <text x="{x}" y="{y}" font-family="Times New Roman, Times, serif" '
            f'font-size="{FONT_ESSAY}" fill="#1E293B">{_esc(line)}</text>\n'
            f"  </g>"
        )

    footer_block = ""
    words = _word_count(paragraphs)
    ann = _footer_annotation(annotation, words) if annotation.strip() else ""
    footer_y = last_y + FOOTER_GAP + 4
    if ann and footer_y <= FOOTER_MAX_Y:
        footer_block = (
            f'  <g id="reveal-footer">\n'
            f'    <text x="{X0}" y="{footer_y}" font-family="Microsoft YaHei, Arial, sans-serif" '
            f'font-size="{FONT_FOOTER}" fill="#64748B">{_esc(ann)}</text>\n'
            f"  </g>"
        )

    badge_w = int(len(badge_label) * 18 + 48)
    badge_text = f"{words} words"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">\n'
        f'  <rect width="1280" height="720" fill="#FFFFFF" />\n'
        f'  <g id="header">\n'
        f'    <rect x="0" y="0" width="1280" height="76" fill="#6366F1" />\n'
        f'    <rect x="0" y="76" width="1280" height="4" fill="#14B8A6" />\n'
        f'    <text x="48" y="52" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_TITLE}" font-weight="bold" fill="#FFFFFF">{_esc(title)}</text>\n'
        f"  </g>\n"
        f'  <g id="reveal-badge">\n'
        f'    <path fill="#14B8A6" d="{_badge_path(badge_w)}" />\n'
        f'    <text x="64" y="118" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_ESSAY}" font-weight="bold" fill="#FFFFFF">{_esc(badge_text)}</text>\n'
        f"  </g>\n"
        f"{chr(10).join(reveal_parts)}\n"
        f"{footer_block}\n"
        f"</svg>\n"
    )


def essay_specs_from_deck() -> list[dict]:
    _root = Path(__file__).resolve().parents[1]
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
    from scripts.generate_classroom_pptx import build_mental_health_deck

    essays = [s for s in build_mental_health_deck() if s["type"] == "essay"]
    if len(essays) != 3:
        raise RuntimeError(f"expected 3 essay slides in deck, got {len(essays)}")
    return essays


def write_essay_svgs(project_dir: Path) -> list[Path]:
    out_dir = project_dir / "svg_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    essays = essay_specs_from_deck()
    written: list[Path] = []
    for filename, spec in zip(ESSAY_OUTPUTS, essays, strict=True):
        svg = build_essay_svg(
            title=spec["title"],
            badge_label=spec.get("badge") or spec["title"],
            essay_text=spec["essay_text"],
            annotation=spec.get("annotation", ""),
        )
        path = out_dir / filename
        path.write_text(svg, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build essay SVG slides for ppt-master")
    parser.add_argument(
        "--project",
        type=Path,
        default=DEFAULT_PROJECT,
        help="ppt-master project directory",
    )
    args = parser.parse_args(argv)
    paths = write_essay_svgs(args.project)
    for p in paths:
        print(f"Wrote: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
