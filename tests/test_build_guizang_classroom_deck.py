"""Smoke test for guizang classroom deck builder."""

import json
from pathlib import Path

from scripts.build_guizang_classroom_deck import (
    SLIDES_MARKER,
    render_guizang_html,
    render_guizang_slide,
)
from scripts.build_classroom_html_deck import build_slide_specs


def test_guizang_render_injects_slides(tmp_path):
    template = f"<!DOCTYPE html><html><body><div id='deck'>{SLIDES_MARKER}</div></body></html>"
    specs = [
        {
            "tag": "导入",
            "title": "高考英语应用文 · 测试",
            "variant": "hero",
            "subtitle": "Ranking Essentials",
            "bullets": ["Line one"],
        },
        {"tag": "Stage 1", "title": "审题 · 三元审题", "bullets": ["A", "B"]},
    ]
    html = render_guizang_html(specs, deck_title="测试", template_text=template)
    assert SLIDES_MARKER not in html
    assert html.count('<section class="slide') == 2
    assert "Ranking Essentials" in html


def test_guizang_slide_has_pipeline_for_bullets():
    slide = {"title": "思维 · 路径", "bullets": ["第一点", "第二点"]}
    out = render_guizang_slide(slide, 1, 3, "light")
    assert 'data-animate="pipeline"' in out
    assert "第一点" in out


def test_build_specs_no_mandatory_point():
    export = Path(__file__).parent / "fixtures" / "export_college_min.json"
    if not export.is_file():
        return
    data = json.loads(export.read_text(encoding="utf-8"))
    specs = build_slide_specs(data, preset="70min")
    blob = json.dumps(specs, ensure_ascii=False)
    assert "mandatory_point" not in blob
