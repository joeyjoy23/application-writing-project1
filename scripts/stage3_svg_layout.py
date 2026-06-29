"""SVG layout templates for Stage 3 phrase-tier and vocab-table slides."""

from __future__ import annotations

import html
import textwrap
from typing import Any

FONT_TITLE = 51
FONT_BODY = 30
FONT_CN = 26
FONT_SMALL = 24
FONT_LABEL = 22
X0 = 48
PANEL_X = 48
PANEL_W = 1184
INSET_X = 80
TEXT_X = 96
Y0 = 100
Y_MAX = 680
LINE_EN = 34
LINE_CN = 28
LABEL_TO_ENG = 38
TIER_GAP = 22

_TIER_BAR = {"基础句": "#94A3B8", "进阶句": "#6366F1", "高级句": "#7C3AED"}
_VOCAB_HEAD = {"必备级": "#E2E8F0", "进阶级": "#DDD6FE", "亮点级": "#C4B5FD"}


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _wrap(text: str, width: int = 72) -> list[str]:
    if len(text) <= width:
        return [text]
    return textwrap.wrap(text, width=width) or [text]


def render_header(title: str) -> str:
    return (
        '  <g id="header">\n'
        '    <rect x="0" y="0" width="1280" height="76" fill="#6366F1" />\n'
        '    <rect x="0" y="76" width="1280" height="4" fill="#14B8A6" />\n'
        f'    <text x="{X0}" y="52" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_TITLE}" font-weight="bold" fill="#FFFFFF">{_esc(title)}</text>\n'
        "  </g>"
    )


def _svg_open() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" '
        'width="1280" height="720">\n'
        '  <rect width="1280" height="720" fill="#FFFFFF" />\n'
    )


def _tier_block(
    parts: list[str],
    reveal_idx: int,
    y: int,
    level: str,
    tier: dict[str, Any],
) -> tuple[int, int]:
    """Render one tier block; return (next_reveal_idx, next_y)."""
    bar = _TIER_BAR.get(level, "#6366F1")
    label_baseline = y + 20
    bar_top = label_baseline - 18

    parts.append(
        f'  <g id="reveal-{reveal_idx:02d}">\n'
        f'    <rect x="{INSET_X}" y="{bar_top}" width="6" height="22" rx="2" fill="{bar}"/>\n'
        f'    <text x="{TEXT_X}" y="{label_baseline}" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_LABEL}" font-weight="bold" fill="{bar}">{_esc(level)}</text>\n'
        f"  </g>"
    )
    reveal_idx += 1
    cy = label_baseline + LABEL_TO_ENG

    eng_lines = _wrap(tier["english"], 82)
    for ln in eng_lines:
        parts.append(
            f'  <g id="reveal-{reveal_idx:02d}">\n'
            f'    <text x="{TEXT_X}" y="{cy}" font-family="Times New Roman, Times, serif" '
            f'font-size="{FONT_BODY}" fill="#1E293B">{_esc(ln)}</text>\n'
            f"  </g>"
        )
        reveal_idx += 1
        cy += LINE_EN

    if level != "基础句" and tier.get("chinese"):
        cy += 6
        for ln in _wrap(tier["chinese"], 84):
            parts.append(
                f'  <g id="reveal-{reveal_idx:02d}">\n'
                f'    <text x="{TEXT_X}" y="{cy}" font-family="Microsoft YaHei, Arial, sans-serif" '
                f'font-size="{FONT_CN}" fill="#64748B">{_esc(ln)}</text>\n'
                f"  </g>"
            )
            reveal_idx += 1
            cy += LINE_CN

    if level == "高级句" and tier.get("high_score"):
        cy += 4
        for ln in _wrap(tier["high_score"], 84):
            parts.append(
                f'  <g id="reveal-{reveal_idx:02d}">\n'
                f'    <text x="{TEXT_X}" y="{cy}" font-family="Microsoft YaHei, Arial, sans-serif" '
                f'font-size="{FONT_SMALL}" fill="#7C3AED">{_esc(ln)}</text>\n'
                f"  </g>"
            )
            reveal_idx += 1
            cy += LINE_CN

    return reveal_idx, cy + TIER_GAP


