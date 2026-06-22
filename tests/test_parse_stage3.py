"""Tests for parse_stage3."""

from pathlib import Path

from scripts.parse_stage3 import parse_stage3_markdown, write_stage3_json

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"


def test_phrase_tables_count():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["phrase_tables"]) == 3
    assert data["phrase_tables"][0]["name"] == "观点表达"


def test_vocab_fields_count():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["vocab_fields"]) == 3


def test_vocab_basic_tier_rows():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    field = next(f for f in data["vocab_fields"] if "设计" in f["name"])
    basic = next(t for t in field["tiers"] if t["level"] == "必备级")
    assert len(basic["rows"]) >= 3
    assert basic["rows"][0]["english"] == "cracked heart"
    assert "symbolizes" in basic["rows"][0]["example"]


def test_phrase_fix_sentence_parsed():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    t0 = data["phrase_tables"][0]
    assert "❌" in t0["fix_bad"]
    assert t0["fix_good"].startswith("→")


def test_write_json_roundtrip(tmp_path):
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    out = tmp_path / "stage3.json"
    write_stage3_json(data, out)
    assert out.exists()
    assert "phrase_tables" in out.read_text(encoding="utf-8")
