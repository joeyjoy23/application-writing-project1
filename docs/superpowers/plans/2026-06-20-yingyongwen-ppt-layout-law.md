# 应用文 PPT Layout Law Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已认可的「活」版 Layout Law 落地为 skill 文档与可执行工作流，使 ppt-master **一次生成**合格课堂 PPT，不再依赖 SVG 补丁脚本。

**Architecture:** 文档层（PPT_LAYOUT_LAW + SKILL + SLIDE_BLUEPRINT 交叉引用）约束 Agent Executor；可选只读校验脚本辅助 §5 清单；用心理健康课题 deck 做端到端回归。python-pptx 与 patch 脚本标记 legacy/deprecated，不删源码。

**Tech Stack:** ppt-master（SVG → finalize → svg_to_pptx）、Cursor skill、Python（prepare_ppt_source 保留；校验脚本可选）

**Spec:** `docs/superpowers/specs/2026-06-20-yingyongwen-ppt-layout-law-design.md`

---

## File Map

| File | 职责 |
|------|------|
| `.cursor/skills/yingyongwen-export-to-ppt/PPT_LAYOUT_LAW.md` | Layout 菜单、排版法律、验收清单 |
| `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md` | 工作流、layout 字段、反模式、弃用脚本表 |
| `.cursor/skills/yingyongwen-export-to-ppt/SLIDE_BLUEPRINT.md` | 页型 A–E + layout 映射表 |
| `docs/superpowers/specs/2026-06-20-yingyongwen-ppt-layout-law-design.md` | 设计规格（已写） |
| `.cursor/rules/yingyongwen-export-to-ppt.mdc` | 触发词规则，指向新 skill 路径 |
| `scripts/validate_ppt_svg.py` | **可选** 只读 SVG 检查（不 patch） |
| `d:\Downloads\ppt-work\yingyongwen-outline.md` | 心理健康课题大纲（含 layout 字段） |

---

### Task 1: 文档层落地（本计划核心）

**Files:**
- Create: `.cursor/skills/yingyongwen-export-to-ppt/PPT_LAYOUT_LAW.md`
- Modify: `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md`
- Modify: `.cursor/skills/yingyongwen-export-to-ppt/SLIDE_BLUEPRINT.md`
- Create: `docs/superpowers/specs/2026-06-20-yingyongwen-ppt-layout-law-design.md`

- [x] **Step 1:** 写入 design spec
- [x] **Step 2:** 写入 PPT_LAYOUT_LAW.md（12 layout + 验收清单）
- [x] **Step 3:** 更新 SKILL.md（workflow、layout 字段、弃用表）
- [x] **Step 4:** 更新 SLIDE_BLUEPRINT.md（layout 映射、引擎说明）

---

### Task 2: Cursor 规则同步

**Files:**
- Modify: `.cursor/rules/yingyongwen-export-to-ppt.mdc`

- [ ] **Step 1:** 在 rule 中增加「必读 PPT_LAYOUT_LAW」「禁止默认 patch 脚本」
- [ ] **Step 2:** 确认触发词仍指向 yingyongwen-export-to-ppt skill

---

### Task 3: 心理健康课题大纲重写（含 layout）

**Files:**
- Modify: `d:\Downloads\ppt-work\yingyongwen-outline.md`（或 ppt-work 内副本）

- [ ] **Step 1:** 阅读现有 outline + source.md
- [ ] **Step 2:** 每页补 `layout:` / `variant:` / `anim: on-click`
- [ ] **Step 3:** Slide 6 设为 `insight-trap-key` + `with-probe`

---

### Task 4: ppt-master 端到端重生 V3（无 patch）

**Files:**
- ppt-master project: `C:\Users\Joey\tools\ppt-master\projects\yingyongwen-mental-health-v3_*`
- Output: `d:\Downloads\ppt-work\mental_health_classroom_V3.pptx`

- [ ] **Step 1:** 在 ppt-master 新建或复用项目，Strategist 用 Eight Confirmations 默认值
- [ ] **Step 2:** Executor 逐页 SVG，**严格 PPT_LAYOUT_LAW**（不跑 patch）
- [ ] **Step 3:** `finalize_svg.py` → `svg_to_pptx.py -s final -a fade --animation-trigger on-click`
- [ ] **Step 4:** 执行 §5 验收清单；失败页局部重写（≤2 轮）
- [ ] **Step 5:** PowerPoint 抽查：封面、Slide 6（无空面板）、范文全文、F5 动画

---

### Task 5: 可选只读校验脚本

**Files:**
- Create: `scripts/validate_ppt_svg.py`
- Test: `tests/test_validate_ppt_svg.py`（轻量）

- [ ] **Step 1:** 实现检查：font-size 下限、panel 空撑启发式、Joyverse/页码 grep
- [ ] **Step 2:** CLI：`python scripts/validate_ppt_svg.py path/to/svg_final`
- [ ] **Step 3:** 在 SKILL.md Step 4.5 引用此脚本（可选，非阻塞）

**注意：** 脚本**只报告**，不改 SVG。

---

### Task 6: 弃用标记（源码注释）

**Files:**
- Modify: `scripts/rebuild_ppt_master_v3.py`（文件头 DEPRECATED 注释）
- Modify: `scripts/ppt_v3_svg_patch.py`（文件头 DEPRECATED 注释）

- [ ] **Step 1:** 添加 deprecation 说明，指向 PPT_LAYOUT_LAW + SKILL
- [ ] **Step 2:** 不删除文件（历史可复现）

---

## 验收标准（整体）

- [ ] 用户「出课件」时 skill 文档不引导 patch 脚本
- [ ] 新 outline 每页含 `layout:`
- [ ] V3 重生后 Slide 6 无大块空白
- [ ] 三篇范文各一 slide 全文
- [ ] 无页码、无 Joyverse；正文 ≥26pt
- [ ] F5 放映 on-click 动画正常

---

## 非本计划范围

- 删除 V1/V2 pptx 或 python-pptx 脚本
- 修改 ppt-master 上游核心
- 自动 git commit（用户未要求时不提交）