def render_phrase_tiers_svg(title: str, table: dict[str, Any]) -> str:
    """Three tiers only — no 本题/改一句 (separate slide)."""
    parts = [_svg_open(), render_header(title)]
    y = Y0 + 16
    panel_bottom = Y0 + 16
    reveal_idx = 1

    parts.append(
        f'  <g id="reveal-{reveal_idx:02d}">\n'
        f'    <rect x="{PANEL_X}" y="{Y0}" width="{PANEL_W}" height="580" rx="16" '
        f'fill="#F5F3FF" stroke="#E2E8F0" stroke-width="2"/>\n'
        f"  </g>"
    )
    reveal_idx += 1

    for tier in table.get("tiers", []):
        reveal_idx, y = _tier_block(parts, reveal_idx, y, tier["level"], tier)
        panel_bottom = y

    # trim panel to content (min height 400)
    panel_h = max(400, min(580, panel_bottom - Y0 + 24))
    parts[2] = (
        f'  <g id="reveal-01">\n'
        f'    <rect x="{PANEL_X}" y="{Y0}" width="{PANEL_W}" height="{panel_h}" rx="16" '
        f'fill="#F5F3FF" stroke="#E2E8F0" stroke-width="2"/>\n'
        f"  </g>"
    )

    parts.append("</svg>\n")
    return "\n".join(parts)


def render_phrase_fix_svg(title: str, table: dict[str, Any]) -> str:
    """本题 + 改一句 on dedicated slide with room to breathe."""
    parts = [_svg_open(), render_header(title)]
    reveal_idx = 1
    y = Y0 + 40

    if table.get("topic_note"):
        parts.append(
            f'  <g id="reveal-{reveal_idx:02d}">\n'
            f'    <rect x="{PANEL_X}" y="{Y0 + 8}" width="{PANEL_W}" height="8" fill="transparent"/>\n'
            f'    <text x="{INSET_X}" y="{y}" font-family="Microsoft YaHei, Arial, sans-serif" '
            f'font-size="{FONT_CN}" font-weight="bold" fill="#475569">本题</text>\n'
            f"  </g>"
        )
        reveal_idx += 1
        y += 36
        for ln in _wrap(table["topic_note"], 88):
            parts.append(
                f'  <g id="reveal-{reveal_idx:02d}">\n'
                f'    <text x="{TEXT_X}" y="{y}" font-family="Microsoft YaHei, Arial, sans-serif" '
                f'font-size="{FONT_CN}" fill="#475569">{_esc(ln)}</text>\n'
                f"  </g>"
            )
            reveal_idx += 1
            y += LINE_CN + 4

    y += 20
    fix_lines_bad = _wrap(table.get("fix_bad", ""), 90) if table.get("fix_bad") else []
    fix_lines_good = _wrap(table.get("fix_good", ""), 90) if table.get("fix_good") else []
    box_h = 56 + len(fix_lines_bad) * 32 + len(fix_lines_good) * 32 + 24

    parts.append(
        f'  <g id="reveal-{reveal_idx:02d}">\n'
        f'    <rect x="{INSET_X}" y="{y - 12}" width="1120" height="{box_h}" rx="12" '
        f'fill="#FFFFFF" stroke="#FCA5A5" stroke-width="2"/>\n'
        f'    <text x="{TEXT_X}" y="{y + 20}" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_CN}" font-weight="bold" fill="#64748B">改一句</text>\n'
        f"  </g>"
    )
    reveal_idx += 1
    fy = y + 48
    for ln in fix_lines_bad:
        parts.append(
            f'  <g id="reveal-{reveal_idx:02d}">\n'
            f'    <text x="{TEXT_X}" y="{fy}" font-family="Times New Roman, Times, serif" '
            f'font-size="{FONT_CN}" fill="#DC2626">{_esc(ln)}</text>\n'
            f"  </g>"
        )
        reveal_idx += 1
        fy += 32
    for ln in fix_lines_good:
        parts.append(
            f'  <g id="reveal-{reveal_idx:02d}">\n'
            f'    <text x="{TEXT_X}" y="{fy}" font-family="Times New Roman, Times, serif" '
            f'font-size="{FONT_CN}" fill="#059669">{_esc(ln)}</text>\n'
            f"  </g>"
        )
        reveal_idx += 1
        fy += 32

    parts.append("</svg>\n")
    return "\n".join(parts)


