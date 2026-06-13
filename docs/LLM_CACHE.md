# LLM 缓存与降本说明

本应用通过三层机制降低 **token 费用** 与 **等待时间**。

## 1. 应用层结果缓存（`llm_cache` 表）

- **开关**：侧边栏「使用 LLM 结果缓存」
- **键**：`guest_id` + 提供商 + 模型 + `prompt_rev`（`prompts/*.md` 内容哈希）+ 阶段号 + 题目哈希 + 上游输出哈希
- **命中**：同题、同模型、同 prompt 版本、同上游结果时，该阶段 **不再调用 API**
- **存储**：本地 `history.db` 的 `llm_cache` 表；云端 Neon 同表结构
- **失效**：修改 `prompts/` 下任意 md 文件后 `prompt_rev` 变化，旧缓存自动不用

## 2. 厂商 Prompt / 前缀缓存

- **开关**：环境变量 `ENABLE_PROMPT_CACHE_LAYOUT=1`（默认开启）
- **做法**：`system` 仅放 `system_prompt.md`；原题 + Stage1 JSON 等稳定内容在前面的 `user` 消息；阶段说明在最后一条 `user`
- **观测**：流式结束时解析 `usage`；侧边栏显示「缓存命中 xxx」（字段因平台而异）

| 提供商 | 典型模型 | usage 中缓存字段 | 说明 |
|--------|----------|------------------|------|
| OpenAI | gpt-4o-mini | `prompt_tokens_details.cached_tokens` | 自动前缀缓存，约 5–60 分钟窗口 |
| DeepSeek | deepseek-v4-pro / chat | `prompt_cache_hit_tokens` 等 | 以官方账单为准 |
| 阿里云百炼 | glm-5.1、deepseek-v4-pro | 兼容接口若返回则同上 | 部分模型有「上下文缓存」独立 API，本应用走 OpenAI 兼容路径 |
| 小米 MiMo | mimo-v2.5-pro | 若有 `cached_tokens` 则展示 | 以控制台账单为准 |

关闭旧版消息格式：`ENABLE_PROMPT_CACHE_LAYOUT=0`

流式 usage：`ENABLE_STREAM_USAGE=1`（默认开启，需 `stream_options.include_usage`）

## 3. Stage2 / Stage3 并行

- **条件**：全流程 / 断点续跑且连续执行 Stage 2 与 3
- **效果**：墙钟时间约 `max(T2,T3)`，**不减少 token**
- **注意**：并行后 Stage2→3 的「先后前缀缓存」不再生效；仍可享受统一 system 前缀缓存

## 4. Stage4 输入压缩

- 送入 API 前对 Stage2/3 长文做 **标题 + 首尾节选** 摘要（见 `utils/stage4_input.py`）
- 降低 Stage4 **输入 token**；缓存键与摘要内容一致

## 环境变量摘要

| 变量 | 默认 | 含义 |
|------|------|------|
| `ENABLE_PROMPT_CACHE_LAYOUT` | `1` | 缓存友好 messages 结构 |
| `ENABLE_STREAM_USAGE` | `1` | 流式返回 usage |
| `use_llm_cache`（session） | `True` | 应用层结果缓存 |

## 验证

1. 同一真题跑满四阶段 → 再点全流程：Stage 1–4 应 toast「已从缓存加载」
2. 侧边栏查看「上次运行 token」与「缓存命中」
3. 全流程对比并行前后总耗时（Cloud 日志）

## 5. 与历史记录的关系

- 应用层缓存（`llm_cache` 表）与 **历史备课包**（`history` 表）是两套数据。
- **清空当前结果** 不会删除历史或 `llm_cache` 中的条目。
- 换模型后缓存按 **新 provider + model** 查键，不会误用旧模型结果；若要强制调 API，可暂时关闭侧边栏「使用 LLM 结果缓存」。

## 6. 相关说明

- 历史自动保存：[USAGE.md](USAGE.md#3-历史记录自动保存)
- 换模型行为：[USAGE.md](USAGE.md#5-更换模型)
