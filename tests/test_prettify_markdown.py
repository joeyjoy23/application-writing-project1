from utils.parsers import (
    normalize_vertical_spacing,
    prettify_stage_markdown,
    promote_section_headings,
)


def test_promote_cn_major_section():
    out = promote_section_headings("一、审题要点\n正文")
    assert "### 一、审题要点" in out


def test_tune_peel_demotes_cn_major_and_star_headings():
    raw = "# 一、PEEL 写作策略卡\n\n## ★核心要点 Point 1：foo"
    out = prettify_stage_markdown(raw)
    assert "### 一、PEEL 写作策略卡" in out
    assert "#### ★核心要点 Point 1：foo" in out


def test_tune_peel_demotes_field_headings_below_point():
    raw = (
        "#### ★核心要点 Point 1：x\n"
        "### P（核心句）\n"
        "正文\n"
        "### 拓展策略（E）\n"
        "## 1. 基础版（9 分档）"
    )
    out = prettify_stage_markdown(raw)
    assert "##### 核心句（P）" in out
    assert "##### P（核心句）" not in out
    assert "##### 拓展策略（E）" in out
    assert "#### 1. 基础版（9 分档）" in out


def test_promote_bracket_section():
    out = promote_section_headings("【功能句型包】")
    assert "### 【功能句型包】" in out


def test_tune_stage1_numbered_sections():
    raw = "## 1. 动笔自查五问\n\n### 2.1 三元审题\n\n## 2. 交际任务分析"
    out = prettify_stage_markdown(raw)
    assert "### 1. 动笔自查五问" in out
    assert "#### 2.1 三元审题" in out
    assert "### 2. 交际任务分析" in out


def test_tune_stage3_tables_and_tiers():
    raw = "# 一、功能句型包\n\n## 表格 1：号召\n\n### 必备级"
    out = prettify_stage_markdown(raw)
    assert "### 一、功能句型包" in out
    assert "#### 表格 1：号召" in out
    assert "##### 必备级" in out


def test_normalize_kuozhan_strategy_to_e():
    raw = "### 拓展策略（选1个）\n### 拓展策略（选1-3个给出使用例子）"
    out = prettify_stage_markdown(raw)
    assert "拓展策略（选1个）" not in out
    assert "选1-3个" not in out
    assert out.count("拓展策略（E）") == 2


def test_normalize_benti_gaiyiju_splits_inline_dash():
    raw = (
        "**本题**：适合用对比句型，不适合用命令式句型。- 改一句：❌ You must not write. "
        "→ ✅ Rather than writing on the pages, we can use notebooks."
    )
    out = prettify_stage_markdown(raw)
    assert "- 改一句" not in out
    assert "##### 改一句" in out
    assert "You must not write. ❌" in out
    assert "→ Rather than writing on the pages, we can use notebooks. ✅" in out
    assert "❌ You must" not in out


def test_format_yijuhodashihua_as_h5():
    raw = (
        "### 1. 动笔自查五问\n\n"
        "**💡 一句大实话**（2–3 行）：这篇投稿最容易踩的坑是光提现象。"
    )
    out = prettify_stage_markdown(raw)
    assert "##### 💡 一句大实话" in out
    assert "这篇投稿最容易踩的坑" in out
    assert "一句大实话**（2–3 行）：这篇" not in out


def test_format_gaiyiju_arrow_block_multiline():
    from utils.parsers import format_gaiyiju_arrow_blocks

    raw = (
        "**改一句**：❌ You must not write on the books and you should use paper. "
        "→ ✅ Rather than writing directly on the pages, we can use sticky notes."
    )
    out = format_gaiyiju_arrow_blocks(raw)
    assert "##### 改一句" in out
    assert "paper. ❌" in out
    assert "→ Rather than writing directly" in out
    assert "sticky notes. ✅" in out


def test_tune_stage4_major_sections():
    raw = "# 一、学情适配教学路径\n\n# 禁止事项"
    out = prettify_stage_markdown(raw)
    assert "### 一、学情适配教学路径" in out
    assert "### 禁止事项" in out


def test_normalize_list_spacing_removes_blank_between_items():
    raw = "- 目标：A\n\n- 操作：B\n\n- 反馈：C"
    out = prettify_stage_markdown(raw)
    assert "\n\n- 操作" not in out
    assert "- 目标：A\n- 操作：B\n- 反馈：C" in out.replace("\r\n", "\n")


def test_merge_list_continuation_joins_indented_wrap():
    from utils.parsers import merge_list_item_continuations

    raw = "- **教师引导**：第一句很长。\n  第二句续写。"
    assert "第二句续写" in merge_list_item_continuations(raw).replace("\n  ", " ")


def test_promote_stage4_error_and_practice_headings():
    raw = (
        "### 二、典型错误预警\n\n"
        "1. **语气错位**：像通知\n"
        "- **高发原因**：A\n"
        "- **教师引导**：B\n"
        "### 三、课后练习题\n\n"
        "**练习1：片段升级训练（适合基础/中等）**\n"
        "- **要点指定**：C"
    )
    out = prettify_stage_markdown(raw)
    assert "#### 1. **语气错位**：像通知" in out
    assert "#### 练习1：片段升级训练（适合基础/中等）" in out


def test_stage1_high_score_points_not_h4():
    raw = (
        "### 4. 能力维度与思维模型分析\n\n"
        "- **高分要点**：\n"
        "1. **细节描写要生动：** 用具体动词。\n"
        "2. **逻辑衔接要自然：** 过渡词。"
    )
    out = prettify_stage_markdown(raw)
    assert "#### 1. **细节" not in out
    assert "- **细节描写要生动：**" in out
    assert "- **逻辑衔接要自然：**" in out


def test_stage4_error_list_compact():
    raw = (
        "1. **语气错位**\n\n"
        "- **高发原因**：A\n\n"
        "- **教师引导**：B 很长的一句。\n\n"
        "  续写同一条。\n\n"
        "2. **细节缺失**"
    )
    out = prettify_stage_markdown(raw)
    assert "- **高发原因**：A\n- **教师引导**：B" in out.replace("\r\n", "\n")
    assert "续写同一条" in out
    assert "B 很长的一句。 续写同一条" in out or "B 很长的一句。\n  续写" not in out


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
