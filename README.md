# 高考英语应用文 AI 分析系统

多阶段 AI Workflow（非聊天机器人）：审题 → 范文 → 句型词汇 → 教学指南。

**项目说明（核心功能、亮点与使用方式，约 800 字）**见 [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md)。

## 技术栈

- Python
- Streamlit
- OpenAI Compatible API

## 项目结构

```text
project/
├── app.py              # Streamlit 入口
├── workflow.py         # 四阶段工作流编排
├── services/           # 无 UI 业务逻辑（序列化、进度）
├── prompts/            # Prompt 模板（动态加载）
├── llm/                # API 客户端
├── utils/              # 配置与解析
├── ui/                 # Streamlit 页面与展示
├── tests/              # pytest 回归
├── styles/             # 界面样式
├── requirements.txt
└── .env
```

## 快速开始

```bash
cd project
pip install -r requirements.txt
cp .env.example .env   # 可选：预填 API Key
streamlit run app.py --server.port 8502
```

浏览器访问：**http://localhost:8502**（默认端口已写在 `.streamlit/config.toml`，也可双击 `run.bat` 启动）。

### 开发与测试

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

`tests/` 覆盖 Stage1 解析、工作流序列化、进度推断与 LLM 消息构造；改 `prompts/` 或 `utils/parsers.py` 后建议先跑一遍。

启动后在**左侧边栏**选择模型提供商（DeepSeek / **智谱** / OpenAI / Gemini / 百炼 / **小米 MiMo**）、模型名称，并输入 API Key；留空 Key 时会尝试从 `.env` 或 Streamlit Secrets 读取。DeepSeek 官方仅 **`deepseek-v4-pro`**；智谱为 **`glm-5.1` / `glm-4.7`**（[open.bigmodel.cn](https://open.bigmodel.cn)）。

**Streamlit Cloud 更新**：改代码后须 `git push` 到 GitHub，再在 Cloud 里 **Reboot**；侧边栏底部版本标签可核对是否已部署。

### 云端历史（Neon，可选）

部署到 Streamlit Cloud 后，在 Secrets 配置 `DATABASE_URL`（Neon PostgreSQL）与 `ADMIN_PASSWORD`，即可持久保存历史；普通用户仅见自己的记录，管理员在侧边栏解锁后可查看全部。详见 [docs/NEON_SETUP.md](docs/NEON_SETUP.md)。

### LLM 缓存与降本

侧边栏可开启「LLM 结果缓存」；全流程自动并行 Stage 2/3。厂商前缀缓存、环境变量与各平台 `usage` 字段说明见 [docs/LLM_CACHE.md](docs/LLM_CACHE.md)。

### 若卡在 Calling API 或 Connection error

1. 看运行日志是否出现 **「正在接收… 已收到约 N 字」**——有数字在涨说明正常，只是模型慢。
2. 百炼旗舰模型（如 qwen3.6-max-preview）可能 **1–3 分钟** 才有首字，可改用 **qwen-plus** / **deepseek-v4-flash** 试跑。
3. 确认 API Key、网络；终端若有 401/404 按提示换模型或检查 Key。
4. `.env` / Secrets 可调：`STAGE_TIMEOUT_SECONDS=300`（单 Stage 最长等待）、`API_READ_TIMEOUT_SECONDS=300`、`STREAM_IDLE_TIMEOUT_SECONDS=180`；若输出在文末被截断，可增大 `STAGE1_MAX_TOKENS`～`STAGE4_MAX_TOKENS`（默认 8192/8192/6144/6144，见 `.env.example`）。
5. 完整四阶段约 8–15 分钟；仍断开则分步运行 Stage 1→2→3→4。

## 工作流

| 阶段 | 输入 | 输出 |
|------|------|------|
| Stage1 | 原题 | 审题总结 + STRUCTURED_JSON |
| Stage2 | 原题 + Stage1 JSON | PEEL、三版范文、对比分析 |
| Stage3 | 原题 + Stage1 JSON | 功能句型包、话题词汇锦囊 |
| Stage4 | Stage1 JSON + Stage2 + Stage3 | 教学重点、易错点、课堂活动 |

Prompt 存放在 `prompts/`，由 `workflow.py` 读取，**不在 `app.py` 中硬编码**。

完成至少 Stage 1 后，可点击 **「一键导出 Word」**：含题目与三阶段内容，标题层级、列表与表格已排版（黑体标题 + 宋体正文，适合阅读与打印）。
