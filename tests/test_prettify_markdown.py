from utils.parsers import prettify_stage_markdown, promote_section_headings


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
