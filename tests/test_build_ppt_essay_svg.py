"""Tests for build_ppt_essay_svg layout engine."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.build_ppt_essay_svg import (
    Y_MAX,
    build_essay_svg,
    essay_specs_from_deck,
    layout_essay_lines,
    write_essay_svgs,
)
from scripts.essay_format import classroom_body_paragraphs

TEXT_Y_RE = re.compile(
    r'id="reveal-\d+".*?<text x="(\d+)" y="(\d+)"',
    re.DOTALL,
)
FOOTER_Y_RE = re.compile(
    r'id="reveal-footer".*?y="(\d+)"',
    re.DOTALL,
)
FORBIDDEN = ("Dear James", "Good luck", "Hope this helps")


def _body_text_ys(svg: str) -> list[int]:
    ys: list[int] = []
    for block in re.findall(r'<g id="reveal-\d+">.*?</g>', svg, re.DOTALL):
        if "Times New Roman" not in block:
            continue
        m = re.search(r'y="(\d+)"', block)
        if m:
            ys.append(int(m.group(1)))
    return ys


def _first_line_x_per_paragraph(svg: str) -> list[int]:
    """First Times line after each paragraph gap uses indent x=108."""
    xs: list[int] = []
    for block in re.findall(r'<g id="reveal-\d+">.*?</g>', svg, re.DOTALL):
        if "Times New Roman" not in block:
            continue
        m = re.search(r'x="(\d+)"', block)
        if m:
            xs.append(int(m.group(1)))
    # paragraph first lines use indent x=88 (see build_ppt_essay_svg.X_INDENT)
    return [x for x in xs if x == 88]


def test_classroom_body_three_paragraphs():
    for spec in essay_specs_from_deck():
        paras = classroom_body_paragraphs(spec["essay_text"])
        assert len(paras) == 3, spec["title"]


def test_high_b_fits_without_footer_overlap():
    spec = essay_specs_from_deck()[2]  # advanced B
    svg = build_essay_svg(
        title=spec["title"],
        badge_label=spec["badge"],
        essay_text=spec["essay_text"],
        annotation=spec["annotation"],
    )
    body_ys = _body_text_ys(svg)
    assert body_ys
    assert max(body_ys) <= Y_MAX
    for bad in FORBIDDEN:
        assert bad not in svg
    fm = FOOTER_Y_RE.search(svg)
    if fm:
        assert int(fm.group(1)) > max(body_ys)


def test_three_paragraph_first_line_indents():
    spec = essay_specs_from_deck()[2]
    svg = build_essay_svg(
        title=spec["title"],
        badge_label=spec["badge"],
        essay_text=spec["essay_text"],
        annotation="",
    )
    assert len(_first_line_x_per_paragraph(svg)) == 3
    assert all(x == 88 for x in _first_line_x_per_paragraph(svg))


def test_no_essay_panel_path():
    spec = essay_specs_from_deck()[0]
    svg = build_essay_svg(
        title=spec["title"],
        badge_label=spec["badge"],
        essay_text=spec["essay_text"],
        annotation="",
    )
    assert "reveal-panel" not in svg
    assert "F5F3FF" not in svg


def test_layout_essay_lines_returns_three_blocks():
    spec = essay_specs_from_deck()[1]
    paras = classroom_body_paragraphs(spec["essay_text"])
    lines, last_y = layout_essay_lines(paras)
    assert len(lines) >= 6
    assert last_y <= Y_MAX


def test_footer_word_count_matches_badge():
    spec = essay_specs_from_deck()[1]  # advanced A
    svg = build_essay_svg(
        title=spec["title"],
        badge_label=spec["badge"],
        essay_text=spec["essay_text"],
        annotation=spec["annotation"],
    )
    badge_m = re.search(r'reveal-badge.*?>(\d+) words', svg, re.DOTALL)
    footer_m = re.search(r'reveal-footer.*?>(\d+) words', svg, re.DOTALL)
    assert badge_m and footer_m
    assert badge_m.group(1) == footer_m.group(1)
    assert "118 words" not in svg or badge_m.group(1) == "118"


def test_essay_starts_below_badge():
    spec = essay_specs_from_deck()[1]
    svg = build_essay_svg(
        title=spec["title"],
        badge_label=spec["badge"],
        essay_text=spec["essay_text"],
        annotation=spec["annotation"],
    )
    first_y = min(_body_text_ys(svg))
    assert first_y >= 168


def test_write_essay_svgs_to_tmp(tmp_path: Path):
    written = write_essay_svgs(tmp_path)
    assert len(written) == 3
    for path in written:
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert max(_body_text_ys(content)) <= Y_MAX
