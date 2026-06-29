# V1 Stage3 表格 + WPS on-click Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 弃用 ppt-master V3 主路径；V1 python-pptx 从 `stage3.json` 生成 Stage3 表格页，并注入 WPS 兼容的 fade on-click 动画。

**Architecture:** `deck_plan.py` 规划页序 → `generate_classroom_pptx.py` 表格 slide + 行级 shape 元数据 → `pptx_click_reveal.py` OOXML 注入 → `one_click_classroom_ppt.py` 串联。

**Tech Stack:** Python 3.12, python-pptx, lxml, pytest；验收 **WPS 演示** F5。

**Spec:** `docs/superpowers/specs/2026-06-20-v1-stage3-table-anim-design.md`

---

## File Map

| File | 职责 |
|------|------|
| `scripts/deck_plan.py` | `deck_plan_from_stage3()` + 加载 `classroom_deck.json` |
| `scripts/pptx_click_reveal.py` | 注入 on-click fade；`--no-anim` 跳过 |
| `scripts/generate_classroom_pptx.py` | `phrase_table_slide` / `vocab_table_slide`；读 stage3 |
| `scripts/one_click_classroom_ppt.py` | 默认 V1 一键；`--legacy-ppt-master` |
| `scripts/prepare_ppt_source.py` | 已有 stage3.json（无需大改） |
| `tests/fixtures/stage3_mental_health.md` | 已有 |
| `tests/test_deck_plan.py` | deck 规划 |
| `tests/test_pptx_click_reveal.py` | timing XML 存在 |
| `tests/test_generate_classroom_stage3.py` | 表格 slide 生成 |
| `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md` | V1 默认 + classroom_deck.json 大纲说明 |
| `docs/superpowers/specs/2026-06-20-v1-stage3-table-anim-design.md` | 已写 |

---

### Task 1: Deck 规划模块

**Files:**
- Create: `scripts/deck_plan.py`
- Create: `tests/test_deck_plan.py`

- [ ] **Step 1: 失败测试**

```python
from scripts.deck_plan import deck_plan_from_stage3
from scripts.parse_stage3 import parse_stage3_file
from pathlib import Path

FIXTURE = Path("tests/fixtures/stage3_mental_health.md")

def test_deck_plan_has_phrase_and_vocab_slides():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    layouts = [s["layout"] for s in plan["slides"]]
    assert "phrase_table" in layouts
    assert "vocab_table" in layouts
    assert sum(1 for s in plan["slides"] if s["layout"] == "vocab_table") >= 9

def test_vocab_basic_columns_two_only():
    data = parse_stage3_file(FIXTURE)
    plan = deck_plan_from_stage3(data)
    basic = next(s for s in plan["slides"] if "必备" in s["title"])
    assert basic["columns"] == ["english", "example"]
```

- [ ] **Step 2: 实现 `deck_plan_from_stage3`**

- 3 × `phrase_table`（source `phrase_tables[i]`）
- 9 × `vocab_table`（3 字段 × 3 tier）
- 必备 tier → `columns: ["english", "example"]`
- 进阶/亮点 → `["english", "chinese", "example"]`

- [ ] **Step 3: `load_deck_plan(path, stage3_data)`** — JSON 覆盖或 merge

- [ ] **Step 4: pytest PASS**

---

### Task 2: V1 Stage3 表格 slides

**Files:**
- Modify: `scripts/generate_classroom_pptx.py`
- Create: `tests/test_generate_classroom_stage3.py`

- [ ] **Step 1: 在 `SlideBuilder` 新增 `phrase_table_slide()`**

```python
def phrase_table_slide(self, title: str, table: dict, *, badge: str | None = None) -> list[int]:
    """Returns shape_ids (or anim_order markers) for animation pass."""
    # headers: 层级 | 英文句型 | 说明
    # rows: 基础说明空；进阶/高级填 chinese；high_score 可拼入说明列
```

- [ ] **Step 2: 新增 `vocab_table_slide(title, tier, rows, columns)`**

- 2 列或 3 列按 `columns` 参数

- [ ] **Step 3: 改 `build_*_deck` 或新增 `build_deck_from_stage3(stage3, plan)`**

- 心理健康：读 `d:\Downloads\ppt-work\stage3.json` 或 fixture

- [ ] **Step 4: 测试 — 生成 tmp pptx，断言 table 行数**

```python
def test_phrase_table_row_count(tmp_path):
    # generate minimal deck, len(table.rows) == 4 for phrase + optional footer shapes
```

- [ ] **Step 5: 为每个可动画 shape 设置 `shape.name = f"anim_{order:03d}"`**

---

### Task 3: WPS on-click 动画注入

**Files:**
- Create: `scripts/pptx_click_reveal.py`
- Create: `tests/test_pptx_click_reveal.py`
- Create: `tests/fixtures/minimal_anim_reference.pptx`（手工在 WPS 做 1 页 2 行 click 出现，提交仓库）

- [ ] **Step 1: 从 WPS 样板提取 timing XML 片段**（文档注释在 `pptx_click_reveal.py` 顶部）

- [ ] **Step 2: `apply_click_reveal(pptx_path, *, effect="fade") -> bool`**

- 遍历 slide shapes，`name.startswith("anim_")` 排序注入

- [ ] **Step 3: 失败测试 — 注入后 slide XML 含 `p:timing`**

- [ ] **Step 4: try/except 失败返回 False，不删原文件**

- [ ] **Step 5: 人工：WPS 打开 `tmp.pptx` F5 点 2 次**（记录在 plan 验收清单）

---

### Task 4: 一键工作流

**Files:**
- Modify: `scripts/one_click_classroom_ppt.py`
- Modify: `scripts/generate_classroom_pptx.py` `main()` CLI

- [ ] **Step 1: `one_click_classroom_ppt.py` 新流程**

```powershell
python scripts/one_click_classroom_ppt.py "export.html" -o ppt-work
# → prepare_ppt_source
# → generate_classroom_pptx --stage3-json ppt-work/stage3.json --out ppt-work/exports/classroom.pptx
# → pptx_click_reveal ppt-work/exports/classroom.pptx
```

- [ ] **Step 2: `--no-anim` / `--legacy-ppt-master` 旗标**

- [ ] **Step 3: 端到端跑心理健康导出**

---

### Task 5: 大纲 LLM + 文档

**Files:**
- Modify: `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md`
- Modify: `SLIDE_BLUEPRINT.md`（V1 默认，ppt-master legacy）

- [ ] **Step 1: SKILL 写清 Agent 产出 `classroom_deck.json` 规则**

- [ ] **Step 2: 提供 `classroom_deck.schema.json` 或 SKILL 内 JSON 示例**

- [ ] **Step 3: ppt-master 步骤标为 legacy**

---

### Task 6: 验收

- [ ] `pytest tests/test_deck_plan.py tests/test_pptx_click_reveal.py tests/test_generate_classroom_stage3.py -q`
- [ ] WPS：`mental_health_classroom.pptx` Stage3 页表格 + F5 逐行
- [ ] 必备词块 2 列无中文

---

## 验收标准（整体）

- [ ] 用户「出课件」默认 V1，不触发 ppt-master
- [ ] WPS 放映 on-click 可用
- [ ] Stage3 表格完整来自 stage3.json
- [ ] 动画仅 fade/appear

## 非本计划

- 删除 ppt-master 源码
- MS Office 全版本动画 QA
- git commit（用户未要求时不提交）
