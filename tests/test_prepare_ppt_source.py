"""prepare_ppt_source.py 测试。"""

import json
import tempfile
from pathlib import Path

from scripts.prepare_ppt_source import prepare_ppt_source
from utils.export_html import export_workflow_to_html
from utils.export_word import export_workflow_to_word


def test_prepare_from_html_export_default_skip_outline():
    html_bytes = export_workflow_to_html(
        question="Write a poster about mental health.",
        stage1_summary="**题型**：观点理由类\n- 要点一",
        stage2_raw="## PEEL\n\nParagraph one.",
        stage3_raw="### 句型\n- Pattern A",
        stage4_raw="### 活动\n1. 讨论",
        question_type_label="观点理由类",
    )
    with tempfile.TemporaryDirectory() as tmp:
        export_path = Path(tmp) / "report.html"
        export_path.write_bytes(html_bytes)
        out_dir = Path(tmp) / "out"
        result = prepare_ppt_source(export_path, out_dir)
        assert len(result) == 2
        md_path, json_path = result
        md = md_path.read_text(encoding="utf-8")
        blueprint = json.loads(json_path.read_text(encoding="utf-8"))
        assert "mental health" in md
        assert "Stage 1" in md
        assert "Stage 2" in md
        assert blueprint["suggested_total_pages"] >= 10
        assert blueprint["question_type_label"] == "观点理由类"
        assert len(blueprint["page_types"]) == 5
        assert not (out_dir / "yingyongwen-outline.md").exists()


def test_prepare_from_html_export_draft_outline():
    html_bytes = export_workflow_to_html(
        question="Write a poster about mental health.",
        stage1_summary="**题型**：观点理由类\n- 要点一",
        stage2_raw="## PEEL\n\nParagraph one.",
        stage3_raw="### 句型\n- Pattern A",
        stage4_raw="### 活动\n1. 讨论",
        question_type_label="观点理由类",
    )
    with tempfile.TemporaryDirectory() as tmp:
        export_path = Path(tmp) / "report.html"
        export_path.write_bytes(html_bytes)
        out_dir = Path(tmp) / "out"
        md_path, json_path, outline_path = prepare_ppt_source(
            export_path, out_dir, outline="draft"
        )
        outline = outline_path.read_text(encoding="utf-8")
        assert outline_path.is_file()
        assert "PPT大纲" in outline or "课堂 PPT 大纲" in outline
        assert "Stage1" in outline or "审题" in outline
        assert "完整英文范文原文" in outline or "范文原文必须完整上屏" in outline
        assert "Stage4" in outline and ("融入" in outline or "动笔易错" in outline)
        assert md_path.is_file()
        assert json_path.is_file()


def test_prepare_from_docx_export():
    docx_bytes = export_workflow_to_word(
        question="Dear editor,",
        stage1_summary="审题内容",
        question_type_label="建议信",
    )
    with tempfile.TemporaryDirectory() as tmp:
        export_path = Path(tmp) / "report.docx"
        export_path.write_bytes(docx_bytes)
        md_path, json_path = prepare_ppt_source(export_path, Path(tmp) / "out")
        md = md_path.read_text(encoding="utf-8")
        assert "Dear editor" in md
        assert "建议信" in md
        assert "Stage 1" in md
        assert json_path.is_file()


def test_prepare_classroom_html_uses_analysis_not_classroom_skeleton():
    """-课件.html 默认只解析 sibling 分析报告，不写 classroom-data.json。"""
    html_bytes = export_workflow_to_html(
        question="Write a poster about mental health.",
        stage1_summary="**题型**：观点理由类\n- 要点一",
        stage2_raw="## PEEL\n\nParagraph one.",
        stage3_raw="### 一、功能句型包\n\n表格 1：观点",
        stage4_raw="### 活动\n1. 讨论",
        question_type_label="观点理由类",
    )
    classroom_html = (
        '<html><body>'
        '<section class="slide" data-title="封面">'
        '<h1>课堂课件</h1><p class="subtitle">预览</p></section>'
        "</body></html>"
    )
    with tempfile.TemporaryDirectory() as tmp:
        analysis_path = Path(tmp) / "report.html"
        analysis_path.write_bytes(html_bytes)
        classroom_path = Path(tmp) / "report-课件.html"
        classroom_path.write_text(classroom_html, encoding="utf-8")
        out_dir = Path(tmp) / "out"
        prepare_ppt_source(classroom_path, out_dir)
        md = (out_dir / "yingyongwen-source.md").read_text(encoding="utf-8")
        assert "mental health" in md
        assert "Stage 3" in md
        assert not (out_dir / "classroom-data.json").exists()
        assert (out_dir / "stage3.json").is_file()


def test_prepare_college_life_docx_parses_stage3_tables():
    """Word 导出 Stage3 句型/词块在表格里，须完整进入 stage3.json。"""
    docx_path = Path(r"d:\Downloads\应用文分析_2026-06-14_deepseek-v4-pro.docx")
    if not docx_path.is_file():
        return
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "out"
        prepare_ppt_source(docx_path, out_dir)
        stage3 = json.loads((out_dir / "stage3.json").read_text(encoding="utf-8"))
        assert stage3["phrase_tables"][0]["tiers"], "phrase tiers missing from Word tables"
        assert "When it comes to" in stage3["phrase_tables"][0]["tiers"][0]["english"]
        vocab_rows = sum(
            len(t.get("rows") or [])
            for f in stage3.get("vocab_fields", [])
            for t in f.get("tiers", [])
        )
        assert vocab_rows >= 15, f"expected vocab rows from docx tables, got {vocab_rows}"
        assert any(
            r.get("english") == "lay a solid foundation"
            for f in stage3["vocab_fields"]
            for t in f["tiers"]
            for r in t.get("rows", [])
        )
