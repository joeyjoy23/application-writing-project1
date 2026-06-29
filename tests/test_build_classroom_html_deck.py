"""Tests for Plan B classroom HTML deck builder."""

from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.build_classroom_html_deck import (
    build_slide_specs,
    render_html,
    render_speaker_notes_html,
    stage1_supplement_specs,
    v2_spec_to_html_slides,
)

FIXTURE_EXPORT = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"
REAL_EXPORT = Path(r"D:\Downloads\ppt-work\export-data.json")
REAL_STAGE3 = Path(r"D:\Downloads\ppt-work\stage3.json")


def test_build_slide_specs_minimal_export():
    export = {
        "meta": "测试",
        "question_type_label": "观点理由类",
        "question": "假如你是李华…",
        "stage1": "题目类型：观点理由类\n\n1. 语气 — 朋友还是报告？\n\n💡 一句大实话\n\n陷阱是空泛理由。\n\n2. 交际任务分析\n2.1 三元审题\n\n- 我是谁：李华\n\n3. 审题结论\n\n- 体裁：邮件\n",
        "stage2": "",
        "stage3": "",
        "stage4": "",
    }
    specs = build_slide_specs(export, preset="70min")
    assert specs[0]["title"]
    assert any(s.get("tag") == "Stage 1" for s in specs)
    html_out = render_html(specs, "测试课件")
    assert "<section class=" in html_out
    assert "26px" in html_out or "--body-min: 26px" in html_out


def test_render_html_click_reveal_controls():
    specs = [{"tag": "测试", "title": "标题", "bullets": ["一点", "二点"]}]
    html_out = render_html(specs, "字体测试")
    assert "advanceOrNext" in html_out
    assert "retreatOrPrev" in html_out
    assert 'class="slide"' in html_out
    assert "essay-para" in html_out


def test_speaker_notes_html():
    specs = [
        {
            "title": "审题",
            "tag": "Stage 1",
            "ast_role_label": "张力",
            "audience_in": "进入",
            "audience_out": "带走",
            "one_thing": "完成审题",
        }
    ]
    notes = render_speaker_notes_html(specs, "测试")
    assert "完成审题" in notes
    assert "观众进入" in notes


def test_v2_essay_uses_prepare_classroom_display():
    raw = (
        "Dear James,\n\nGlad to hear about your poster designs!\n\n"
        "Word count: 42\n\n中文批注：\n\n- ①选择明确"
    )
    slides = v2_spec_to_html_slides(
        {"type": "essay", "title": "基础版范文", "essay_text": raw}
    )
    assert len(slides) == 1
    assert "Glad to hear" in slides[0]["essay"]
    assert "Word count: 42" in slides[0]["essay"]
    assert "Dear James" not in slides[0]["essay"]  # salutation stripped for classroom


def test_stage1_supplements_include_self_checks():
    export = {
        "stage1": (
            "0. 审题\n\n1. 语气 — 朋友还是报告？\n\n"
            "2. 结构 — 有理由吗？\n\n"
            "3. 逻辑 — 双向说明？\n\n"
            "4. 立意 — 深层意义？\n\n"
            "5. 语言 — 关键表达？\n\n"
            "💡 一句大实话\n\n陷阱是空泛。\n\n"
            "3. 审题结论\n\n- 体裁：邮件\n\n"
            "6. 要点与结构规划\n开头段\n\n- 功能：问候\n"
        )
    }
    supp = stage1_supplement_specs(export)
    titles = [s["title"] for s in supp]
    assert any("自检" in t for t in titles)
    assert any("结论" in t for t in titles)


def test_render_html_slide_count_matches_export(tmp_path):
    if not REAL_EXPORT.is_file() or not REAL_STAGE3.is_file():
        return
    plan = Path(r"D:\Downloads\ppt-work\humanize-run\slide_plan.json")
    data = json.loads(REAL_EXPORT.read_text(encoding="utf-8"))
    specs = build_slide_specs(
        data,
        stage3_path=REAL_STAGE3,
        slide_plan_path=plan if plan.is_file() else None,
        preset="70min",
    )
    assert len(specs) >= 35, f"expected 70min full deck, got {len(specs)}"
    assert any(s.get("essay") for s in specs), "missing essay slides"
    assert any(s.get("phrase_body") for s in specs), "missing phrase tables"
    assert any(s.get("one_thing") for s in specs), "missing Humanize AST"
    out = tmp_path / "deck.html"
    html_out = render_html(specs, "心理健康")
    out.write_text(html_out, encoding="utf-8")
    assert html_out.count("<section") == len(specs)
    assert "advanceOrNext" in html_out


def test_no_sub_26px_body_in_css():
    specs = [{"tag": "测试", "title": "T", "bullets": ["a"]}]
    css = render_html(specs, "T")
    assert "0.88rem" not in css
    assert "0.72rem" not in css
