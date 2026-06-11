"""Word 导出 Markdown 解析测试。"""

from docx import Document
import io

from utils.export_word import (
    _heading_level,
    _heading_text,
    _iter_markdown_blocks,
    export_workflow_to_word,
)


def test_heading_level_recognizes_h5_h6():
    assert _heading_level("##### 必备级") == 5
    assert _heading_level("###### 子标题") == 6
    assert _heading_level("#### 表格 1") == 4


def test_heading_text_strips_hash_marks():
    assert _heading_text("##### 💡 一句大实话") == "💡 一句大实话"
    assert _heading_text("##### **改一句**") == "改一句"


def test_iter_markdown_blocks_treats_h5_as_heading():
    blocks = list(_iter_markdown_blocks("##### 核心句（P）\n正文段落"))
    assert blocks[0] == ("heading5", "核心句（P）")
    assert blocks[1] == ("paragraph", "正文段落")


def test_export_word_docx_has_no_literal_hash_heading():
    raw = (
        "### 一、功能句型包\n\n"
        "##### 必备级\n"
        "- 句型 A\n\n"
        "##### 改一句\n"
        "❌ bad → ✅ good"
    )
    docx_bytes = export_workflow_to_word(
        question="测试题目",
        stage3_raw=raw,
    )
    doc = Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "#####" not in full_text
    assert "必备级" in full_text
    assert "改一句" in full_text
