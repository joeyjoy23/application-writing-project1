# 高考英语应用文 AI 分析系统 — 项目简介

## 这是什么

面向**高中英语应用文（高考题型）**的 **AI 备课助手**，不是聊天机器人。教师输入一道真题（文字或图片），系统按固定流程生成：**审题分析 → PEEL/多版范文 → 句型词汇 → 教学指南**，可导出 Word，可保存历史并在断点处继续生成。

适用场景：备课、教研、课堂示范、个人练习后的讲评材料整理。

---

## 核心能力一览

| 能力 | 说明 |
|------|------|
| 四阶段工作流 | Stage1 审题（含结构化 JSON）→ Stage2 范文 → Stage3 句型词汇 → Stage4 教学指南 |
| 分步 / 全流程 | 可只跑某一阶段，也可一键跑满四阶段；支持跳过已完成阶段续跑 |
| 多模型提供商 | DeepSeek、OpenAI、Gemini、阿里云百炼、小米 MiMo（OpenAI 兼容接口） |
| 侧边栏配 Key | 网页端直接填 API Key，也可用 `.env` / Streamlit Secrets |
| 历史记录 | 同题同模型合并为一条；每完成一个 Stage 自动保存，失败也可保留已完成部分 |
| 载入续跑 | 从历史记录载入题目与进度，回到「新建」继续跑后续 Stage |
| 导出 Word | 一键生成排版好的 `.docx`（标题、正文层级） |
| 降本提速 | 可选 LLM 结果缓存；Stage2/3 并行；厂商前缀缓存友好消息结构 |

---

## 四阶段在做什么

```
原题 ──► Stage1 审题 ──► STRUCTURED_JSON + 教师可读总结
              │
              ├──► Stage2 PEEL 策略卡 + 多版范文
              │
              └──► Stage3 功能句型包 + 话题词汇锦囊
                        │
         Stage1~3 摘要 ──► Stage4 教学重点、易错点、课堂活动
```

- **Stage1** 建立「写作蓝图」JSON，供后续阶段校验要点与结构。  
- **Stage2 / Stage3** 仅依赖 Stage1，全流程中可**并行**执行以缩短等待。  
- **Stage4** 在压缩后的 Stage2/3 节选基础上生成教案向内容，控制 token 成本。

各阶段 Prompt 存放在 [`prompts/`](../prompts/)，由 [`workflow.py`](../workflow.py) 加载，便于教研修改而无需改界面代码。

---

## 技术架构（简要）

```text
app.py                 # Streamlit 入口、会话初始化
├── ui/
│   ├── sidebar.py     # 模式切换、API/模型、历史管理入口
│   ├── new_page.py    # 新建分析、历史列表/详情、导出
│   └── run_manager.py # 后台线程、流式进度、分阶段运行与取消
├── workflow.py        # 四阶段编排（纯业务，不依赖 Streamlit）
├── llm/client.py      # OpenAI 兼容客户端（流式、用量统计）
├── db/                # 历史 + LLM 缓存（SQLite 本地 / Neon 云端）
├── utils/             # 配置、解析、Word 导出、缓存键
└── prompts/           # 各阶段 Prompt 模板（Markdown）
```

**设计原则**

- **编排与 UI 分离**：长耗时 API 在子线程中执行，主线程 `rerun` 刷新进度。  
- **状态集中**：`WorkflowState` 存各阶段结果；`run_job` 锁定当次运行的模型，避免与侧边栏控件冲突。  
- **双环境数据库**：未配置 `DATABASE_URL` 时用本地 `history.db`；Streamlit Cloud 配置 Neon 后持久化多用户数据。

---

## 如何使用（教师视角）

1. 启动：本地双击 `run.bat` 或 `streamlit run app.py`（默认端口见 `.streamlit/config.toml`）。  
2. 在侧边栏选择**提供商、模型**，填写 **API Key**。  
3. 在「**新建**」模式粘贴或输入题目。  
4. 点击 **Stage 1~4** 或 **全流程**；运行中可看步骤日志与生成字数。  
5. 完成后 **导出 Word**；或切到「**历史**」查看、搜索、载入续跑。  

云端部署见 [NEON_SETUP.md](NEON_SETUP.md)；缓存与费用优化见 [LLM_CACHE.md](LLM_CACHE.md)。

---

## 历史与权限

- 每位浏览器访客有独立 `guest_id`，默认只能看到自己的记录。  
- 配置 `ADMIN_PASSWORD` 后，管理员可在侧边栏解锁查看全部历史（便于班级统一维护）。  
- 记录按 **题目哈希 + 模型名** 去重更新；换模型会生成新记录。  
- 列表中的阶段标记（如 `S1✓ S2· S3✓ S4·`）表示各 Stage 是否已有内容。

---

## 配置与部署要点

| 项 | 说明 |
|----|------|
| `.env` / Secrets | API Key、`LLM_PROVIDER`、`DATABASE_URL`、`ADMIN_PASSWORD` 等 |
| Streamlit Cloud | 勿在 `config.toml` 写死非 8501 端口；配置 Secrets 后 Reboot |
| 版本核对 | 侧边栏底部 `界面 xxxx` 标签（`UI_BUILD_TAG`）确认是否已更新部署 |
| MiMo 模型 | API 须使用小写 `mimo-v2.5-pro` 等官方 ID |

示例 Secrets 见项目根目录 `streamlit_cloud_secrets.toml.example`。

---

## 仓库与文档索引

| 文档 | 内容 |
|------|------|
| [README.md](../README.md) | 安装、快速开始、故障排查 |
| [NEON_SETUP.md](NEON_SETUP.md) | 云端 PostgreSQL 与管理员 |
| [LLM_CACHE.md](LLM_CACHE.md) | 结果缓存、前缀缓存、并行与 token 优化 |
| [COMMERCIAL_EDITION.md](COMMERCIAL_EDITION.md) | 复制为对外收费版的改造路线（内部版与商业版并行） |

---

## 维护说明

- 修改 Prompt：编辑 `prompts/*.md`，会触发 `prompt_rev` 变化，旧 LLM 结果缓存自动失效。  
- 修改阶段逻辑：优先改 `workflow.py` 与 `utils/parsers.py`，UI 仅负责触发与展示。  
- 日志：本地 `logs/app.log`（Rotating，约 5MB × 3 份）。

---

*文档随代码演进更新；以仓库内实际行为为准。*
