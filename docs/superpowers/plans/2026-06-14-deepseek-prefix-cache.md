# DeepSeek 前缀缓存优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重排 API messages 使稳定前缀（system + stage_prompt）在前，统一 Stage 2→3 串行，移除全部并行逻辑，提高 DeepSeek 跨题/同次流程前缀缓存命中率。

**Architecture:** `build_chat_messages` 先写 stage_prompt、再写可变 user 块、最后写固定 tail 指令；`workflow.py` 用 `sort_keys=True` 序列化 Stage1 JSON；`run_manager` 回归单线程单 stage API 调度，删除 `parallel_*` 状态机。应用层 `llm_cache` 不变。

**Tech Stack:** Python 3.12, Streamlit, OpenAI-compatible API (DeepSeek), pytest

**Spec:** `docs/superpowers/specs/2026-06-14-deepseek-prefix-cache-design.md`

---

## File Map

| File | 变更 |
|------|------|
| `utils/llm_messages.py` | 重排 messages；新增 `format_stage1_json` |
| `workflow.py` | user_parts / tail 拆分；JSON 稳定化；`run_full_pipeline` 串行 S2→S3 |
| `utils/stage4_input.py` | `json.dumps(..., sort_keys=True)` |
| `ui/run_cache.py` | 删除并行辅助函数 |
| `ui/run_manager.py` | 删除 `_start_parallel_23_thread` 及 parallel job 字段/分支 |
| `tests/test_llm_messages.py` | 断言 stage_prompt 在可变内容之前 |
| `tests/test_run_visibility.py` | 删除并行测试；保留单 stage running 测试 |
| `tests/test_workflow_serial.py` | 新建：`run_full_pipeline` 调用顺序（mock） |
| `docs/LLM_CACHE.md` | 删并行章节；更新 messages 结构 |
| `docs/USAGE.md`, `README.md`, `docs/COMMERCIAL_EDITION.md`, `docs/PROJECT_OVERVIEW.md` | 删并行表述 |
| `ui/new_page.py` | 删「Stage 2/3 并行」caption |

---

### Task 1: 缓存友好 messages 重排

**Files:**
- Modify: `utils/llm_messages.py`
- Test: `tests/test_llm_messages.py`

- [ ] **Step 1: 写失败测试 — stage_prompt 位于第一个 user 消息**

在 `tests/test_llm_messages.py` 追加：

```python
def test_build_chat_messages_stage_prompt_before_variable_parts(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "1")
    msgs = build_chat_messages(
        system_base="SYS",
        stage_prompt="STAGE_PROMPT",
        user_parts=["VAR_A", "VAR_B"],
        tail_instruction="TAIL",
    )
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert msgs[1]["role"] == "user"
    assert "STAGE_PROMPT" in msgs[1]["content"]
    assert "VAR_A" not in msgs[1]["content"]
    assert msgs[2]["content"] == "VAR_A"
    assert msgs[3]["content"] == "VAR_B"
    assert msgs[4]["content"] == "TAIL"


def test_format_stage1_json_sort_keys():
    from utils.llm_messages import format_stage1_json

    a = format_stage1_json({"z": 1, "a": 2})
    b = format_stage1_json({"a": 2, "z": 1})
    assert a == b
    assert '"a"' in a and a.index('"a"') < a.index('"z"')
```

- [ ] **Step 2: 运行测试确认 FAIL**

Run: `python -m pytest tests/test_llm_messages.py::test_build_chat_messages_stage_prompt_before_variable_parts tests/test_llm_messages.py::test_format_stage1_json_sort_keys -v`

Expected: FAIL（`tail_instruction` / `format_stage1_json` 不存在，或 message 顺序不对）

- [ ] **Step 3: 实现 `utils/llm_messages.py`**

1. 新增：

```python
import json
from typing import Any

def format_stage1_json(stage1_json: dict[str, Any]) -> str:
    return json.dumps(stage1_json, ensure_ascii=False, indent=2, sort_keys=True)
```

2. 更新 `build_chat_messages` 签名与 docstring：

```python
def build_chat_messages(
    *,
    system_base: str,
    stage_prompt: str,
    user_parts: list[str],
    tail_instruction: str = "",
) -> list[dict[str, Any]]:
    """
    缓存友好顺序（ENABLE_PROMPT_CACHE_LAYOUT=1）：
    system → user(stage_prompt) → user(可变…) → user(tail)
    """
```

