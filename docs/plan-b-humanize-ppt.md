# Plan B：Humanize PPT（HTML 演讲预览）

> **Plan A（生产）**：`scripts/one_click_classroom_ppt.py` → Architecture V1 + V2 python-pptx → 可编辑 `.pptx`（WPS 放映）  
> **Plan B（实验）**：Humanize PPT → AST 大纲 → 下游 HTML 渲染 → 浏览器预览 / 演讲模式

Plan B **不替代**主链路；仅用于探索「演讲叙事 + HTML 预览」。

## 技能安装路径

已通过 skills CLI 安装（2026-06-22）：

| 路径 | 说明 |
|------|------|
| `C:\Users\Joey\.agents\skills\humanize-ppt\` | 上游：AST 大纲、媒体槽、演讲体检 |
| `C:\Users\Joey\.agents\skills\ecc-frontend-slides\` | 下游（英文 / 通用 HTML deck） |
| （可选）`guizang-ppt-skill` | 下游（中文杂志风 / 瑞士风 HTML） |

安装命令（网络可用时）：

```powershell
npx skills add LearnPrompt/humanize-ppt -g
# 或告诉 Agent：请安装 https://github.com/LearnPrompt/humanize-ppt
```

依赖：Humanize 本体为 **Python 3** 本地脚本，零 API Key；配图可选 `baoyu-image-gen`（Codex CLI）；视频可选 Remotion。

## Humanize 产出物（AST 格式）

Humanize 不直接渲染最终 deck，核心 JSON 为 **`slide_plan.json`**（每页一条）：

```json
{
  "slides": [
    {
      "id": "s01",
      "title": "…",
      "role": "hook",
      "audience_in": "…",
      "audience_out": "…",
      "intent": "本页要完成的观众状态转移",
      "speaker_notes": "…",
      "media": []
    }
  ]
}
```

同目录还有：

- `speaker_intent.md` — 整场演讲意图
- `guizang-production-prompt.md` 或 frontend-slides brief — 交给下游渲染
- `preview-outline.html` — 渲染前状态转移图
- `presenter-shell.html` — 演讲模式壳（按 S 进入）

详见上游 `SPEC.md` 与示例 `examples/04-preview-outline-ai-tool-update/slide_plan.json`。

## 应用文导出 → Humanize 上游

应用文一键课件已产出结构化中间文件，可直接作 Humanize `--source`：

| 应用文产物 | 路径（默认 `ppt-work/`） | 用途 |
|------------|--------------------------|------|
| 四阶段合并源稿 | `yingyongwen-source.md` | **首选** Humanize 输入 |
| 分阶段 JSON | `export-data.json` | 可手工拼成 `.md` |
| Stage3 语言包 | `stage3.json` | 句型/词块页素材 |
| 架构蓝图 | `yingyongwen-blueprint.json` | 对照 Architecture V1 模块 |

推荐：用 `yingyongwen-source.md`（含 Stage1–4 全文），标题取题型/话题第一行。

## 下游渲染配对

| 场景 | Humanize `--renderer` | 下游 Skill |
|------|----------------------|------------|
| 中文课堂、杂志排版 | `guizang` | [guizang-ppt-skill](https://github.com/op7418/guizang-ppt-skill) |
| 英文 / 轻量 HTML | `frontend-slides` | `ecc-frontend-slides` 或 [frontend-slides](https://github.com/zarazhangrui/frontend-slides) |
| 英文多模板 | `beautiful-html-templates` | 同作者模板库 |

Humanize 只写 **brief + fix prompt**，不改下游已渲染 HTML。

## 首次试跑命令

在应用文导出并完成 Plan A 预处理之后：

```powershell
# 1) 应用文 → ppt-work（若尚未生成）
python scripts/one_click_classroom_ppt.py "D:\Downloads\应用文分析_xxx.html" `
  -o "D:\Downloads\ppt-work" --keep-intermediate --preset 80min

# 2) Humanize 出 AST + 生产 brief（中文 guizang 示例）
python C:\Users\Joey\.agents\skills\humanize-ppt\scripts\humanize_ppt.py `
  --source "D:\Downloads\ppt-work\yingyongwen-source.md" `
  --out "D:\Downloads\ppt-work\humanize-run" `
  --title "高考英语应用文 · 观点理由类" `
  --renderer guizang --guizang-style A --guizang-theme ink-classic

# 3) 把输出的 guizang-production-prompt.md 交给 guizang-ppt-skill Agent 渲染 HTML

# 4) 渲染完成后演讲体检（可选）
python C:\Users\Joey\.agents\skills\humanize-ppt\scripts\humanize_ppt.py `
  --qa-from "D:\Downloads\ppt-work\humanize-run\rendered\index.html" `
  --out "D:\Downloads\ppt-work\humanize-run" `
  --renderer guizang --max-qa-iterations 3
```

英文试跑：把 `--renderer guizang …` 换成 `--renderer frontend-slides`，下游用 `ecc-frontend-slides` 生成单文件 `presentation.html`。

## Plan A vs Plan B 边界

| | Plan A | Plan B |
|---|--------|--------|
| 输出 | `.pptx`（WPS / Office） | HTML + 演讲模式 |
| 结构 | 固定 Architecture V1 槽位 | AST 观众状态转移（LLM 编排） |
| 布局 | `ppt_layout_fit` + WPS 验证 | 下游 viewport-safe CSS |
| 适用 | **日常备课、校内放映** | 预览叙事、开源模板实验 |
| 入口 | `one_click_classroom_ppt.py` | `humanize_ppt.py` + 下游 skill |

## 已知限制

- GitHub 直连 clone 可能失败；可用 `npx skills add` 安装。
- Humanize 不生成 python-pptx；与 Plan A 并行，不写入 `generate_classroom_pptx_v2.py`。
- 下游 guizang / Remotion / baoyu-image-gen 需单独安装（见 Humanize README「30 秒装上」表）。
