# 全站格式稳定 — 设计说明

**日期：** 2026-06-13  
**状态：** 已实现（P0 + P1 + P3）  
**范围：** 历史列表 + Stage 1–4 页面展示 + Word 导出

## 背景

用户反馈格式「不时」出现小问题，主要集中在：

1. 历史列表右侧挤、列对不齐  
2. Stage 正文标题/列表/表格渲染不稳定  
3. Word 导出与网页展示不一致  

## 根因（简要）

| 区域 | 原因 |
|------|------|
| 历史列表 | 用 `st.columns` 拼表格，列宽随窗口变化；收藏按钮曾误写在操作列（`cols[6]`），与表头错位 |
| Stage 展示 | LLM 输出形态多变，靠链式正则事后修补 |
| Word 导出 | 与网页并非完全同一条「整理格式」流水线 |

## 目标

- 历史列表：时间到分钟、收藏/删除列固定宽度、表头不换行  
- Stage / Word：**同一套**正文整理函数，减少「网页好、Word 坏」  
- 改 prompt 或改代码后：用固定样例自动回归，减少悄悄变坏  

## 非目标

- 不重做全站 UI 主题  
- 本期不改 Stage 业务内容，只动格式层  
- 不做 PDF 导出  

---

## 历史列表（用户选择：方案 A）

**保持现有交互：**

- 「只读查看」「载入编辑」两个按钮继续外露  
- 「收藏 ☆」「删除 🗑」各占独立列，列宽固定，表头横向显示  

**技术做法：**

1. **P0** 修正列索引：收藏 → `cols[7]`，删除 → `cols[8]`  
2. **P0** 抽常量 `HISTORY_COL_WEIGHTS`，表头行与数据行共用  
3. **P0** CSS：`.history-table-head` 等，`white-space: nowrap`；收藏/删除列 `min-width`  
4. **P0** 时间列用 `format_created_at_list`（`YYYY-MM-DD HH:MM`）  
5. **P2（可选）** 若 CSS 仍不够稳，再改为 HTML `<table>`，但**仍保留方案 A 的四列操作布局**（两按钮 + 星 + 删）  

---

## Stage 展示 + Word 导出（统一管线）

新增统一入口（建议 `utils/stage_format.py`）：

```text
prepare_stage_text(stage, raw, target="ui" | "word")
  → sanitize（Stage3 等）
  → strip_reader_self_check
  → prettify_stage_markdown
```

**接入点：**

- `ui/stage_display.py` — 页面渲染  
- `utils/export_word.py` — Word 写入前  
- 导出按钮相关路径 — 与上同源  

Stage 3 词汇表 UI 专用表格保留，但输入须先经 `prepare_stage_text`。

---

## 回归测试（Golden）

在 `tests/fixtures/` 放置各 Stage 样例 Markdown（来自真实输出片段）：

- `test_format_regression.py`：prettify 结果关键片段  
- `test_export_word.py` 扩展：导出无字面量 `#####`  
- AppTest：历史页表头含「收藏」「删除」且可加载  

`utils/prompt_rev.py` 或 stage prompt 变更时，CI 跑上述测试。

---

## 分期实施

| 期 | 内容 | 用户可见效果 |
|----|------|--------------|
| **P0** | 历史列 bug + 列宽常量 + CSS + 时间到分钟 | 右边不再挤、列对齐 |
| **P1** | `prepare_stage_text` 统一，UI/Word 全接入 | 网页与 Word 更一致 |
| **P2** | 历史改 HTML 表（仅当 P0 仍不足） | 窄屏也稳 |
| **P3** | golden fixtures + 回归测试 | 以后少「时不时」坏 |
| **P4（后续）** | prompt 规定 Canonical Markdown，减少 regex | 长期更稳 |

**本期实施范围：P0 + P1 + P3**；P2 视 P0 效果再定；P4 单独迭代。

---

## 验收标准

- [ ] 历史列表：表头「收藏」「删除」横向显示；星/删与表头同列  
- [ ] 历史列表：时间无秒，如 `2026-06-13 10:09`  
- [ ] Stage 1–4 页面与 Word 导出对同一段正文，标题层级一致  
- [ ] Word 全文无 `#####` 字面量  
- [ ] pytest 全绿，含新增 format regression  

---

## 用户确认项

- [x] 范围：历史 + Stage 展示 + Word  
- [x] 历史操作：方案 A（两按钮外露 + 星/删独立列）  
- [x] 实施范围：P0 + P1 + P3  