3. 缓存布局分支改为：

```python
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_base}]
    if stage_prompt.strip():
        messages.append(
            {
                "role": "user",
                "content": f"【本阶段任务说明】\n\n{stage_prompt.strip()}",
            }
        )
    for part in user_parts:
        if part.strip():
            messages.append({"role": "user", "content": part.strip()})
    if tail_instruction.strip():
        messages.append({"role": "user", "content": tail_instruction.strip()})
    return messages
```

4. legacy 分支（`ENABLE_PROMPT_CACHE_LAYOUT=0`）保持不变：合并 system+stage_prompt，单 user 含全部 parts + tail。

- [ ] **Step 4: 运行测试确认 PASS**

Run: `python -m pytest tests/test_llm_messages.py -v`

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add utils/llm_messages.py tests/test_llm_messages.py
git commit -m "refactor: put stage prompt before variable user parts for prefix cache"
```

---

### Task 2: workflow 各 Stage 调用与 JSON 稳定化

**Files:**
- Modify: `workflow.py`, `utils/stage4_input.py`

- [ ] **Step 1: 更新 imports**

```python
from utils.llm_messages import (
    build_chat_messages,
    format_stage1_json,
    shared_question_context,
)
```

- [ ] **Step 2: 改写 `run_stage1` … `run_stage4` 的 `build_chat_messages` 调用**

**Stage 1** — 可变区仅原题，tail 固定：

```python
messages = build_chat_messages(
    system_base=self._system,
    stage_prompt=stage_prompt,
    user_parts=[f"【应用文原题】\n\n{question.strip()}"],
    tail_instruction=(
        "请按 stage1 任务说明输出 STRUCTURED_JSON 与 HUMAN_READABLE_SUMMARY。"
        "JSON 从简（短句/短语）；PART B 六节必须写全，§6 须完整输出至「结尾段」。"
    ),
)
```

**Stage 2 / 3** — 用 `format_stage1_json` 替代 `json.dumps`：

```python
json_text = format_stage1_json(stage1_json)
messages = build_chat_messages(
    system_base=self._system,
    stage_prompt=stage_prompt,
    user_parts=[shared_question_context(question, json_text)],
    tail_instruction="请按 stage2 任务说明完成 PEEL 写作策略卡与多版范文（不含句型包与词汇锦囊）。",
)
# stage3 tail: "请按 stage3 任务说明输出功能句型包与话题词汇锦囊。"
```

**Stage 4** — stage_prompt 已含 `[student_level]` 替换；可变区保持水平 + JSON + S2/S3 节选：

```python
messages = build_chat_messages(
    system_base=self._system,
    stage_prompt=stage_prompt,
    user_parts=[
        f"当前学生水平：{level}",
        f"student_level：{level}",
        f"【Stage1 JSON】\n\n```json\n{json_block}\n```",
        f"【Stage2 输出（PEEL 与范文）】\n\n{s2}",
        f"【Stage3 输出（句型与词汇）】\n\n{s3}",
    ],
    tail_instruction="请按 stage4 任务说明输出教学指南与易错预警。",
)
```

- [ ] **Step 3: `utils/stage4_input.py` 中 `json.dumps` 加 `sort_keys=True`**

```python
json_block = json.dumps(stage1_json, ensure_ascii=False, indent=2, sort_keys=True)
```

- [ ] **Step 4: 串行化 `run_full_pipeline`**

删除 `ThreadPoolExecutor` 导入与并行块，改为：

```python
try:
    state.stage2 = self.run_stage2(question, state.stage1.structured_json)
    state.stage3 = self.run_stage3(question, state.stage1.structured_json)
except Exception as e:
    state.errors.append(f"Stage2/3 失败: {e}")
    return state
