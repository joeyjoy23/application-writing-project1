# WPS 课件排版防护规范（2026-06-22）

## 目标

防止 python-pptx 生成的课堂 PPT 在 WPS 放映（F5）时出现截断、重叠、错内容；**优先拆页**，不把正文字号压到 26pt 以下。

## 上游内容槽位上限

| 槽位 | 规则 | 实现 |
|------|------|------|
| A1 封面 | 题干与 `[图：…]` 分离；HTML 实体解码 | `architecture_v1._question_lines` + `poster_lines` |
| C1 思维路径 | 只用「底层思维路径」或维度链；禁止「学生容易写成」类 bullet | `_extract_thinking_chain` |
| F3s 当堂迁移 | 与题干人物/主题冲突的 Stage4 泛化题拒绝 | `_migration_matches_question` + 题干 fallback |
| content 页 | 每页最多 3 条 bullet 卡片 | `expand_content_slides` |
| PEEL | 双卡溢出则每 Point 一页 | `expand_peel_slides` |
| 范文 | 按句/段拆页 | `expand_essay_slides` |
| 句型 footer | `topic_note` 超长 → 双行黄条或 `footer_part=note` 独立页 | `split_banner_text` + `deck_plan.refine_deck_plan` |

## 自动拆页流水线（渲染前必跑）

```
slides = expand_content_slides(
    expand_peel_slides(
        expand_essay_slides(slides)
    )
)
```

入口：`scripts/one_click_classroom_ppt.py` → `_render_and_verify`。

Stage3 句型/词块拆页由 `deck_plan.refine_deck_plan` 在合并前完成。

## WPS 安全系数

| 常量 | 值 | 用途 |
|------|-----|------|
| `FIT_WIDTH_FACTOR` | 0.85 | 规划阶段文本宽度 |
| `WPS_SAFETY_FACTOR` | 0.85 | `verify_text_fit` 验收 |
| `MIN_BODY_PT` | 26 | 禁止再缩小 |

原则：**needs_split → 拆页**，而非继续缩字。

## WPS F5 抽验清单

1. **封面**：题干区无 `[图：…]` 原文；海报描述在下方「图」区块；`'` 等实体已解码。
2. **C1**：3–5 行思维链（含 ↓），无 triplet / 易错长段。
3. **content 卡片**：无底部裁切、无互相重叠。
4. **句型 footer**：黄条「本题」全文可见（可两行）。
5. **F3s**：迁移题与 James/心理健康一致，无 Lucy/环保串题。
6. **PEEL E 行**：以英文引语为主，无中文 meta 标签残留。
7. **终端**：`verify_text_fit` 返回空列表。

## 回归测试

- `tests/test_architecture_v1.py`：题干解码、C1 路径、迁移过滤、poster_lines
- `tests/test_ppt_layout_fit.py`：`expand_content_slides`、`split_banner_text`

改 `architecture_v1` / `ppt_layout_fit` / V2 渲染器后：**pytest 全绿 + 可选一键导出 F5 抽验**。

## 变更门禁

1. 改 slot 填槽逻辑 → 补 architecture 单测
2. 改布局预算 → 补 layout_fit 单测
3. 合并前跑 `expand_*` 链 + `verify_text_fit`
4. 重大排版修复 → 更新本文档日期与表格

## 渲染硬规则（2026-06-22 增补）

| 规则 | 说明 |
|------|------|
| 框高 shrink-wrap | 圆角矩形高度 = `fit_typography` / `fit_paragraphs` 实测块高 + padding；禁止用固定 `min` 高度忽略 fit 结果（封面海报区、stem 白框） |
| 箭头分隔符 | `↓` `→` `↔` 等链式箭头：**无**卡片底框，居中纯文字，`ARROW_SEP_HEIGHT≈0.12"`；不计入 `MAX_CONTENT_BULLETS` |
| 范文批注 | 英文正文与中文批注（①②③）**纵向堆叠**：`annotation_top = body_top + body_height + gap`；禁止与正文共用起始 Y 或垂直居中导致重叠 |

实现：`plan_title_cover_layout`、`plan_essay_stack`、`is_arrow_separator`（`ppt_layout_fit.py`）；V2 渲染器 `generate_classroom_pptx_v2.py`。
