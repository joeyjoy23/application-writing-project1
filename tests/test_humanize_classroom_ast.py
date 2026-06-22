"""Tests for Humanize AST mapping on 应用文 classroom decks."""

from __future__ import annotations

from pathlib import Path

from scripts.humanize_classroom_ast import (
    enrich_specs_with_ast,
    humanize_role_for_tag,
    load_slide_plan,
    parse_speaker_intent_md,
)

PLAN = Path(r"D:\Downloads\ppt-work\humanize-run\slide_plan.json")
INTENT = Path(r"D:\Downloads\ppt-work\humanize-run\speaker_intent.md")


def test_humanize_role_for_tag():
    assert humanize_role_for_tag("导入", variant="hero") == "hook"
    assert humanize_role_for_tag("Stage 1") == "tension"
    assert humanize_role_for_tag("Stage 3") == "proof"


def test_load_slide_plan_real():
    if not PLAN.is_file():
        return
    plan = load_slide_plan(PLAN)
    assert len(plan) >= 6
    assert plan[0].get("role") == "hook"


def test_enrich_specs_attaches_ast():
    if not PLAN.is_file():
        return
    specs = [
        {"tag": "导入", "variant": "hero", "title": "导入 · 真题展示"},
        {"tag": "Stage 1", "title": "审题 · 三元审题"},
        {"tag": "Stage 3", "title": "功能句型"},
    ]
    enrich_specs_with_ast(specs, slide_plan_path=PLAN, speaker_intent_path=INTENT)
    assert specs[0].get("one_thing")
    assert specs[0].get("audience_in")
    assert specs[1].get("ast_role") == "tension"
    assert specs[2].get("ast_role") == "proof"


def test_parse_speaker_intent_md():
    if not INTENT.is_file():
        return
    intents = parse_speaker_intent_md(INTENT)
    assert "S01" in intents
    assert "注意力" in intents["S01"] or "疲劳" in intents["S01"]