```

- [ ] **Step 5: 运行相关测试**

Run: `python -m pytest tests/test_llm_messages.py tests/test_stage_max_tokens.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add workflow.py utils/stage4_input.py
git commit -m "refactor: stable JSON and serial Stage 2 then 3 in workflow"
```

---

### Task 3: 移除 run_cache 并行辅助

**Files:**
- Modify: `ui/run_cache.py`
- Grep: 确认无残留引用

- [ ] **Step 1: 删除以下函数及仅被其使用的 import**

- `should_parallel_stage23`
- `try_load_parallel_cache`

- [ ] **Step 2: 更新模块 docstring**

```python
"""运行期 LLM 结果缓存辅助。"""
```

- [ ] **Step 3: 全库 grep 确认无引用**

Run: `rg "should_parallel_stage23|try_load_parallel_cache" --glob "*.py"`

Expected: 无匹配（Task 4 完成前可能仍有 run_manager 引用，Task 4 后再跑一次）

- [ ] **Step 4: Commit**（可与 Task 4 合并为一次 commit，若同会话连续做）

---

### Task 4: 简化 run_manager（删除并行状态机）

**Files:**
- Modify: `ui/run_manager.py`
- Test: `tests/test_run_visibility.py`

- [ ] **Step 1: 更新测试文件**

删除 `test_running_stages_parallel_23` 及对 `should_parallel_stage23` 的 import。

保留并确认 `test_running_stages_single_stage2` 仍 PASS。

可选新增：

```python
def test_running_stages_only_one_at_a_time():
    state = WorkflowState()
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="ok")
    job = {
        "phase": "api",
        "thread": _AliveThread(),
        "mode": "full",
        "stages": [1, 2, 3, 4],
        "stage_index": 2,  # stages[2] == 3
    }
    assert _running_stages_for_job(job, state) == {3}
```

- [ ] **Step 2: 简化 `_running_stages_for_job`**

删除 `should_parallel_stage23` 分支，仅保留：

```python
idx = job["stage_index"]
stages = job.get("stages") or []
if idx < len(stages):
    return {stages[idx]}
return set()
```

- [ ] **Step 3: 删除整函数 `_start_parallel_23_thread`（约 L532–613）**

- [ ] **Step 4: 简化 `_begin_cached_or_api`**

删除 `should_parallel_stage23` / `try_load_parallel_cache` 整块；仅保留单 stage 的 `try_load_cached_stage` 路径。

- [ ] **Step 5: 简化 `advance_run_job`**

1. 删除 `if should_parallel_stage23(job): _start_parallel_23_thread(...)` 分支，统一走 `_start_api_thread`。
2. 删除线程结束处理中的：
   - `parallel_partial` / `_parallel_failed_stage`
   - `parallel_mode` + `parallel_results` 成功 flush 分支（L1062–1077 一带）
3. 错误处理中 `failed_stage` 改回 `stage_num`（或 job 当前 stage）。

- [ ] **Step 6: 清理 job 初始化字段**

在 `try_start_run_job`（或创建 job dict 处）删除：

```python
"parallel_mode": False,
"parallel_results": None,
```

以及 `_start_api_thread` 内对 `parallel_mode` / `parallel_results` 的清零。

- [ ] **Step 7: 更新 imports**

从 `ui/run_cache` 仅 import `merge_job_usage`, `save_stage_cache`, `try_load_cached_stage`（按实际使用）。

- [ ] **Step 8: 运行测试**

Run: `python -m pytest tests/test_run_visibility.py -v`

Expected: PASS

- [ ] **Step 9: 全库 grep**

Run: `rg "parallel_23|should_parallel|parallel_mode|parallel_results|_start_parallel" --glob "*.py"`

Expected: 无匹配（tests 除外若已删）

- [ ] **Step 10: Commit**

```bash
git add ui/run_manager.py ui/run_cache.py tests/test_run_visibility.py
git commit -m "refactor: remove parallel Stage 2/3 execution path"
```

---

### Task 5: workflow 串行 pipeline 测试（mock）

**Files:**
- Create: `tests/test_workflow_serial.py`

- [ ] **Step 1: 写 mock 测试**

```python
"""workflow.run_full_pipeline Stage 2→3 串行顺序。"""

from unittest.mock import MagicMock

from workflow import GaokaoWritingWorkflow, Stage1Result, Stage2Result, Stage3Result, Stage4Result


def test_run_full_pipeline_runs_stage2_before_stage3(monkeypatch):
    order: list[str] = []

    wf = GaokaoWritingWorkflow(client=MagicMock())
    s1 = Stage1Result(raw="", structured_json={"k": 1}, human_summary="ok")
    monkeypatch.setattr(wf, "run_stage1", lambda q: order.append("s1") or s1)
    monkeypatch.setattr(
        wf,
        "run_stage2",
        lambda q, j: order.append("s2") or Stage2Result(raw="s2"),
    )
    monkeypatch.setattr(
        wf,
        "run_stage3",
        lambda q, j: order.append("s3") or Stage3Result(raw="s3"),
    )
    monkeypatch.setattr(
        wf,
        "run_stage4",
        lambda *a, **k: order.append("s4") or Stage4Result(raw="s4"),
    )

    wf.run_full_pipeline("题目", student_level="中等")
    assert order == ["s1", "s2", "s3", "s4"]
