# V1 课堂 PPT · Stage3 表格 + 自动 on-click（WPS 优先）

**日期：** 2026-06-20  
**状态：** 已认可（用户：方案 A + 动画 A，目标 **WPS 演示**）  
**取代：** ppt-master V3 主路径；`build_ppt_stage3_svg.py` 等 SVG 管线降为 legacy

---

## 1. 目标

| 项 | 要求 |
|----|------|
| 引擎 | **仅 V1**：`generate_classroom_pptx.py` + python-pptx |
| 内容 | Stage 3 来自 Joyverse 导出 → `stage3.json`（复用 `parse_stage3.py`） |
| 排版 | Stage 3 **原生表格**（非 bullet）；功能句型表 + 词块表 |
| 动画 | **自动 on-click**；仅 **出现/淡入** 一种效果（稳定性优先） |
| 放映环境 | **WPS 演示**（金山 WPS Office）为主验收；MS PowerPoint 为辅 |
| 大纲 | LLM 产出 **`classroom_deck.json`** 设计页序/拆页/layout，不手写英文摘要 |
| 兜底 | 动画注入失败仍交付无动画 PPT + 日志警告（方案 A+C） |

---

## 2. 非目标

- 不使用 ppt-master Strategist/Executor/SVG
- 不追求飞入、强调等多效果
- 不在此阶段改 Stage 1–2 LLM prompt 结构

---

## 3. 架构

```
Joyverse 导出 (.html / .docx)
    → prepare_ppt_source.py
        → yingyongwen-source.md
        → stage3.json
        → yingyongwen-blueprint.json（页型统计，可选）
    → Agent（大纲阶段）
        → classroom_deck.json   ← LLM 设计页序 + layout + source 指针
    → generate_classroom_pptx.py
        → 读 export + stage3.json + classroom_deck.json（或内置默认 deck）
        → phrase_table_slide / vocab_table_slide
        → 每可动画单元独立 shape（行级）
    → pptx_click_reveal.py
        → 注入 OOXML p:timing（fade/appear, on-click）
    → <课题>_classroom.pptx
```

**一键入口：** `one_click_classroom_ppt.py` 改为默认调用 V1 管线，不再写 ppt-master `NEXT_STEP.txt`。

---

## 4. 数据模型

### 4.1 `stage3.json`（已有）

由 `parse_stage3.py` 解析，结构不变：`phrase_tables[]`、`vocab_fields[]`。

### 4.2 `classroom_deck.json`（新增）

LLM 在大纲阶段输出（Agent 读 `yingyongwen-source.md` + `stage3.json`）：

```json
{
  "version": 1,
  "target": "wps",
  "default_anim": "fade_on_click",
  "slides": [
    {
      "id": "phrase_opinion",
      "layout": "phrase_table",
      "title": "功能句型 · 观点表达",
      "source": "phrase_tables[0]",
      "anim": "row"
    },
    {
      "id": "vocab_design_basic",
      "layout": "vocab_table",
      "title": "话题词块 · 设计元素 · 必备",
      "source": "vocab_fields[1].tiers[0]",
      "columns": ["english", "example"],
      "anim": "row"
    }
  ]
}
```

**LLM 规则（写入 SKILL / 大纲 prompt）：**

- 只设计 **页序、layout、source 指针、columns、拆页**；禁止 slash 合并词块
- 词块必备：`columns: ["english", "example"]`（无中文）
- 词块进阶/亮点：`columns: ["english", "chinese", "example"]`
- 行数 >6 → 拆为 `… · 1/2` 两页

**Fallback：** 无 `classroom_deck.json` 时，`deck_plan_from_stage3()` 用确定性规则生成（与心理健康默认一致）。

---

## 5. Stage 3 表格版式（V1）

### 5.1 功能句型 `phrase_table`

| 列 | 宽比 | 内容 |
|----|------|------|
| 层级 | 15% | 基础句 / 进阶句 / 高级句 |
| 英文句型 | 55% | Times New Roman 26pt |
| 说明 | 30% | 基础句 **留空**；进阶/高级填中文说明（可含高分提示） |

