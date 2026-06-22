"""Tests for application-letter essay paragraph splitting."""

import re

from scripts.essay_format import (
    classroom_body_paragraphs,
    essay_layout_for_length,
    prepare_classroom_essay_display,
    split_essay_three_paragraphs,
    wrap_paragraph_lines,
)


def test_split_basic_three_paragraphs():
    text = (
        "Dear James,\n\n"
        "Glad to hear about your poster designs.\n\n"
        "I'd go with Poster 1. The cracked heart stands out.\n\n"
        "Hope this helps! Good luck!"
    )
    sal, paras = split_essay_three_paragraphs(text)
    assert sal == "Dear James,"
    assert len(paras) == 3
    assert paras[0].startswith("Glad")
    assert "Poster 1" in paras[1]
    assert "Good luck" in paras[2]


def test_split_single_block_heuristic():
    text = (
        "Dear James,\n\n"
        "Glad to hear about your designs. I'd go with Poster 1. It is great. "
        "Hope this helps! Good luck!"
    )
    sal, paras = split_essay_three_paragraphs(text)
    assert sal == "Dear James,"
    assert len(paras) == 3
    assert "Poster 1" in paras[1]
    assert "Good luck" in paras[2]


def test_classroom_body_strips_salutation_and_closing():
    text = (
        "Dear James,\n\n"
        "Glad to hear about your designs.\n\n"
        "I'd go with Poster 1. It is great.\n\n"
        "The details really matter.\n\n"
        "Hope this helps! Good luck!"
    )
    body = classroom_body_paragraphs(text)
    assert len(body) == 3
    assert "Dear" not in " ".join(body)
    assert all("Good luck" not in p for p in body)


def test_word_count_excludes_salutation_and_closing():
    text = (
        "Dear James,\n\n"
        "Glad to hear about your designs.\n\n"
        "I'd go with Poster 1. It is great.\n\n"
        "The details really matter.\n\n"
        "Hope this helps! Good luck!"
    )
    full = len(re.findall(r"\b[\w']+\b", text.replace("Dear James,", "").replace("Hope this helps! Good luck!", "")))
    body = len(re.findall(r"\b[\w']+\b", " ".join(classroom_body_paragraphs(text))))
    assert body == full
    assert "Dear" not in text.split("\n\n")[1]  # first body block has no Dear


def test_high_b_splits_overall_as_third_paragraph():
    from scripts.generate_classroom_pptx import build_mental_health_deck

    essay = next(s for s in build_mental_health_deck() if "高分版 B" in s["title"])
    body = classroom_body_paragraphs(essay["essay_text"])
    assert len(body) == 3
    assert body[0].startswith("Thanks")
    assert "Firstly" in body[1]
    assert body[2].startswith("Overall,")


def test_essay_layout_tightens_for_long_text():
    long_paras = ["x" * 500, "y" * 300]
    spacing, para_space, _indent = essay_layout_for_length(long_paras)
    assert spacing <= 0.98
    assert para_space <= 6


def test_wrap_first_line_indent():
    lines = wrap_paragraph_lines("Hello world " * 20, width=40, indent_chars=4)
    assert lines[0].startswith("    ")
    assert len(lines) > 1


def test_prepare_classroom_essay_strips_dear_and_inline_word_count():
    raw = (
        "Dear James,\n\n"
        "Glad to hear about your designs.\n\n"
        "I'd go with Poster 1. It is great.\n\n"
        "The details really matter.\n\n"
        "Hope this helps! Good luck!\n\n"
        "Word count: 42\n\n"
        "中文批注：\n\n"
        "- ① 选择明确"
    )
    paragraphs, ann = prepare_classroom_essay_display(raw)
    joined = " ".join(paragraphs)
    assert "Dear" not in joined
    assert "Good luck" not in joined
    assert paragraphs[-1].endswith("Word count: 42")
    assert "①" in ann


def test_extract_essay_block_does_not_bleed_into_next_version():
    from scripts.architecture_v1 import _extract_essay_block

    stage2 = (
        "1. 基础版（9 分档）\n"
        "Dear James,\n\nBody one.\n\nBody two.\n\nBody three.\n\n"
        "Word count: 50\n\n"
        "中文批注：\n- note\n"
        "2. 高分版 A：情感共鸣型\n"
        "Dear James,\n\nAdvanced body.\n\n"
        "Word count: 60\n"
    )
    basic = _extract_essay_block(stage2, "基础版")
    assert "Advanced body" not in basic
    assert basic.startswith("Dear James")
    advanced = _extract_essay_block(stage2, "高分版 A")
    assert "Body one" not in advanced
