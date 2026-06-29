#!/usr/bin/env python
"""Read-only SVG validator for yingyongwen classroom PPT (PPT_LAYOUT_LAW §5)."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MIN_BODY_PX = 35
MIN_TITLE_PX = 51
MAX_ENGLISH_LINE_CHARS = 58
PANEL_HEIGHT_RATIO = 1.6

FORBIDDEN_PATTERNS = [
    (re.compile(r"Joyverse", re.IGNORECASE), "Joyverse branding"),
    (re.compile(r"\b\d+\s*/\s*\d+\b"), "page number (N / M)"),
    (re.compile(r"page\s*\d+\s*of\s*\d+", re.IGNORECASE), "page number (page N of M)"),
]

FONT_SIZE_RE = re.compile(r'font-size="(\d+(?:\.\d+)?)"')
RECT_RE = re.compile(
    r'<rect[^>]*\by="(\d+(?:\.\d+)?)"[^>]*\bheight="(\d+(?:\.\d+)?)"[^>]*(?:rx=|fill="#(?:F5F3FF|FEF2F2|ECFEFF|FFF))',
    re.IGNORECASE,
)
TEXT_BLOCK_RE = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)
TSPAN_RE = re.compile(r"<tspan[^>]*>([^<]*)</tspan>")
PLAIN_TEXT_RE = re.compile(r">([^<]+)<")


@dataclass
class SlideReport:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _extract_visible_text(svg: str) -> list[str]:
    lines: list[str] = []
    for block in TEXT_BLOCK_RE.findall(svg):
        tspans = TSPAN_RE.findall(block)
        if tspans:
            lines.extend(t.strip() for t in tspans if t.strip())
        else:
            plain = PLAIN_TEXT_RE.findall(block)
            lines.extend(p.strip() for p in plain if p.strip() and not p.startswith("<?"))
    return lines


def _estimate_content_height(text_line_count: int) -> float:
    if text_line_count <= 0:
        return 80.0
    return 48.0 + text_line_count * 48.0


def validate_svg_file(path: Path) -> SlideReport:
    report = SlideReport(path=path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.errors.append(f"cannot read file: {exc}")
        return report

    for pattern, label in FORBIDDEN_PATTERNS:
        if pattern.search(content):
            report.errors.append(f"forbidden content: {label}")

    for match in FONT_SIZE_RE.finditer(content):
        size = float(match.group(1))
        if size < MIN_BODY_PX:
            report.errors.append(
                f"font-size {size}px below body minimum {MIN_BODY_PX}px (~26pt)"
            )

    header_match = re.search(r'id="header".*?</g>', content, re.DOTALL)
    if header_match:
        header_block = header_match.group(0)
        for match in FONT_SIZE_RE.finditer(header_block):
            size = float(match.group(1))
            if size >= 48 and size < MIN_TITLE_PX:
                report.errors.append(
                    f"page title font-size {size}px below minimum {MIN_TITLE_PX}px (~38pt)"
                )

    for line in _extract_visible_text(content):
        if re.search(r"[A-Za-z]", line) and len(line) > MAX_ENGLISH_LINE_CHARS:
            if "font-family" in content and "Times New Roman" in content:
                report.warnings.append(
                    f"english line may exceed {MAX_ENGLISH_LINE_CHARS} chars: "
                    f"{line[:40]}..."
                )

    text_lines = _extract_visible_text(content)
    est_height = _estimate_content_height(len(text_lines))
    for rect_match in RECT_RE.finditer(content):
        height = float(rect_match.group(2))
        if height > est_height * PANEL_HEIGHT_RATIO and height > 200:
            report.warnings.append(
                f"possible empty panel: rect height {height:.0f}px "
                f"vs estimated content ~{est_height:.0f}px"
            )

    return report


def validate_directory(svg_dir: Path) -> tuple[list[SlideReport], bool]:
    files = sorted(svg_dir.glob("*.svg"))
    if not files:
        return [], False

    reports: list[SlideReport] = []
    for svg_file in files:
        reports.append(validate_svg_file(svg_file))

    ok = all(not r.errors for r in reports)
    return reports, ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate classroom PPT SVGs against PPT_LAYOUT_LAW §5 (read-only)."
    )
    parser.add_argument(
        "svg_path",
        type=Path,
        help="Path to svg_final directory or a single .svg file",
    )
    args = parser.parse_args(argv)

    target = args.svg_path
    if target.is_dir():
        reports, ok = validate_directory(target)
    elif target.is_file() and target.suffix.lower() == ".svg":
        report = validate_svg_file(target)
        reports, ok = [report], not report.errors
    else:
        print(f"error: not a directory or .svg file: {target}", file=sys.stderr)
        return 2

    error_count = 0
    warn_count = 0
    for report in reports:
        if not report.errors and not report.warnings:
            continue
        print(f"\n{report.path.name}:")
        for err in report.errors:
            print(f"  ERROR: {err}")
            error_count += 1
        for warn in report.warnings:
            print(f"  WARN:  {warn}")
            warn_count += 1

    total = len(reports)
    print(f"\nChecked {total} file(s): {error_count} error(s), {warn_count} warning(s)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
