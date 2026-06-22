"""Tests for deck_plan."""

from pathlib import Path

from scripts.deck_plan import (
    deck_plan_from_stage3,
    load_deck_plan,
    refine_deck_plan,
    stage3_specs_from_plan,
    validate_slide_fit,
)
from scripts.parse_stage3 import parse_stage3_file

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"


def test_deck_plan_has_phrase_and_vocab_slides():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    layouts = [s["layout"] for s in plan["slides"]]
    assert "phrase_table_body" in layouts
    assert "phrase_table_footer" in layouts
    assert "vocab_table" in layouts
    assert sum(1 for s in plan["slides"] if s["layout"] == "vocab_table") >= 9


def test_vocab_basic_columns_two_only():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    basic = next(s for s in plan["slides"] if "必备" in s["title"])
    assert basic["columns"] == ["english", "example"]


def test_stage3_specs_from_plan_phrase_table():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    specs = stage3_specs_from_plan(data, plan)
    phrase = next(s for s in specs if s["type"] == "phrase_table")
    assert phrase["table"]["name"] == "观点表达"
    assert len(phrase["table"]["tiers"]) == 3


def test_load_deck_plan_fallback(tmp_path):
    data = parse_stage3_file(FIXTURE)
    plan = load_deck_plan(None, data)
    assert plan["version"] == 2
    assert len(plan["slides"]) >= 15


def test_validate_slide_fit_phrase_body():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    body = next(s for s in plan["slides"] if s["layout"] == "phrase_table_body")
    assert validate_slide_fit(body, data)


def test_vocab_chunks_by_measurement_not_only_six():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    vocab_slides = [s for s in plan["slides"] if s["layout"] == "vocab_table"]
    assert len(vocab_slides) >= 9
    for slide in vocab_slides:
        assert len(slide.get("rows", [])) <= 6


def test_refine_deck_plan_idempotent():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    again = refine_deck_plan(data, plan)
    assert len(again["slides"]) == len(plan["slides"])
