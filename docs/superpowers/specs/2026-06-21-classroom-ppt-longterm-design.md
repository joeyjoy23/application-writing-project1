# 课堂 PPT 长期方案（定稿）

**日期：** 2026-06-21  
**状态：** 长期复用  
**取代：** ppt-master 全路径；Oh My PPT 仅可选润色

---

## 1. 目标

| 项 | 要求 |
|----|------|
| 输入 | Joyverse Word/HTML 导出 |
| 内容 | Stage3 确定性解析（`stage3.json`） |
| 结构 | LLM 产出 `classroom_deck.json`（页型 + 拆页 + source 指针） |
| 呈现 | V2 python-pptx + **布局预算** + **26–32pt 弹性字号** |
| 动画 | WPS on-click fade（`pptx_click_reveal.py`） |
| 验收 | `verify_text_fit` 无 overflow；WPS F5 抽验 |

---

## 2. 三层分工（核心）

```
┌─────────────────────────────────────────────────────────┐
│ 内容层（确定性）                                         │
│ prepare_ppt_source → source.md + stage3.json            │
├─────────────────────────────────────────────────────────┤
│ 结构层（LLM，可选）                                      │
│ prompts/classroom_deck_prompt.md → classroom_deck.json    │
│ · 只选 layout + 拆页 · 不写装饰/坐标/字号               │
├─────────────────────────────────────────────────────────┤
│ 呈现层（确定性）                                         │
│ ppt_layout_fit.py  布局预算 + 弹性字号                   │
│ generate_classroom_pptx_v2.py  模板渲染                  │
│ pptx_click_reveal.py  动画                                │
└─────────────────────────────────────────────────────────┘
```

**LLM 预留装饰空间的方式：** 选用带占屏预算的 `layout`，遵守每 layout 容量表；**不是**在 markdown 里描述黄条。

---

## 3. Layout 注册表

见 `scripts/ppt_layout_fit.py` → `LAYOUT_REGISTRY`。

| layout | 自动装饰（适度） | LLM 容量规则 |
|--------|------------------|--------------|
| `phrase_table_body` | 句型 tag + 技能 pill | 仅 3 tier 表格 |
| `phrase_table_footer` | 本题黄条 + 改错双卡片 | 1 本题 + 1 错 + 1 对 |
| `vocab_table` | 层级 pill + 提示 | ≤6 行 |
| `content_key` | ≤1 黄条 | 1 关键句 + ≤3 要点 |
| `peel_dual` | 双卡片 P/E/L | 2 Point |

---

## 4. 字号弹性

| 文本类型 | 范围 | 策略 |
|----------|------|------|
| 背句 / 词块 / P·L 英文 | 28–32pt | 优先大，fit 失败逐级降到 26 |
| 说明 / 中文 / 本题 | 26–28pt | 次级 |
| 全局下限 | **26pt** | 低于则拆页，不压扁行高 |

算法：`pick_font_pt()` → 试 32→30→28→26 → 仍溢出则 `deck_plan` 拆页（非缩字号到 24）。

---

## 5. 一键命令

```powershell
python scripts/one_click_classroom_ppt.py "导出.docx" -o "ppt-work"
# 可选：先让 Agent 按 prompts/classroom_deck_prompt.md 写 ppt-work/classroom_deck.json
python scripts/one_click_classroom_ppt.py "导出.docx" -o "ppt-work" --deck-plan ppt-work/classroom_deck.json
```

---

## 6. 非目标

- ppt-master / SVG Executor  
- Oh My PPT 作为主引擎  
- LLM 手写 HTML/SVG/OOXML  

---

## 7. 演进

1. ✅ 句型 body/footer 拆页  
2. ✅ `ppt_layout_fit` + deck prompt  
3. 🔲 审题/Stage4 从 source 动态生成 deck（去 mental_health 硬编码）  
4. 🔲 生成后 overflow → 自动二次拆页  
