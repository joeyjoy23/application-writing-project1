# DeepSeek 前缀缓存优化 — 设计说明

**日期：** 2026-06-14  
**状态：** 已确认，待实现  
**范围：** messages 结构、Stage 2→3 串行、并行逻辑移除

## 背景与目标

用户希望同时优化两类场景：

| 场景 | 目标 |
|------|------|
| **B** | 不同题目批量备课时，跨题共享「教研规则 + 阶段任务说明」等稳定前缀 |
| **C** | 单次全流程也尽量降低 DeepSeek API 输入成本 |

当前观测：一次 DeepSeek V4 Pro 全流程 `cached_tokens` 仅约 384 / 17,761 输入（~2%）。首跑偏低属正常；但现有 messages 顺序与 Stage 2/3 并行进一步压制了前缀命中空间。

**本方案不替代**应用层 `llm_cache`（同题同模型跳过 API）。本方案优化的是**仍须调用 API** 时的 DeepSeek Context Caching。

## 用户确认（2026-06-14）

- 采用 **方案 A**（缓存友好 messages + Stage 2→3 串行）
- **不做**侧边栏「缓存命中 / 未命中 / 命中率」展示
- **不保留** Stage 2/3 并行「极速模式」，统一串行

## DeepSeek 机制摘要（实现约束）

- 默认开启，无需额外 API 参数
- 命中要求：从第 0 token 起**字节级一致**的前缀
- 存储单元约 64 token；实践中稳定前缀 **≥1024 token** 时命中率更可靠
- `prompt_tokens = prompt_cache_hit_tokens + prompt_cache_miss_tokens`
- 首条新前缀请求命中常为 0；后续相同前缀请求命中上升（best-effort，非 100%）
- 前缀中不得夹带时间戳、随机 ID、JSON 键序抖动等动态内容

## 方案 A：缓存友好 messages + 串行 Stage 2→3

### 1. Messages 结构重排（核心）

**现状**（`utils/llm_messages.py`）：

```text
system: system_prompt.md
user:   可变内容（原题 / Stage1 JSON / Stage2·3 输出 …）
user:   阶段短指令
user:   stage{n}_prompt.md          ← 稳定内容在最后
```

**目标**：

```text
system: system_prompt.md             ← 稳定
user:   【本阶段任务说明】+ stage{n}_prompt.md   ← 稳定，跨题相同
user:   可变内容块（原题 / JSON / 压缩后的 S2·S3 …）
user:   固定短指令（按 stage 写死的单行文案）
```

**各 Stage 可变区约定：**

| Stage | 稳定前缀 | 可变 user 块 |
|-------|----------|----------------|
| 1 | system + stage1_prompt | 原题 |
| 2 | system + stage2_prompt | 原题 + Stage1 JSON |
| 3 | system + stage3_prompt | 原题 + Stage1 JSON |
| 4 | system + stage4_prompt（含 `[student_level]` 替换后的完整 prompt） | 学生水平、JSON 摘要、S2/S3 节选 |

说明：Stage 4 的 `student_level` 留在可变区，**不**放入跨题稳定前缀（水平切换不应污染其他题的缓存键）。

关闭 `ENABLE_PROMPT_CACHE_LAYOUT=0` 时仍回退为现有「单 system 合并 + 单 user」行为，避免破坏调试路径。

### 2. JSON 与文本稳定性

- 所有 `json.dumps(stage1_json, …)` 统一 `sort_keys=True`（`ensure_ascii=False, indent=2` 保留）
- messages 前缀禁止：时间戳、`guest_id`、运行 ID、随机数
- `prompt_rev`（`prompts/*.md` 哈希）变更时应用层缓存自然失效；messages 稳定前缀随 prompt 文件更新而更新，属预期行为

### 3. Stage 2 → Stage 3 一律串行

**移除**以下并行路径（不再提供开关）：

