"""Tests for Stage 3 SVG builders."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.build_ppt_stage3_svg import build_stage3_slide_specs, write_stage3_svgs
from scripts.parse_stage3 import parse_stage3_file
from scripts.stage3_svg_layout import render_phrase_tiers_svg, render_vocab_table_svg

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"


def test_basic_vocab_two_columns_only():
    svg = render_vocab_table_svg(
        title="话题词块 · 设计元素 · 必备",
        tier="必备级",
        rows=[
            {
                "english": "cracked heart",
                "chinese": "带裂痕的心",
                "example": "The cracked heart in Poster 1 symbolizes emotional pain.",
            }
        ],
        show_chinese=False,
    )
    assert "cracked heart" in svg
    assert "symbolizes" in svg
    assert "带裂痕" not in svg
    assert "中文释义" not in svg


def test_basic_phrase_english_only():
    svg = render_phrase_tiers_svg(
        title="功能句型 · 观点表达",
        table={
            "name": "观点表达",
            "tiers": [
                {
                    "level": "基础句",
                    "english": "I prefer Poster 1.",
                    "chinese": "用途：直接表明选择",
                    "high_score": None,
                },
                {
                    "level": "进阶句",
                    "english": "I'm leaning towards Poster 1.",
                    "chinese": "用途：委婉",
                    "high_score": None,
                },
                {
                    "level": "高级句",
                    "english": "Among the two...",
                    "chinese": "用途：对比",
                    "high_score": "strikes me as",
                },
            ],
            "topic_note": "明确表达选择",
            "fix_bad": "I think Poster 1 is good. ❌",
            "fix_good": "→ Personally, I'm leaning towards Poster 1. ✅",
        },
    )
    assert "I prefer Poster 1." in svg
    assert "用途：直接表明选择" not in svg
    assert "用途：委婉" in svg


def test_phrase_label_not_overlapping_english():
    svg = render_phrase_tiers_svg(
        title="功能句型 · 观点表达",
        table={
            "name": "观点表达",
            "tiers": [
                {"level": "基础句", "english": "I prefer Poster 1.", "chinese": "用途：x", "high_score": None},
                {"level": "进阶句", "english": "I'm leaning towards Poster 1.", "chinese": "用途：y", "high_score": None},
            ],
            "topic_note": "",
            "fix_bad": "",
            "fix_good": "",
        },
    )
    # label 基础句 then english — english y should be at least 30px below label
    m_label = re.search(r"基础句.*?y=\"(\d+)\"", svg, re.DOTALL)
    m_eng = re.search(r"I prefer Poster 1\..*?y=\"(\d+)\"", svg, re.DOTALL)
    assert m_label and m_eng
    assert int(m_eng.group(1)) - int(m_label.group(1)) >= 30


def test_slide_spec_count():
    data = parse_stage3_file(FIXTURE)
    specs = build_stage3_slide_specs(data)
    assert len(specs) >= 15  # 6 phrase + 9 vocab
    assert any("必备级" in s["title"] for s in specs)


def test_no_text_below_ymax(tmp_path):
    data = parse_stage3_file(FIXTURE)
    json_path = tmp_path / "stage3.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    written = write_stage3_svgs(tmp_path, json_path)
    assert len(written) >= 12
    for p in written:
        svg = p.read_text(encoding="utf-8")
        ys = [int(m.group(1)) for m in re.finditer(r'y="(\d+)"', svg)]
        assert max(ys) <= 720