def render_phrase_tier_svg(title: str, table: dict[str, Any]) -> str:
    """Backward-compatible alias: tiers only."""
    return render_phrase_tiers_svg(title, table)


def split_rows(rows: list[dict[str, str]], max_rows: int = 6) -> list[list[dict[str, str]]]:
    if not rows:
        return [[]]
    return [rows[i : i + max_rows] for i in range(0, len(rows), max_rows)]


def render_vocab_table_svg(
    title: str,
    tier: str,
    rows: list[dict[str, str]],
    *,
    show_chinese: bool,
) -> str:
    parts = [_svg_open(), render_header(title)]
    head_fill = _VOCAB_HEAD.get(tier, "#E2E8F0")
    parts.append(
        f'  <g id="reveal-01">\n'
        f'    <rect x="{PANEL_X}" y="{Y0}" width="{PANEL_W}" height="560" rx="12" '
        f'fill="#FAFAFA" stroke="#E2E8F0" stroke-width="2"/>\n'
        f'    <rect x="{PANEL_X}" y="{Y0}" width="{PANEL_W}" height="44" rx="12" fill="{head_fill}"/>\n'
        f'    <text x="72" y="{Y0 + 36}" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_BODY}" font-weight="bold" fill="#1E293B">{_esc(tier)}</text>\n'
        f"  </g>"
    )

    if show_chinese:
        cols = [("英文词块", 72), ("中文释义", 400), ("例句", 600)]
    else:
        cols = [("英文词块", 72), ("例句", 480)]

    reveal_idx = 2
    hy = Y0 + 68
    for label, cx in cols:
        parts.append(
            f'  <g id="reveal-{reveal_idx:02d}">\n'
            f'    <text x="{cx}" y="{hy}" font-family="Microsoft YaHei, Arial, sans-serif" '
            f'font-size="{FONT_SMALL}" font-weight="bold" fill="#64748B">{_esc(label)}</text>\n'
            f"  </g>"
        )
        reveal_idx += 1

    row_y = hy + 32
    for row in rows:
        parts.append(
            f'  <g id="reveal-{reveal_idx:02d}">\n'
            f'    <line x1="72" y1="{row_y - 6}" x2="1208" y2="{row_y - 6}" stroke="#E2E8F0" stroke-width="1"/>\n'
            f"  </g>"
        )
        reveal_idx += 1
        eng_lines = _wrap(row["english"], 28 if show_chinese else 42)
        ex_lines = _wrap(row.get("example", ""), 42 if show_chinese else 58)
        row_h = max(len(eng_lines), len(ex_lines), 1) * 28 + 16
        for j, ln in enumerate(eng_lines):
            parts.append(
                f'  <g id="reveal-{reveal_idx:02d}">\n'
                f'    <text x="72" y="{row_y + j * 28}" font-family="Times New Roman, Times, serif" '
                f'font-size="{FONT_BODY}" fill="#1E293B">{_esc(ln)}</text>\n'
                f"  </g>"
            )
            reveal_idx += 1
        if show_chinese:
            for j, ln in enumerate(_wrap(row.get("chinese", ""), 14)):
                parts.append(
                    f'  <g id="reveal-{reveal_idx:02d}">\n'
                    f'    <text x="400" y="{row_y + j * 26}" font-family="Microsoft YaHei, Arial, sans-serif" '
                    f'font-size="{FONT_CN}" fill="#475569">{_esc(ln)}</text>\n'
                    f"  </g>"
                )
                reveal_idx += 1
        ex_x = 480 if not show_chinese else 600
        for j, ln in enumerate(ex_lines):
            parts.append(
                f'  <g id="reveal-{reveal_idx:02d}">\n'
                f'    <text x="{ex_x}" y="{row_y + j * 26}" font-family="Times New Roman, Times, serif" '
                f'font-size="{FONT_CN}" fill="#334155">{_esc(ln)}</text>\n'
                f"  </g>"
            )
            reveal_idx += 1
        row_y += row_h

    parts.append("</svg>\n")
    return "\n".join(parts)
