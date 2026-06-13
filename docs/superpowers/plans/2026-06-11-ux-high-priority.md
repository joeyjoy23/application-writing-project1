# 高优先级 UX 六项 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复收藏筛选 bug，统一清空确认，优化历史/导出/完整流程文案，提升教师日常使用清晰度。

**Architecture:** 最小 diff：DB 层补 `starred_only` 透传；UI 层集中改 `new_page.py`、`sidebar.py`、`history.py`；新增纯函数测试，不引入 Streamlit 集成测试。

**Tech Stack:** Python, Streamlit, SQLite/Postgres db layer, pytest

---

## File Map

| File | 变更 |
|------|------|
| `db/sqlite_backend.py` | `count_records` 增加 `starred_only` |
| `db/__init__.py` | `get_all_records` / `count_records` 透传 `starred_only` |
| `ui/new_page.py` | 历史列表 DB 筛选；按钮文案；导出 warning；完整流程 caption/help |
| `ui/sidebar.py` | `request_clear_checkpoint()`；侧边栏清空改请求确认 |
| `ui/history.py` | `history_resume_hint` 文案 |
| `tests/test_db_history.py` | 新建：starred count/filter |
| `tests/test_history_ux.py` | 新建：resume hint |

---

### Task 1: DB starred_only 透传

**Files:**
- Modify: `db/sqlite_backend.py`, `db/__init__.py`
- Test: `tests/test_db_history.py`

- [ ] **Step 1:** `sqlite_backend.count_records` 增加 `starred_only: bool = False`，SQL 加 `AND is_starred = 1`
- [ ] **Step 2:** `db/__init__.py` 的 `get_all_records(..., starred_only=False)` 与 `count_records(..., starred_only=False)` 传给 backend
- [ ] **Step 3:** 写测试：插入 2 条记录，star 一条，`count_records(starred_only=True)==1`
- [ ] **Step 4:** `pytest tests/test_db_history.py -v`

---

### Task 2: 历史列表使用 DB 筛选

**Files:**
- Modify: `ui/new_page.py` (`render_history_list`)

- [ ] **Step 1:** `total = count_records(..., starred_only=starred_only)`
- [ ] **Step 2:** `get_all_records(..., starred_only=starred_only)`，删除前端 `if starred_only: records = [...]` 分支
- [ ] **Step 3:** 无记录且 `starred_only` 时 info「当前筛选条件下无收藏记录」

---

### Task 3: 统一清空确认

**Files:**
- Modify: `ui/sidebar.py`, `ui/new_page.py`

- [ ] **Step 1:** 在 `sidebar.py` 增加 `request_clear_checkpoint()` 设置 `_confirm_clear=True`，非新建则 `app_mode="新建"`
- [ ] **Step 2:** 侧边栏按钮 onclick 改为 `request_clear_checkpoint()` + `st.rerun()`

---

### Task 4: 查看/载入文案 + 载入 hint

**Files:**
- Modify: `ui/new_page.py`, `ui/history.py`

- [ ] **Step 1:** 列表按钮改为「只读查看」「载入编辑」+ help
- [ ] **Step 2:** 改写 `history_resume_hint` 与详情 caption

---

### Task 5: 导出未完成提醒

**Files:**
- Modify: `ui/new_page.py` (`render_export_buttons`)

- [ ] **Step 1:** 导入 `stage_has_content`，计算 `done/4`，`done < 4` 时 `st.warning`

---

### Task 6: 完整流程 help + 并行 caption

**Files:**
- Modify: `ui/new_page.py`

- [ ] **Step 1:** 更新 `btn_full` help 文案
- [ ] **Step 2:** 运行方式区末尾加 caption 说明 Stage 2/3 并行

---

### Task 7: 验证

- [ ] **Step 1:** `pytest` 全量
- [ ] **Step 2:** 更新 `UI_BUILD_TAG` 为 `2026.06.11-ux-high6`
