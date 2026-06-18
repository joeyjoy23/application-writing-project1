# Agent 指南（应用文 AI 备课项目）

## 默认工作流

所有任务默认使用 **Superpowers** + **ECC** 技能。详见 `.cursor/rules/ecc-superpowers-default.mdc`。

## 项目要点

- **入口**：`app.py` → `ui/` + `workflow.py` 四阶段流水线
- **测试**：`pytest`（改 UI、DB、解析、导出、工作流后必跑）
- **文档**：`README.md`、`docs/USAGE.md`
- **部署**：Streamlit Cloud；侧边栏 `UI_BUILD_TAG` 核对版本

## Git

- 勿提交 `logs/`、`.env`、API Key、宣传 docx
- **完成任务后自动** `commit` + `push`（见 `.cursor/rules/auto-git-push-major.mdc`）；用户当次说「先别提交」时除外
