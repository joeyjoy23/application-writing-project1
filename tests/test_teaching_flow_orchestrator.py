"""Tests for teaching_flow_orchestrator."""

from scripts.ppt_layout_fit import pack_slides
from scripts.teaching_flow_orchestrator import orchestrate_teaching_flow


def test_orchestrator_keeps_phrase_body_footer_separate():
    slides = [
        {
            "type": "phrase_table",
            "part": "body",
            "title": "功能句型 · 观点表达",
            "table": {"tiers": [{"level": "基础句", "english": "I think", "chinese": ""}]},
        },
        {
            "type": "phrase_table",
            "part": "footer",
            "title": "功能句型 · 观点表达 · 本题",
            "table": {"topic_note": "note", "fix_bad": "bad", "fix_good": "good"},
        },
    ]
    out = orchestrate_teaching_flow(slides)
    assert len(out) == 2
    assert out[0]["part"] == "body"
    assert out[1]["part"] == "footer"


def test_orchestrator_keeps_essay_annotation_separate():
    slides = [
        {"type": "essay", "title": "基础版范文", "essay_text": "Hi", "annotation": ""},
        {"type": "content", "title": "基础版范文 · 批注", "bullets": ["批注 1"]},
    ]
    out = orchestrate_teaching_flow(slides)
    assert len(out) == 2
    assert out[1]["type"] == "content"


def test_pack_paginates_vocab_by_rows_after_orchestrator():
    rows = [{"english": f"w{i}", "chinese": f"词{i}"} for i in range(10)]
    slides = [
        {
            "type": "vocab_table",
            "title": "话题词块 · 观点表达 · 必备级",
            "tier": "必备级",
            "columns": ["english", "chinese"],
            "rows": rows,
        }
    ]
    out = pack_slides(slides)
    assert len(out) >= 2
    assert sum(len(s["rows"]) for s in out) == 10


def test_orchestrator_preserves_small_vocab_page():
    slides = [
        {
            "type": "vocab_table",
            "title": "话题词块 · 观点表达 · 必备级",
            "tier": "必备级",
            "columns": ["english", "chinese"],
            "rows": [{"english": "stress", "chinese": "压力"}],
        }
    ]
    out = orchestrate_teaching_flow(slides)
    assert len(out) == 1
    assert len(out[0]["rows"]) == 1
