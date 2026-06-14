# 高考英语应用文 AI 分析系统

多阶段 AI Workflow（非聊天机器人）：审题 → 范文 → 句型词汇 → 教学指南。

**项目说明（核心功能、亮点）**见 [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)。  
**日常使用（历史、清空、换模型、导出）**见 [docs/USAGE.md](docs/USAGE.md)。

## 技术栈

- Python
- Streamlit
- OpenAI Compatible API
- SQLite（本地）/ Neon PostgreSQL（云端，可选）

## 项目结构

```text
应用文project/
├── app.py                  # Streamlit 入口
├── workflow.py             # 四阶段工作流编排
├── services/               # 业务逻辑（序列化、进度、模型来源追踪）
├── prompts/                # Prompt 模板（动态加载，改后缓存自动失效）
├── llm/                    # API 客户端
├── db/                     # 历史记录与 LLM 缓存（SQLite / Postgres）
├── utils/                  # 配置、解析、Word 导出
├── ui/                     # 页面、侧边栏、运行调度
├── tests/                  # pytest 回归
├── styles/                 # 界面样式
├── docs/                   # 说明文档
├── requirements.txt
└── .env
```

## 快速开始

```bash
pip install -r requirements.txt
cp .env.example .env   # 可选：预填 API Key
streamlit run app.py --server.port 8502
```

浏览器访问：**http://localhost:8502**（默认端口见 `.streamlit/config.toml`，也可双击 `run.bat`）。

### 开发与测试

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

`tests/` 覆盖 Stage1 解析、工作流序列化、进度推断、Word 导出、模型切换与侧边栏导航等；改 `prompts/` 或 `utils/parsers.py` 后建议先跑一遍。

### 基本使用

1. 侧边栏选 **新建**，配置模型与 API Key（DeepSeek / 智谱 / OpenAI / Gemini / 百炼 / MiMo）。
2. 粘贴题目 → **完整流程** 或单跑某一 Stage。
3. **每完成一个 Stage 自动写入历史**（同题同模型合并为一条）；可 **导出 Word** 或在 **历史** 中载入续跑。
4. **清空当前结果** 只清本页输出，**不会删除**历史记录（详见 [docs/USAGE.md](docs/USAGE.md)）。

**Streamlit Cloud**：`git push` 后在 [share.streamlit.io](https://share.streamlit.io) **Reboot**；侧边栏底部版本标签可核对部署版本。见 [docs/DEPLOY_CLOUD.md](docs/DEPLOY_CLOUD.md)。

### 云端历史（Neon，可选）

Secrets 配置 `DATABASE_URL` 与 `ADMIN_PASSWORD` 后，历史与 LLM 缓存可跨会话持久化；管理员可查看全部记录。详见 [docs/NEON_SETUP.md](docs/NEON_SETUP.md)。

### LLM 缓存与降本

侧边栏「使用 LLM 结果缓存」：同题同模型同 prompt 版本可跳过 API。Stage 2/3 全流程并行。详见 [docs/LLM_CACHE.md](docs/LLM_CACHE.md)。

### API 重试与容错

API 调用失败时自动重试（最多 3 次，指数退避 2s→4s→8s）。超时、连接失败、限流（429）会自动重试；401/400/404 不重试（配置错误）。可在 `.env` 中配置：
- `LLM_MAX_RETRIES=3`（重试次数）
- `LLM_RETRY_BASE_DELAY=2`（基础延迟秒数）

### Token 用量追踪

每次运行的 token 用量（输入/输出/缓存命中）会自动记录到历史数据库，可在历史列表和详情页查看，便于回溯成本和优化 prompt。

### 若卡在 Calling API 或 Connection error

1. 看运行日志是否出现 **「正在接收… 已收到约 N 字」**——有数字在涨说明正常，只是模型慢。
2. 百炼旗舰模型可能 **1–3 分钟** 才有首字，可改用 **qwen-plus** 等更快模型试跑。
3. 确认 API Key、网络；401/404 按提示换模型或检查 Key。
4. `.env` / Secrets 可调：`STAGE_TIMEOUT_SECONDS`、`API_READ_TIMEOUT_SECONDS`、`STAGE1_MAX_TOKENS`～`STAGE4_MAX_TOKENS`（默认 8192/8192/6144/6144，见 `.env.example`）。
5. 完整四阶段约 8–15 分钟；仍不稳定可分步 Stage 1→2→3→4。

## 工作流

| 阶段 | 输入 | 输出 |
|------|------|------|
| Stage1 | 原题 | **题目类型识别** + 审题总结 + STRUCTURED_JSON |
| Stage2 | 原题 + Stage1 JSON | PEEL、三版范文（105–125 词）、对比分析（根据题目类型差异化） |
| Stage3 | 原题 + Stage1 JSON | 功能句型包、话题词汇锦囊（根据题目类型差异化） |
| Stage4 | Stage1 JSON + Stage2 + Stage3 | 教学指南（受学生水平影响） |

**题目类型识别**：Stage1 会自动识别题目类型（活动记录类 / 观点理由类 / 混合类型），并根据类型给出差异化的分析重点、高分要点和构思维度推荐。

Prompt 存放在 `prompts/`，由 `workflow.py` 读取，不在 `app.py` 中硬编码。

完成至少 Stage 1 后可 **一键导出 Word**（黑体标题 + 宋体正文，支持 h1–h6 与构思维度分块排版）。

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/USAGE.md](docs/USAGE.md) | 历史自动保存、清空 vs 删除、换模型、断点续跑 |
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | 项目定位与亮点 |
| [docs/DEPLOY_CLOUD.md](docs/DEPLOY_CLOUD.md) | Streamlit Cloud 部署与 Reboot |
| [docs/NEON_SETUP.md](docs/NEON_SETUP.md) | Neon 数据库配置 |
| [docs/LLM_CACHE.md](docs/LLM_CACHE.md) | 缓存键、降本与并行说明 |
