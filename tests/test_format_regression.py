"""格式回归：fixtures + prepare_stage_text + Word 无 #####。"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from docx import Document

from utils.export_word import export_workflow_to_word
from utils.stage_format import prepare_stage_text

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("stage", "fixture", "needles"),
    [
        (1, "stage1_snippet.md", ("##### 💡 一句大实话", "要点与结构规划", "结尾段")),
        (2, "stage2_snippet.md", ("##### 核心句（P）", "##### 拓展策略（E）", "#### 1. 基础版")),
        (3, "stage3_snippet.md", ("##### 必备级", "##### 改一句", "mark")),
        (4, "stage4_snippet.md", ("### 一、学情适配", "易错预警")),
    ],
)
def test_prepare_stage_text_fixture(stage: int, fixture: str, needles: tuple[str, ...]) -> None:
    raw = _load(fixture)
    out = prepare_stage_text(stage, raw, target="word")
    for needle in needles:
        assert needle in out


@pytest.mark.parametrize(
    ("stage", "fixture", "kwarg"),
    [
        (1, "stage1_snippet.md", "stage1_summary"),
        (2, "stage2_snippet.md", "stage2_raw"),
        (3, "stage3_snippet.md", "stage3_raw"),
        (4, "stage4_snippet.md", "stage4_raw"),
    ],
)
def test_word_export_no_literal_hash(stage: int, fixture: str, kwarg: str) -> None:
    raw = _load(fixture)
    docx_bytes = export_workflow_to_word(question="测试题目", **{kwarg: raw})
    doc = Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "#####" not in full_text
    assert len(full_text.strip()) > 20
