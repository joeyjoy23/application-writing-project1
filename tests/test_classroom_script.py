"""Tests for Classroom Script MVP compiler."""

from pathlib import Path

import pytest

from scripts.classroom_script import (
    ClassroomScriptError,
    assert_source_exclusivity,
    check_and_split_layout,
    compile_classroom_script,
    load_script_template,
)
from scripts.deck_plan import deck_plan_from_stage3, refine_deck_plan, stage3_specs_from_plan
from scripts.parse_stage3 import parse_stage3_file

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"


def _stage3_bundle():
    data = parse_stage3_file(FIXTURE)
    plan = refine_deck_plan(data, deck_plan_from_stage3(data))
    return data, stage3_specs_from_plan(data, plan)


def test_source_exclusivity_raises_on_duplicate():
    seq = [
        {"id": "a", "archetype": "triplet_review", "bind": {"source": "stage1.triplet"}},
        {"id": "b", "archetype": "task_checklist", "bind": {"source": "stage1.triplet"}},
    ]
    with pytest.raises(ClassroomScriptError, match="exclusivity conflict"):
        assert_source_exclusivity(seq)


def test_cover_meta_has_empty_body_no_stem():
    export_data = {
        "question_type_label": "观点理由类",
        "question": "假如你是李华，James 参加心理健康周海报大赛。\n[图：Poster 1 …]",
        "stage1": "- 底层思维路径：先确定选择，再分析设计元素",
        "stage2": "PEEL\n1. 基础版\nDear James,",
        "stage4": "",
    }
    script = load_script_template("dual_poster_opinion")
    stage3_data, stage3_specs = _stage3_bundle()
    slides = compile_classroom_script(
        script, export_data, stage3_data, stage3_specs=stage3_specs
    )
    assert slides[0]["type"] == "title"
    assert slides[0]["body"] == []
    assert slides[0].get("subtitle") == ""
    assert "James" not in slides[0].get("subtitle", "")
    stem_slide = next(s for s in slides if s.get("title") == "导入 · 真题展示")
    assert any("James" in b for b in stem_slide["bullets"])
    assert not any(s.get("type") == "title" and s.get("poster_lines") for s in slides)


def test_visual_poster_expands_one_per_slide():
    export_data = {
        "question_type_label": "观点理由类",
        "question": (
            "题干行\n"
            "[图：两张海报：Poster 1是双手托心；Poster 2是浇水壶浇灌植物]"
        ),
        "stage1": "- 我是谁：李华",
        "stage2": "PEEL",
        "stage4": "",
    }
    script = load_script_template("dual_poster_opinion")
    stage3_data, stage3_specs = _stage3_bundle()
    slides = compile_classroom_script(
        script, export_data, stage3_data, stage3_specs=stage3_specs
    )
    poster_slides = [s for s in slides if s.get("title") == "海报示意"]
    assert len(poster_slides) >= 2
    for ps in poster_slides:
        bullet = (ps.get("bullets") or [""])[0]
        assert "两张海报：" != bullet.strip()
        assert len(bullet.strip()) > 6


def test_thinking_core_replaces_triplet_task_formula():
    export_data = {
        "question_type_label": "观点理由类",
        "question": "假如你是李华…",
        "stage1": "- 我是谁：李华\n- 写给谁：James\n- 为了什么：说明选择理由",
        "stage2": "PEEL\nDear James,",
        "stage4": "",
    }
    script = load_script_template("dual_poster_opinion")
    stage3_data, stage3_specs = _stage3_bundle()
    slides = compile_classroom_script(
        script, export_data, stage3_data, stage3_specs=stage3_specs
    )
    titles = [s.get("title") for s in slides]
    assert any((t or "").startswith("思维 · 审题与路径") for t in titles)
    assert "审题 · 三元审题" not in titles
    assert "审题 · 任务拆解" not in titles
    assert "思维 · 高分公式" not in titles


def test_compile_includes_phrase_and_vocab_from_stage3_specs():
    export_data = {
        "question_type_label": "观点理由类",
        "question": "假如你是李华…",
        "stage1": "- 我是谁：李华",
        "stage2": "PEEL\nDear James,",
        "stage4": "",
    }
    script = load_script_template("notice_campaign")
    stage3_data, stage3_specs = _stage3_bundle()
    slides = compile_classroom_script(
        script, export_data, stage3_data, stage3_specs=stage3_specs
    )
    types = [s["type"] for s in slides]
    assert "phrase_table" in types
    assert slides[0]["type"] == "title"
    assert slides[0]["body"] == []


def test_phrase_table_interleaves_body_and_footer():
    from scripts.classroom_script import _phrase_specs_interleaved

    specs = [
        {"type": "phrase_table", "part": "body", "title": "功能句型 · 观点", "table": {"name": "观点表达"}},
        {"type": "phrase_table", "part": "footer", "title": "功能句型 · 观点 · 用法与改错", "table": {"name": "观点表达"}},
        {"type": "phrase_table", "part": "body", "title": "功能句型 · 论据", "table": {"name": "论据支撑"}},
        {"type": "phrase_table", "part": "footer", "title": "功能句型 · 论据 · 用法与改错", "table": {"name": "论据支撑"}},
    ]
    out = _phrase_specs_interleaved(specs)
    assert [s["part"] for s in out] == ["body", "footer", "body", "footer"]
    assert out[1]["table"]["name"] == "观点表达"
    for tid in ("dual_poster_opinion", "letter_suggestion", "notice_campaign"):
        script = load_script_template(tid)
        assert script["lesson"]["template_id"] == tid
        assert_source_exclusivity(script["sequence"])


def test_layout_injects_min_font_size():
    spec = {"type": "content", "title": "思维 · 高分路径", "bullets": ["步骤一", "↓", "步骤二"]}
    out = check_and_split_layout(spec, archetype="thinking_path")
    assert all(s.get("font_size", 0) >= 26 for s in out)
    assert all(s.get("min_font_size") == 26 for s in out)


def test_essay_layout_prefers_single_page_when_fits():
    short = "Dear James,\n\nPersonally, I'd choose Poster 1.\n\nGood luck!"
    spec = {"type": "essay", "title": "高分版 A", "essay_text": short, "annotation": ""}
    out = check_and_split_layout(spec, archetype="essay_display")
    assert len(out) == 1
    assert out[0].get("font_size", 0) >= 26


def test_essay_layout_splits_when_over_char_limit():
    long_body = "Dear James,\n\n" + ("Personally, I'd choose Poster 1 because it shows detail. " * 80)
    spec = {"type": "essay", "title": "高分版 A", "essay_text": long_body, "annotation": ""}
    out = check_and_split_layout(spec, archetype="essay_display")
    assert len(out) >= 2
    assert out[0].get("_essay_part") == 1 or "Part 1" in out[0].get("title", "")
