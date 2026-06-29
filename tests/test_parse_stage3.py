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


def test_phrase_tables_from_word_tsv():
    text = """
表格 1：表达个人排序立场
层级\t英文句型\t中文说明\t高分说明
基础级\tWhen it comes to..., my priority is clear.\t用途：开头亮明排序\t—
进阶级\tIf I had to rank..., I would place A at the top.\t用途：虚拟语气\t—
高级级\tWhile many might argue otherwise, I am convinced...\t用途：让步亮观点\t可用于开头
本题：适合用直接但非生硬的句型亮明排序。
改一句
In my opinion, studying is the most important. ❌
→ If I had to prioritize the three, I would argue...\t✅
"""
    data = parse_stage3_markdown(text)
    assert len(data["phrase_tables"]) == 1
    tiers = data["phrase_tables"][0]["tiers"]
    assert len(tiers) == 3
    assert tiers[0]["level"] == "基础句"
    assert "When it comes to" in tiers[0]["english"]


def test_vocab_rows_from_word_tsv():
    text = """
二、话题词汇锦囊
语义场 1：大学生活要素
必备级
英文词块\t中文释义\t具体使用例句
lay a solid foundation\t打下坚实基础\tI believe that academic study will lay a solid foundation.
time management\t时间管理\tEffective time management is the real challenge.
"""
    data = parse_stage3_markdown(text)
    field = data["vocab_fields"][0]
    basic = next(t for t in field["tiers"] if t["level"] == "必备级")
    assert len(basic["rows"]) == 2
    assert basic["rows"][0]["english"] == "lay a solid foundation"
