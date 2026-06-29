# Stage 3 完整上屏 · 确定性 PPT 渲染设计规格

**日期：** 2026-06-18  
**状态：** 已认可（用户选 A；基础档省略中文释义与拓展说明）  
**关联：** 补全 `2026-06-20-yingyongwen-ppt-layout-law-design.md` 中 Executor 对页型 D 的不可靠性

---

## 1. 问题陈述

Stage 3（功能句型 + 话题词块）是课堂「语言支架」核心，学生需在投影上完整积累。当前链路存在三层数据丢失：

1. **大纲 Agent** 将表格压成 slash 列表  
2. **ppt-master Executor** 再次摘要 SVG 内容  
3. **临时脚本** `build_ppt_vocab_svg.py` 仅竖排 4 行 bullet，无表格结构

结果：内容不全、排版丑、与 Joyverse Stage 3 导出脱节。

---

## 2. 目标

| 项 | 要求 |
|----|------|
| 内容保真 | Stage 3 表格 **逐字来自导出**，禁止 LLM 改写 |
| 课堂积累 | 投影即讲义；**28–32 页**详细版可接受 |
| 基础档从简 | **必备/基础句**：仅英文 + 例句（词块）或仅英文（句型）；**无中文释义、无高分说明、无用途展开** |
| 进阶/亮点 | 句型：英文 + 中文说明；词块：英文 \| 中文 \| 例句 三列 |
| ppt-master 角色 | **不做 Stage 3 内容**；仅 finalize、动画、导出；Executor 限 A/B/E 页 |
| 拆页 | 词块表 **>6 行/页** 自动拆页；句型「改一句」过长可独立 1 页 |

---

## 3. 架构

```
Joyverse 导出 (HTML/Word)
    → prepare_ppt_source.py
        → yingyongwen-source.md
        → stage3.json          ← NEW：结构化真相
    → Agent 大纲 yingyongwen-outline.md
        → 页序 + layout + source 指针（禁止手写英文摘要）
    → build_ppt_stage3_svg.py  ← NEW：确定性 SVG
    → build_ppt_essay_svg.py   （范文，已有）
    → ppt-master Executor        （封面/审题/Stage4 等）
    → finalize_svg → svg_to_pptx
```

**单一数据源：** `stage3.json` 由 `parse_stage3.py` 从 Stage 3 Markdown 解析；大纲与 SVG 均引用此文件，不重复存英文正文。

---

## 4. 数据模型（stage3.json）

```json
{
  "phrase_tables": [
    {
      "name": "观点表达",
      "tiers": [
        {"level": "基础句", "english": "...", "chinese": "...", "high_score": null},
        {"level": "进阶句", "english": "...", "chinese": "...", "high_score": null},
        {"level": "高级句", "english": "...", "chinese": "...", "high_score": "..."}
      ],
      "topic_note": "本题：…",
      "fix_bad": "... ❌",
      "fix_good": "→ ... ✅"
    }
  ],
  "vocab_fields": [
    {
      "name": "设计元素描述",
      "tiers": [
        {
          "level": "必备级",
          "rows": [{"english": "...", "chinese": "...", "example": "..."}]
        }
      ]
    }
  ]
}
```

解析器须兼容：

- Word/HTML 导出后的 **Markdown 表格**（`| col |`）
- **Tab 分列** 的纯文本（见 `d:\Downloads\ppt-work\yingyongwen-source.md` Stage 3 段）

---

## 5. 页型 D 渲染规则

### 5.1 功能句型页（`phrase-tier`）

**单页结构（默认 1 功能 = 1 slide）：**

| 区块 | 基础句 | 进阶句 | 高级句 |
|------|--------|--------|--------|
| 英文 | ✓ 单行 | ✓ 可换行 | ✓ 可换行 |
| 中文说明 | ✗ | ✓ 一行 | ✓ 一行 |
| 高分说明 | ✗ | ✗ | ✓ 可选 1–2 行 |
| 本题 | 页底 1 行（三级共用） | | |
| 改一句 | 对比框：❌ 行 + ✅ 行 | | |

**拆页：** 若高级句 + 改一句超出 `Y_MAX`，改一句移至 `phrase-fix` 第 2 slide。

**视觉：** 浅紫面板 `#F5F3FF`；左色条：基础 `#94A3B8`、进阶 `#6366F1`、高级 `#7C3AED`；字号：英文 32px、中文 28px（≥26pt 投影）。

### 5.2 话题词块页（`vocab-table`）

| 层级 | 列 | 行数 |
|------|-----|------|
| **必备级** | 英文词块 \| 例句（**2 列，无中文释义**） | 5–7 |
| **进阶级** | 英文 \| 中文 \| 例句 | 5–7 |
| **亮点级** | 英文 \| 中文 \| 例句 | 5–7 |

**拆页：** 同一 tier 超过 6 行 → 按 6 行分页，标题后缀 `· 必备 1/2`。

**视觉：** 表头色条（必备 `#E2E8F0`、进阶 `#DDD6FE`、亮点 `#C4B5FD`）；逐行 `reveal-NN` on-click。

---

## 6. 页数预算（心理健康课题）

| 区块 | 页数 |
|------|------|
| 题目 + 审题 + Stage4 易错 | ~8 |
| 范文 + 对比 + 讲评 | ~8 |
| 功能句型 ×3 | 3–6 |
| 话题词块 ×3 语义场 ×3 tier | 9–12（含拆页） |
| 迁移 + 易错深化 + 小结 | ~4 |
| **合计** | **28–32** |

---

## 7. 大纲格式（机器可读）

```markdown
## Slide 18 · 话题词块 · 设计元素 · 必备
layout: vocab-table
source: stage3.json#vocab_fields[1].tiers[0]
anim: on-click
```

**禁止：** `prefer / lean towards / strike me as` 类 slash 摘要。

---

## 8. ppt-master 边界

| 组件 | Stage 3 相关职责 |
|------|------------------|
| Strategist | 确认总页数 ~30、节奏 dense |
| Executor | **禁止** 生成 slide 14–N（句型词块段）；仅 A/B/E |
| finalize_svg | 嵌字、圆角转 path |
| svg_to_pptx | fade + on-click 动画 |

与范文页策略一致：**内容脚本出 SVG，ppt-master 出壳与导出**。

---

## 9. 废弃与迁移

| 项 | 处理 |
|----|------|
| `build_ppt_vocab_svg.py` | 由 `build_ppt_stage3_svg.py` 取代；文件头 DEPRECATED |
| Executor 手排 17–19 | 禁止 |
| `generate_classroom_pptx.py` 内 Stage3 demo bullets | 保留作离线 fallback；非 ppt-master 主路径 |

---

## 10. 验收标准

- [ ] `parse_stage3.py` 解析 `yingyongwen-source.md` Stage 3 段，3 句型表 + 3 语义场 × 3 tier 完整  
- [ ] 心理健康 V3 导出 28–32 页；slide 18 必备级 **2 列**（英文+例句），无中文释义  
- [ ] 进阶/亮点词块 **3 列**完整  
- [ ] 句型基础档 **仅英文**，无中文说明  
- [ ] pytest：`test_parse_stage3.py`、`test_build_ppt_stage3_svg.py` 通过  
- [ ] SKILL.md / SLIDE_BLUEPRINT.md 更新工作流 Step 4.6  

---

## 11. 非目标

- 不改 Stage 3 LLM prompt 结构（导出已够丰富）  
- 不在此阶段脚本化全部 A/B/E 页（仍由 Executor）  
- 不删除 ppt-master Executor 能力，仅缩小其内容职责范围  
