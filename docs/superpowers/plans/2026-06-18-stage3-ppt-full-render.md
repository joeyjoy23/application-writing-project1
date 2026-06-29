# Stage 3 完整上屏 PPT 渲染 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 Joyverse Stage 3 导出解析完整表格，用确定性 SVG 脚本上屏（28–32 页），基础档仅英文+例句；ppt-master Executor 不再生成句型词块页。

**Architecture:** `parse_stage3.py` 产出 `stage3.json` → `stage3_svg_layout.py` 渲染 phrase/vocab 模板 → `build_ppt_stage3_svg.py` 写 `svg_output/`；与 `build_ppt_essay_svg.py` 并列；Executor 仅 A/B/E。

**Tech Stack:** Python 3.12、pytest、ppt-master（finalize_svg / svg_to_pptx）

**Spec:** `docs/superpowers/specs/2026-06-18-stage3-ppt-full-render-design.md`

---

## File Map

| File | 职责 |
|------|------|
| `scripts/parse_stage3.py` | Stage 3 Markdown → `stage3.json` |
| `scripts/stage3_svg_layout.py` | phrase-tier / vocab-table SVG 模板 |
| `scripts/build_ppt_stage3_svg.py` | 拆页、写 SVG、CLI |
| `scripts/prepare_ppt_source.py` | 增加 `--json` 或默认写 `stage3.json` |
| `tests/fixtures/stage3_mental_health.md` | 心理健康 Stage 3 完整 fixture |
| `tests/test_parse_stage3.py` | 解析器测试 |
| `tests/test_build_ppt_stage3_svg.py` | 布局/拆页/基础档列数 |
| `scripts/build_ppt_vocab_svg.py` | DEPRECATED，指向新脚本 |
| `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md` | Step 4.6、页数 28–32 |
| `.cursor/skills/yingyongwen-export-to-ppt/SLIDE_BLUEPRINT.md` | 页型 D 细则、大纲 source 指针 |

---

### Task 1: Stage 3 解析器

**Files:**
- Create: `scripts/parse_stage3.py`
- Create: `tests/fixtures/stage3_mental_health.md`
- Create: `tests/test_parse_stage3.py`

从 `d:\Downloads\ppt-work\yingyongwen-source.md` 复制 Stage 3 段（L276 起）到 fixture。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_parse_stage3.py
from pathlib import Path
from scripts.parse_stage3 import parse_stage3_markdown

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"

def test_phrase_tables_count():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    assert len(data["phrase_tables"]) == 3
    assert data["phrase_tables"][0]["name"] == "观点表达"

def test_vocab_basic_tier_has_chinese_in_json_but_display_policy_is_layout():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    field = next(f for f in data["vocab_fields"] if "设计元素" in f["name"])
    basic = next(t for t in field["tiers"] if t["level"] == "必备级")
    assert len(basic["rows"]) >= 3
    assert basic["rows"][0]["english"]
    assert basic["rows"][0]["example"]

def test_phrase_fix_sentence_parsed():
    data = parse_stage3_markdown(FIXTURE.read_text(encoding="utf-8"))
    t0 = data["phrase_tables"][0]
    assert "❌" in t0["fix_bad"] or "good" in t0["fix_bad"].lower()
    assert t0["fix_good"].startswith("→") or "→" in t0["fix_good"]
```

- [ ] **Step 2: 运行确认 FAIL**

```powershell
Set-Location "d:\桌面\应用文project"
python -m pytest tests/test_parse_stage3.py -v
```

Expected: `ModuleNotFoundError` or assertion fail

- [ ] **Step 3: 实现 `parse_stage3.py`**

核心逻辑：

1. 用 `一、功能句型包` / `二、话题词汇锦囊` 分段  
2. 句型：按 `表格 N：` 或 `表格 1：` 切块；表头行含 `层级|英文句型` 或 tab 分列  
3. 词块：按 `语义场 N：` 切块；`必备级|进阶级|亮点级` 子块；行含 english/chinese/example  
4. 提取 `本题：`、`改一句` 块（bad/good 两行）  
5. `parse_stage3_file(path) -> dict`；`write_stage3_json(data, path)`

- [ ] **Step 4: pytest PASS**

```powershell
python -m pytest tests/test_parse_stage3.py -v
```

---

### Task 2: SVG 布局模块

**Files:**
- Create: `scripts/stage3_svg_layout.py`
- Create: `tests/test_build_ppt_stage3_svg.py`（部分）

- [ ] **Step 1: 写失败测试 — 必备词块 2 列**

```python
from scripts.stage3_svg_layout import render_vocab_table_svg