```

- [ ] **Step 2: 运行**

Run: `python -m pytest tests/test_workflow_serial.py -v`

Expected: PASS（Task 2 完成后）

- [ ] **Step 3: Commit**

```bash
git add tests/test_workflow_serial.py
git commit -m "test: assert full pipeline runs Stage 2 before Stage 3"
```

---

### Task 6: 文档与 UI 文案

**Files:**
- Modify: `docs/LLM_CACHE.md`, `docs/USAGE.md`, `README.md`, `docs/COMMERCIAL_EDITION.md`, `docs/PROJECT_OVERVIEW.md`, `ui/new_page.py`

- [ ] **Step 1: `docs/LLM_CACHE.md`**

- 删除「## 3. Stage2 / Stage3 并行」整节；后续章节编号顺延
- §2 更新 messages 结构为：system → stage_prompt → 可变 user → tail
- 验证清单删除「对比并行前后总耗时」；删除「侧边栏显示缓存命中」一句
- 新增说明：Stage 2 完成后才发起 Stage 3，利于 DeepSeek 前缀链式命中

- [ ] **Step 2: 其它文档**

| 文件 | 改什么 |
|------|--------|
| `docs/USAGE.md` L12 | 删「Stage 2 与 Stage 3 自动并行」→ 改为「Stage 2 完成后运行 Stage 3」 |
| `README.md` L68 | 删「Stage 2/3 全流程并行」 |
| `docs/COMMERCIAL_EDITION.md` L201 | 删「并行 Stage2/3」 |
| `docs/PROJECT_OVERVIEW.md` L15 | 删「Stage2/3 并行」 |

- [ ] **Step 3: `ui/new_page.py`**

删除或替换 caption（约 L588）：

```python
# 删除：
"完整流程时 Stage 2 与 Stage 3 将并行生成，可缩短等待时间。"
# 可选替换（YAGNI：也可整句删除）：
"完整流程按 Stage 1→2→3→4 顺序生成；同题重复可走 LLM 结果缓存。"
```

- [ ] **Step 4: 更新 spec 状态**

`docs/superpowers/specs/2026-06-14-deepseek-prefix-cache-design.md` 首行状态改为「已实现」。

- [ ] **Step 5: Commit**

```bash
git add docs/LLM_CACHE.md docs/USAGE.md README.md docs/COMMERCIAL_EDITION.md docs/PROJECT_OVERVIEW.md ui/new_page.py docs/superpowers/specs/2026-06-14-deepseek-prefix-cache-design.md
git commit -m "docs: serial Stage 2/3 and cache-friendly message layout"
```

---

### Task 7: 全量验证与收尾

- [ ] **Step 1: 全量 pytest**

Run: `python -m pytest -q`

Expected: 全绿

- [ ] **Step 2: grep 无并行残留**

Run: `rg "并行运行 Stage|should_parallel|parallel_mode|_start_parallel" --glob "*.{py,md}"`

Expected: 无匹配（或仅历史 plan/spec 归档可接受）

- [ ] **Step 3: 手动 smoke（可选，有 API Key 时）**

1. 同一模型连跑 2 道不同题的 Stage 1
2. 历史详情对比第 2 题 `cached_tokens` 是否高于第 1 题

- [ ] **Step 4: Commit（若有遗漏）并 push**

---

## Spec Coverage Checklist

| Spec 要求 | Task |
|-----------|------|
| messages 重排 | Task 1, 2 |
| JSON sort_keys | Task 1, 2 |
| 串行 S2→S3 | Task 2, 4 |
| 删除并行路径 | Task 3, 4 |
| 不增侧边栏命中率 UI | （无 task） |
| 历史 cached_tokens 保留 | 无代码变更 |
| 文档更新 | Task 6 |
| pytest 全绿 | Task 7 |

## 风险提醒

实现完成后若 Stage 输出质量下降，用 1 道真题对比改版前后四阶段再决定是否微调 tail 文案（不回退 messages 顺序）。