页底可选：**本题** 1 段 + **改一句** 对比（❌/✅）— 各为独立 anim 块。

### 5.2 话题词块 `vocab_table`

| 层级 | 列 |
|------|-----|
| 必备 | 英文词块 \| 例句 |
| 进阶/亮点 | 英文 \| 中文 \| 例句 |

表头行静态（紫底白字，复用现有 `table_slide` 样式）；数据行逐行 on-click。

### 5.3 实现要点

- 复用/扩展 `SlideBuilder.table_slide()` → `phrase_table_slide()`、`vocab_table_slide()`
- **动画单位：** 每个数据行用 **独立 table 行** 或 **独立 textbox 行**（推荐后者，WPS 动画兼容性更好）
- 字号 ≥26pt；行高自适应 `word_wrap`

---

## 6. 动画（`pptx_click_reveal.py`）

### 6.1 效果

- 仅 **fade（淡入）** 或 **appear（出现）** — 实现时选 WPS 兼容更好的那种，另一种作 fallback
- Trigger：**on-click**（单击换页内下一块）
- 顺序：表头 → 行1 → 行2 → … → 本题 → 改一句前 → 改一句后

### 6.2 技术

python-pptx 无动画 API → 生成 `.pptx` 后：

1. 解压 / 用 `lxml` 访问 `slide*.xml`
2. 为每个带 `anim_order` 元数据的 shape 写入 `p:timing` / `p:seq` 节点
3. 参考 WPS 可打开的样板 PPT 提取最小 timing XML（**WPS 实测样板优先于 MSO 文档**）

### 6.3 WPS 验收

- [ ] WPS 打开无修复提示
- [ ] F5 放映：Stage3 页逐行 click 出现
- [ ] 保存后再开动画仍在
- [ ] MS PowerPoint 抽查 1–2 页（非阻塞）

### 6.4 失败兜底

- 注入异常 → 记录 warning，输出无动画 pptx，exit code 0
- CLI：`--no-anim` 跳过注入

---

## 7. 工作流变更

| 文件 | 变更 |
|------|------|
| `one_click_classroom_ppt.py` | 默认 V1 全流程；可选 `--legacy-ppt-master` |
| `generate_classroom_pptx.py` | 接 stage3.json + deck plan；Stage3 表格化 |
| `pptx_click_reveal.py` | **新增** |
| `deck_plan.py` | **新增**：`deck_plan_from_stage3()` + 读 classroom_deck.json |
| `prepare_ppt_source.py` | 已有 stage3.json |
| `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md` | V1 默认；ppt-master legacy |
| `prompts/` 或 skill | **PPT 大纲 Agent** 输出 `classroom_deck.json` 说明 |

**弃用主路径：** `build_ppt_stage3_svg.py`、`build_ppt_essay_svg.py`（范文仍可在 V1 用 `essay_slide()`，无需 SVG）。

---

## 8. 页数

详细版 **28–32 页**（与此前 A 方案一致）：  
13 前段 + 6 句型（3 表 + 3 改一句可合并或分页）+ 9 词块 + 3 尾段。

---

## 9. 验收标准

- [ ] `one_click_classroom_ppt.py export.html` 一键出 WPS 可放映 pptx
- [ ] Stage 3 全部为表格，内容与 `stage3.json` 一致
- [ ] 必备词块无中文列；基础句型说明列为空
- [ ] WPS F5 on-click 逐行出现
- [ ] pytest：deck plan、表格行数、动画 XML 存在性（不依赖 GUI）
- [ ] 无 `classroom_deck.json` 时确定性 fallback 仍可生成

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| WPS 与 MSO timing XML 差异 | 以 WPS 样板 PPT 反推 XML；验收仅在 WPS |
| 原生 table 行难单独动画 | 用对齐 textbox 模拟表格行 |
| LLM deck plan 漂移 | source 指针校验 + fallback 默认 plan |
