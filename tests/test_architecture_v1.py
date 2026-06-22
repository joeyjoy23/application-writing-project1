"""Tests for classroom architecture V1 deck builder."""

import json
from pathlib import Path

from scripts.architecture_v1 import (
    ARCHITECTURE_V1_SLOTS,
    build_architecture_deck,
    inject_module_dividers,
    merge_stage3_into_architecture_deck,
    slots_for_preset,
)
from scripts.parse_stage3 import parse_stage3_file

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"


def test_80min_has_more_slots_than_40min():
    assert len(slots_for_preset("80min")) > len(slots_for_preset("40min"))


def test_build_architecture_deck_has_title_and_stage3_placeholder():
    data = {
        "question_type_label": "观点理由类",
        "question": "假如你是李华…\n请选择并说明理由。",
        "stage1": "- 我是谁：李华\n- 写给谁：James",
        "stage2": "PEEL\n基础版\nDear James,",
        "stage4": "易错：理由空泛",
    }
    deck = build_architecture_deck(data, preset="40min")
    types = [s["type"] for s in deck]
    assert "title" in types
    assert "_stage3_placeholder" in types
    assert types.index("title") < types.index("_stage3_placeholder")


def test_inject_module_dividers_inserts_before_modules():
    data = {
        "question": "题目",
        "stage1": "审题",
        "stage2": "PEEL",
        "stage4": "迁移",
    }
    base = build_architecture_deck(data, preset="40min")
    out = inject_module_dividers(base, enabled=True)
    assert out[0]["type"] == "divider"
    assert out[0]["name"] == "导入"


def test_merge_stage3_replaces_placeholder():
    data = parse_stage3_file(FIXTURE)
    stage3_specs = [
        {"type": "phrase_table", "part": "body", "title": "功能句型 · 观点", "table": data["phrase_tables"][0]},
    ]
    base = build_architecture_deck({"question": "q", "stage1": "s1", "stage2": "s2", "stage4": "s4"}, preset="40min")
    merged = merge_stage3_into_architecture_deck(base, stage3_specs)
    assert not any(s.get("type") == "_stage3_placeholder" for s in merged)
    assert any(s.get("type") == "phrase_table" for s in merged)


def test_slot_ids_unique():
    ids = [s.slot_id for s in ARCHITECTURE_V1_SLOTS]
    assert len(ids) == len(set(ids))