def test_basic_vocab_two_columns_only():
    svg = render_vocab_table_svg(
        title="话题词块 · 设计元素 · 必备",
        tier="必备级",
        rows=[{"english": "cracked heart", "chinese": "裂痕之心", "example": "The cracked heart stands out."}],
    )
    assert "cracked heart" in svg
    assert "The cracked heart" in svg
    assert "裂痕" not in svg  # 基础档不上屏中文
    assert "中文释义" not in svg
```

- [ ] **Step 2: 写失败测试 — 句型基础档仅英文**

```python
from scripts.stage3_svg_layout import render_phrase_tier_svg

def test_basic_phrase_english_only():
    svg = render_phrase_tier_svg(
        title="功能句型 · 观点表达",
        table={
            "name": "观点表达",
            "tiers": [
                {"level": "基础句", "english": "I prefer Poster 1.", "chinese": "用途：…", "high_score": None},
                {"level": "进阶句", "english": "I'm leaning towards Poster 1.", "chinese": "用途：委婉", "high_score": None},
                {"level": "高级句", "english": "Among the two...", "chinese": "用途：对比", "high_score": "strikes me as"},
            ],
            "topic_note": "本题：明确表达选择",
            "fix_bad": "I think Poster 1 is good. ❌",
            "fix_good": "→ Personally, I'm leaning towards Poster 1. ✅",
        },
    )
    assert "I prefer Poster 1." in svg
    # 基础句区块不应含「用途」
    assert svg.index("I prefer Poster 1.") < svg.index("用途：委婉")
    assert "用途：…" not in svg.split("进阶")[0] if "进阶" in svg else True
```

- [ ] **Step 3: 实现 `stage3_svg_layout.py`**

常量（与 essay 脚本对齐）：

```python
FONT_TITLE = 51
FONT_BODY = 32
FONT_CN = 28
HEADER_H = 76
X0 = 48
Y0 = 120
ROW_H = 44
Y_MAX = 680
MAX_ROWS_PER_PAGE = 6
```

函数：

- `render_header(title: str) -> str`
- `render_phrase_tier_svg(title, table) -> str`
- `render_vocab_table_svg(title, tier, rows, *, show_chinese: bool) -> str`
- `split_rows(rows, max_rows=6) -> list[list]` 供拆页

必备级调用 `show_chinese=False` → 2 列表头 `英文词块 | 例句`

- [ ] **Step 4: pytest PASS**

```powershell
python -m pytest tests/test_build_ppt_stage3_svg.py -v
```

---

### Task 3: Stage 3 SVG 构建器与拆页

**Files:**
- Create: `scripts/build_ppt_stage3_svg.py`
- Modify: `tests/test_build_ppt_stage3_svg.py`

- [ ] **Step 1: 写失败测试 — 输出文件数**

```python
from pathlib import Path
from scripts.build_ppt_stage3_svg import build_stage3_slide_specs, write_stage3_svgs

def test_slide_spec_count_for_mental_health(tmp_path):
    json_path = Path("tests/fixtures/stage3_mental_health.json")  # Task 3 生成
    specs = build_stage3_slide_specs(json_path)
    assert len(specs) >= 12  # 3 phrase + 9 vocab minimum
    assert any("必备" in s["title"] for s in specs)
```

- [ ] **Step 2: 实现 `build_stage3_slide_specs`**

```python
def build_stage3_slide_specs(stage3_json: Path) -> list[dict]:
    data = json.loads(stage3_json.read_text(encoding="utf-8"))
    specs = []
    for i, table in enumerate(data["phrase_tables"]):
        specs.append({"filename": f"14_phrases_{i}.svg", "title": f"功能句型 · {table['name']}", "kind": "phrase", "table": table})
    for fi, field in enumerate(data["vocab_fields"]):
        for ti, tier in enumerate(field["tiers"]):
            chunks = split_rows(tier["rows"], MAX_ROWS_PER_PAGE)
            for ci, chunk in enumerate(chunks):
                suffix = f" · {tier['level']}" + (f" {ci+1}/{len(chunks)}" if len(chunks) > 1 else "")
                specs.append({
                    "filename": f"{17+fi*3+ti:02d}_vocab_{fi}_{ti}.svg",  # 或稳定 slug
                    "title": f"话题词块 · {field['name']}{suffix}",
                    "kind": "vocab",
                    "tier": tier["level"],
                    "rows": chunk,
                })
    return specs