- `ui/run_manager.py`：`_start_parallel_23_thread`、`should_parallel_stage23` 分支、`parallel_mode` / `parallel_results` 状态机
- `ui/run_cache.py`：`should_parallel_stage23`、`try_load_parallel_cache`（或收敛为仅应用层缓存批量读取，若 Stage 2/3 串行后不再需要「并行加载缓存」）
- `workflow.py`：`run_full_pipeline` 内 `ThreadPoolExecutor` 并行 Stage 2/3

**统一行为**：全流程 / 断点续跑在 Stage 2 完成后**再**启动 Stage 3 API。墙钟时间 Stage 2+3 段约为 `T2 + T3`（此前并行为 `max(T2, T3)`）。

**预期收益（C）**：同一 session 内 S2 请求落盘后，S3 请求更易复用 API 侧已持久化的前缀单元（至少 `system + stage_prompt` 段；同题时还可共享原题+JSON 段之前的稳定部分）。

### 4. 可观测性（按用户要求精简）

- **不新增**侧边栏命中率 UI
- 保持现有能力：历史详情 `format_usage_detail` 中的「缓存命中 xxx」；`llm_run_usage` / 历史库 `cached_tokens` 字段照常写入
- 验证依赖：历史详情、DeepSeek 控制台账单、开发者自测连跑多题对比

### 5. 文档更新

实现后同步：

- `docs/LLM_CACHE.md`：删除「Stage2/3 并行」章节；更新 messages 结构说明；去掉「侧边栏显示缓存命中」表述
- `README.md` / `docs/USAGE.md`：全流程 Stage 2→3 改为串行表述
- `docs/COMMERCIAL_EDITION.md`：成本估算中删除并行相关表述

## 非目标

- 不做预热空请求
- 不做巨型 system 锚点（原方案 C）
- 不替代 `llm_cache` 应用层结果缓存
- 不新增 UI 命中率面板
- 不保留并行 Stage 2/3 或环境变量 `PARALLEL_STAGE23`

## 涉及文件（实现时）

| 文件 | 变更 |
|------|------|
| `utils/llm_messages.py` | 重排 `build_chat_messages`；可选抽出 `STAGE_TAIL_INSTRUCTION` 常量 |
| `workflow.py` | 各 stage 的 `user_parts` 顺序；`sort_keys`；`run_full_pipeline` 串行 S2→S3 |
| `ui/run_manager.py` | 删除并行 23 线程与相关 job 字段/错误分支 |
| `ui/run_cache.py` | 删除 `should_parallel_stage23` / `try_load_parallel_cache` 或等价简化 |
| `tests/test_llm_messages.py` | 更新 messages 顺序断言 |
| `tests/test_run_visibility.py` | 删除并行相关测试；补充串行 running stages |
| `docs/LLM_CACHE.md` 等 | 见 §5 |

## 风险与验收

| 风险 | 缓解 |
|------|------|
| 阶段说明提前导致输出质量下降 | 用 2–3 道真题对比改版前后 Stage 1–4 输出；无回归再合并 |
| 串行拉长等待 | 用户已接受；同题重复仍走 `llm_cache` 跳过 API |
| 前缀命中仍非 100% | 文档说明首题/首阶段偏低属 DeepSeek best-effort |

**验收标准：**

1. `pytest` 全绿（含 `test_llm_messages`、run 相关测试）
2. 同一模型连跑 **3 道不同题**的 Stage 1：第 2、3 题历史记录 `cached_tokens` 明显高于第 1 题（同 stage、稳定前缀段）
3. 全流程 Stage 3 在 Stage 2 之后发起，日志/运行状态无并行 Stage 2/3 文案
4. 代码库中无 `should_parallel_stage23` / `_start_parallel_23_thread` 调用路径

## 与现有缓存层关系

```text
同题重复生成 → 优先 llm_cache（0 API 调用）
新题 / 缓存未命中 → API 调用 → 受益于本方案的 DeepSeek 前缀缓存
```

两层互补，不冲突。
