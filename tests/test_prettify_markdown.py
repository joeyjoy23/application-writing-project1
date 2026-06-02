from utils.parsers import (
    normalize_vertical_spacing,
    prettify_stage_markdown,
    promote_section_headings,
)


def test_promote_cn_major_section():
    out = promote_section_headings("一、审题要点\n正文")
    assert "## 一、审题要点" in out


def test_promote_bracket_section():
    out = promote_section_headings("【功能句型包】")
    assert "## 【功能句型包】" in out


def test_prettify_inserts_blank_line_before_heading():
    raw = "段落\n## 小节"
    out = prettify_stage_markdown(raw)
    assert "段落\n\n## 小节" in out


def test_prettify_collapses_extra_blank_lines():
    assert prettify_stage_markdown("a\n\n\n\nb") == "a\n\nb"


def test_normalize_inserts_gap_between_label_lines():
    raw = "**考查的能力维度**：A\n**理由**：B\n**设计意图**：C"
    out = normalize_vertical_spacing(raw)
    assert "**考查的能力维度**：A\n\n**理由**：B\n\n**设计意图**：C" == out


def test_normalize_gap_after_list_before_label():
    raw = "- 词数约 80\n**考查的能力维度**：选 X"
    out = normalize_vertical_spacing(raw)
    assert "- 词数约 80\n\n**考查的能力维度**：选 X" in out
