"""HTML 导出测试。"""

from utils.export_html import export_workflow_to_html


def test_export_html_contains_stages_and_no_literal_hash_heading():
    raw = (
        "### 一、功能句型包\n\n"
        "##### 必备级\n"
        "- 句型 A\n\n"
        "| 列1 | 列2 |\n| --- | --- |\n| a | b |\n"
    )
    html_bytes = export_workflow_to_html(
        question="测试题目",
        stage1_summary="**审题要点**：要点一",
        stage3_raw=raw,
        question_type_label="建议信",
    )
    text = html_bytes.decode("utf-8")
    assert "<!DOCTYPE html>" in text
    assert "测试题目" in text
    assert "Stage 1" in text
    assert "Stage 3" in text
    assert "建议信" in text
    assert "Joyverse" in text
    assert "#####" not in text
    assert "必备级" in text
    assert "<table>" in text


def test_make_export_html_filename_matches_word_basename():
    from services.workflow_storage import make_export_html_filename, make_export_word_filename

    word = make_export_word_filename("glm-5.1", "2026-06-02")
    html_name = make_export_html_filename("glm-5.1", "2026-06-02")
    assert html_name == word.replace(".docx", ".html")
