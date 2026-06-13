# 高优先级 UX 六项 — 设计说明

**日期：** 2026-06-11  
**范围：** 教师日常使用路径中的 6 项高优先级优化（不含中低优先级项）

## 背景

上一轮 UX 审查发现：收藏筛选有 bug、清空入口不一致、历史载入文案误导、导出缺提醒、完整流程说明不准确。六项均属文案或小范围 UI/DB 接线，不改变工作流核心逻辑。

## 需求与方案

### 1. 修复「只看收藏」+ 分页

**问题：** `new_page.py` 在前端对当前页做 star 过滤，`count_records` 未传 `starred_only`，导致总数与分页错误。

**方案：** 后端已支持 `starred_only`（SQLite `get_all_records`、Postgres 两者均有；SQLite `count_records` 需补参数）。在 `db/__init__.py` 的 `get_all_records` / `count_records` 增加 `starred_only` 并纳入 cache 键；历史列表统一走 DB 筛选，删除前端 filter。

**验收：** 勾选「只看收藏」时 total、分页与列表一致；无收藏时显示 info 而非错误页码。

### 2. 统一「清空」确认

**问题：** 主区「清空结果」有二次确认，侧边栏「清空当前结果」一点即清。

**方案：** 侧边栏按钮改为 `request_clear_checkpoint()`：设置 `_confirm_clear=True`；若当前非「新建」模式则切到「新建」。确认 UI 仍只用 `new_page.py` 现有 confirm 框，确认后调用 `clear_checkpoint()`。

**验收：** 两处入口均须确认后才清空；历史记录不受影响。

### 3. 明确「查看」vs「载入」

**方案：**

| 位置 | 原文案 | 新文案 |
|------|--------|--------|
| 历史列表 | 查看 | 只读查看 |
| 历史列表 | 载入 | 载入编辑 |
| 详情页 | 载入继续编辑 / 载入到新建页 | 保持不变（已够清晰） |

按钮 `help` 补充一句用途说明。

### 4. 修正载入后提示

**问题：** `history_resume_hint` 与详情 caption 仍写「切换到新建」，但 `load_history_into_session` 已自动切换。

**方案：** 改写 `history_resume_hint` 与 `render_history_detail` 中 caption，指向「继续生成」按钮，不再提手动切换模式。

### 5. 未完成阶段导出提醒

**方案：** 在 `render_export_buttons` 内，若已完成阶段 &lt; 4，在「导出报告」标题下显示 `st.warning`，说明 Word/JSON 可能不完整。

### 6. 完整流程说明 + Stage 2/3 并行提示

**方案：**

- 「完整流程」按钮 `help` 拆为两句：同模型跳过已完成；换模型全部重跑。
- 「运行方式」区块下增加一行 caption：完整流程时 Stage 2 与 3 并行。

## 不在本次范围

- 学生水平变更提示、Stage 中文按钮名、运行日志隐藏、JSON 文件名等中低优先级项。

## 测试

- `tests/test_db_history.py`：`count_records(starred_only=True)`（SQLite 内存库）
- `tests/test_history_ux.py`：`history_resume_hint` 文案；导出完成度 helper（若抽取）

## 文档

- 实施后可选更新 `docs/USAGE.md` 中「只看收藏」与清空说明（若行为有变仅第 2 项）。
