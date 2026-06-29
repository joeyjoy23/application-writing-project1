"""Tests for student-facing classroom content filter."""

from scripts.classroom_content_filter import (
    is_student_insight_quote,
    is_teacher_only_line,
    normalize_activity_line,
    parse_stage4_student_from_export,
    sanitize_student_text,
    student_bullets_from_slide,
)


def test_teacher_guidance_quote_not_student_insight():
    assert not is_student_insight_quote("引导：用 Stage 3 词块 + PEEL 范文片段做「改一句」即时练。")
    assert is_student_insight_quote("陷阱：只说 I think Poster 1 is good 而不分析元素。")


def test_activity_line_strips_timing():
    assert "10" not in normalize_activity_line("10′ 元素–主题关联拆解（看海报 → 造句）")
    assert "元素" in normalize_activity_line("10′ 元素–主题关联拆解（看海报 → 造句）")


def test_student_bullets_drop_teacher_quote():
    slide = {
        "data_title": "易错",
        "bullets": [
            "理由空泛 — 只写 about mental health，不绑设计元素",
        ],
        "quote": "引导：用 Stage 3 词块 + PEEL 范文片段做「改一句」即时练。",
    }
    bullets = student_bullets_from_slide(slide, include_insight_quote=True)
    assert len(bullets) == 1
    assert "引导" not in bullets[0]
    assert not any("💡" in b for b in bullets)


def test_parse_stage4_extracts_student_tasks():
    stage4 = """
活动1：元素拆解（10分钟）
- 目标：激活关联思维
- 教师操作：展示海报
- 学生任务：用 Stage3 词块造句，将元素与主题关联。

二、典型错误预警
1. **理由空泛，未结合设计元素**：The poster is good because it's about mental health.
- 教师引导：用 Stage3 词块绑定元素

三、课后练习题
练习2：完整写作迁移
- 写作题：你是李华，Lucy 环保海报二选一并说明理由。
"""
    parsed = parse_stage4_student_from_export(stage4)
    assert parsed["activities"]
    assert "Stage3" in parsed["activities"][0] or "词块" in parsed["activities"][0]
    assert parsed["warn"] and parsed["warn"][0].startswith("❌")
    assert parsed["migration"] and "Lucy" in parsed["migration"][0]


def test_sanitize_student_text_strips_mandatory_point():
    raw = '要点指定：mandatory_point "论证逻辑"（即避免空泛） 基础片段：I put study first.'
    clean = sanitize_student_text(raw)
    assert "mandatory_point" not in clean.lower()
    assert "要点指定" not in clean
    assert "I put study first" in clean


def test_parse_stage4_warn_without_bold_markers():
    stage4 = """
二、典型错误预警
1. “投稿体”误判为“私人信”：开头写成问候寒暄
2. “正确废话”陷阱：用义务腔替代个人化理由
"""
    parsed = parse_stage4_student_from_export(stage4)
    assert len(parsed["warn"]) >= 2
    assert all("mental health" not in w for w in parsed["warn"])
    assert "投稿体" in parsed["warn"][0]
