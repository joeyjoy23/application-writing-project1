# 应用文课堂 PPT · Layout Law 设计规格

**日期：** 2026-06-20  
**状态：** 已认可（用户选择「活」版 A 方案）  
**目标：** 通过 skill 约束 ppt-master **一次生成合格课件**，禁止默认用 Python 脚本补丁 SVG。

---

## 1. 问题陈述

V3（ppt-master）勉强可用，但多次出现：

- 面板固定撑满 → 下方大块空白（如「一句大实话」页）
- 长英文单行不换行 → 挤出框外
- 封面/要点页元素重叠
- 动画过少或一次全出

根因：**SLIDE_BLUEPRINT 只有内容/字号规则，缺少 Executor 级排版法律**；Agent 走 `rebuild_ppt_master_v3.py` / `ppt_v3_svg_patch.py` 事后改坐标，质量不可控。

用户要求：**约束 skill，让 ppt-master 直接生成符合要求的 PPT**，而非脚本处理。

---

## 2. 决策摘要

| 项 | 决策 |
|----|------|
| 主引擎 | **ppt-master only**（Strategist → Executor SVG → finalize → svg_to_pptx） |
| 灵活度 | **「活」**：10–12 种 layout + variant，允许 `layout: custom`（严检） |
| 脚本 | 仅保留 `prepare_ppt_source.py`；**禁止**默认 `generate_classroom_pptx*.py`、`rebuild_ppt_master_v3.py` |
| 动画 | 默认 `on-click` + `reveal-NN` groups；放映 F5 |
| 失败处理 | 自动检查 → **只重写失败页 SVG**（可换 variant），最多 2 轮 |
| V1/V2 | 历史备份，skill **不自动生成** |

---

## 3. 工作流（新）

```
prepare_ppt_source.py → yingyongwen-source.md + blueprint.json
Agent 撰写 yingyongwen-outline.md（每页 layout + variant + anim）
ppt-master Strategist（Eight Confirmations 默认值）
ppt-master Executor（严格 PPT_LAYOUT_LAW.md）
finalize_svg.py → svg_to_pptx.py（-a fade --animation-trigger on-click）
课堂检查清单（PPT_LAYOUT_LAW §验收）
失败页局部重写（换 variant 或拆页）
交付 mental_health_classroom_{课题}.pptx
```

---

## 4. Layout 菜单（10–12）

详见 `.cursor/skills/yingyongwen-export-to-ppt/PPT_LAYOUT_LAW.md`。

要点：

- 每页大纲必填 `layout:`；可选 `variant:`、`anim:`
- 面板高度 **内容驱动**，禁止无内容撑满底边（y=680）
- 内容过少 → `with-probe` variant 或拆页，不允许空白大块
- SVG 字号 px：正文 ≥35（≈26pt），标题 ≥51（≈38pt）

---

## 5. 三道闸口（预防未列出的问题）

1. **生成前**：Layout Law + 大纲 layout 字段  
2. **导出前**：ppt-master quality check + 课堂清单（溢出、空面板、字号、范文完整）  
3. **导出后**：用户可选抽查；Agent 必查封面、审题、trap-key、PEEL、范文各 1 页  

---

## 6. 非目标

- 不在此阶段重写 ppt-master 核心  
- 不删除 `generate_classroom_pptx*.py` 源码（仅 skill 弃用）  
- 不承诺零人工；承诺 **问题类型可预防 + 失败可定位**

---

## 7. 交付物

| 文件 | 用途 |
|------|------|
| `PPT_LAYOUT_LAW.md` | Agent Executor 必读排版法律 |
| `SKILL.md` 更新 | 工作流、反模式、检查清单 |
| `SLIDE_BLUEPRINT.md` 更新 | 交叉引用 Layout Law；移除脚本默认路径 |
| `docs/superpowers/plans/2026-06-20-yingyongwen-ppt-layout-law.md` | 实施计划 |

---

## 8. 验收标准（整体）

- [ ] 用户说「出课件」时 Agent 不调用 `rebuild_ppt_master_v3.py`  
- [ ] 新大纲每页含 `layout:`  
- [ ] 「一句大实话」类页使用 `insight-trap-key`，无块延伸到底边  
- [ ] 导出前检查清单有文档且 Agent 执行  
- [ ] 交付说明含 F5 放映与 on-click 动画提示  