```

**文件名策略：** 心理健康 V3 项目已有 `14_phrases_opinion.svg` … `19_vocab_theme.svg`。构建器应支持 `manifest.json` 映射到现有 14–19+ 文件名，或扩展为 `14–28` 新序列并在 outline 同步。**推荐：** 首次实现用 `stage3_manifest.json` 列出 `{filename, title, ...}`，心理健康样例目标 28+ slides。

- [ ] **Step 3: CLI**

```powershell
python scripts/build_ppt_stage3_svg.py --project "C:\Users\Joey\tools\ppt-master\projects\yingyongwen-mental-health-v3_ppt169_20260620" --stage3-json "d:\Downloads\ppt-work\stage3.json"
```

- [ ] **Step 4: 集成测试 — 无 y 溢出**

```python
def test_no_text_below_ymax(tmp_path):
    written = write_stage3_svgs(tmp_path, FIXTURE_JSON)
    for p in written:
        svg = p.read_text(encoding="utf-8")
        for m in re.finditer(r'y="(\d+)"', svg):
            assert int(m.group(1)) <= 680
```

---

### Task 4: prepare_ppt_source 集成

**Files:**
- Modify: `scripts/prepare_ppt_source.py`

- [ ] **Step 1: 导出时写 stage3.json**

在 `main()` 成功提取 `stage3` 文本后：

```python
from scripts.parse_stage3 import parse_stage3_markdown, write_stage3_json

if data.get("stage3"):
    s3 = parse_stage3_markdown(data["stage3"])
    write_stage3_json(s3, out_dir / "stage3.json")
```

- [ ] **Step 2: 测试**

```powershell
python scripts/prepare_ppt_source.py "d:\Downloads\ppt-work\yingyongwen-source.md" -o "d:\Downloads\ppt-work"
# 或真实 HTML 导出路径
Test-Path "d:\Downloads\ppt-work\stage3.json"
```

---

### Task 5: 文档与工作流

**Files:**
- Modify: `.cursor/skills/yingyongwen-export-to-ppt/SKILL.md`
- Modify: `.cursor/skills/yingyongwen-export-to-ppt/SLIDE_BLUEPRINT.md`
- Modify: `scripts/build_ppt_vocab_svg.py`（DEPRECATED 头）

- [ ] **Step 1: SKILL.md 增加 Step 4.6**

```
- [ ] 4.6 python scripts/build_ppt_stage3_svg.py --project <proj> --stage3-json <path>
```

- [ ] **Step 2: SLIDE_BLUEPRINT 页型 D**

- 默认体量 28–32 页  
- 基础档：词块 2 列、句型仅英文  
- 大纲 `source: stage3.json#...`  
- 禁止 Executor 手排 14–N 句型词块段  

- [ ] **Step 3: build_ppt_vocab_svg.py 顶部注释 DEPRECATED**

---

### Task 6: 心理健康 V3 端到端样例

**Files:**
- ppt-master project svg_output 14+  
- Output: `d:\Downloads\ppt-work\mental_health_classroom_V3_stage3.pptx`

- [ ] **Step 1:** `prepare_ppt_source` → `stage3.json`  
- [ ] **Step 2:** 更新 `yingyongwen-outline.md` slide 14–N（source 指针，无 slash 摘要）  
- [ ] **Step 3:** `build_ppt_stage3_svg.py` + `build_ppt_essay_svg.py`  
- [ ] **Step 4:** Executor 仅重生非 Stage3 页（或保留已有 01–13、20–22）  
- [ ] **Step 5:** finalize → svg_to_pptx  
- [ ] **Step 6:** 人工抽查 slide 18 必备 2 列、进阶 3 列、句型基础无中文  

---

### Task 7: 全量 pytest

- [ ] **Step 1:**

```powershell
Set-Location "d:\桌面\应用文project"
python -m pytest tests/test_parse_stage3.py tests/test_build_ppt_stage3_svg.py tests/test_build_ppt_essay_svg.py tests/test_essay_format.py -q
```

Expected: all pass

---

## 验收标准（整体）

- [ ] Stage 3 内容 100% 来自导出 JSON，Executor 未改写句型词块正文  
- [ ] 基础档词块：2 列（英文+例句），无中文释义  
- [ ] 基础档句型：仅英文一行  
- [ ] 进阶/亮点完整三列或句型含中文说明  
- [ ] 心理健康 deck ≥28 页  
- [ ] SKILL / SLIDE_BLUEPRINT 已更新  

---

## 非本计划范围

- 脚本化全部审题/Stage4 页（仍 Executor）  
- 修改 Stage 3 LLM prompt  
- git commit（用户未要求时不提交）  

---

## Spec 覆盖自检

| Spec § | Task |
|--------|------|
| stage3.json 模型 | Task 1 |
| phrase-tier 基础无中文 | Task 2 |
| vocab 必备 2 列 | Task 2 |
| 拆页 >6 行 | Task 3 |
| prepare 集成 | Task 4 |
| ppt-master 边界 | Task 5 |
| 28–32 页样例 | Task 6 |
