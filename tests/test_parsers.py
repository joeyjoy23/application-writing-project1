"""Stage1 输出解析回归测试。"""

from utils.parsers import (
    JSON_MARKER,
    SUMMARY_MARKER,
    clean_stage1_summary,
    parse_stage1_output,
    sanitize_llm_html_breaks,
    strip_reader_self_check,
)


def test_parse_stage1_markers():
    raw = f"""{JSON_MARKER}
{{"genre": "建议信", "points": ["a", "b"]}}
{SUMMARY_MARKER}
## 体裁
建议信

## 输出前自检
- 要点已覆盖
"""
    structured, summary = parse_stage1_output(raw)
    assert structured.get("genre") == "建议信"
    assert "体裁" in summary
    assert "输出前自检" not in summary


def test_parse_stage1_part_a_b_split():
    raw = """# PART A: STRUCTURED_JSON
```json
{"task_type": "letter"}
```
# PART B: HUMAN_READABLE_SUMMARY
**体裁**：建议信
"""
    structured, summary = parse_stage1_output(raw)
    assert structured.get("task_type") == "letter"
    assert "建议信" in summary


def test_clean_stage1_summary_strips_json_fence():
    text = "```json\n{}\n```\n**要点**：三条"
    assert "json" not in clean_stage1_summary(text).lower() or "要点" in text


def test_strip_prompt_instruction_leaks():
    from utils.parsers import strip_prompt_instruction_leaks

    body = (
        "正文\n\n"
        "（单独小标题；**下一段起**写 2–3 行正文）收束五问；用备课组长口吻点出本题最危险的陷阱。"
        "勿与标题写在同一行，勿在标题后用冒号接正文。实质内容在这里。"
    )
    out = strip_prompt_instruction_leaks(body)
    assert "收束五问" not in out
    assert "实质内容在这里" in out


def test_strip_reader_self_check():
    body = "正文\n\n### 输出前自检\n- [x] ok"
    assert "输出前自检" not in strip_reader_self_check(body)


def test_sanitize_llm_html_breaks():
    assert "<br>" not in sanitize_llm_html_breaks("第一句<br>第二句").lower()
