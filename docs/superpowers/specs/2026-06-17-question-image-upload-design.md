# 题目图片上传（识图审题）设计

**日期：** 2026-06-17  
**状态：** **已实现**  
**范围：** 新建分析页题目输入、Stage 1 多模态 API、侧边栏 👁 标识、历史摘要

---

## 背景与目标

教师有时拿到的是**拍照/截图**（含海报、选项图等非纯文字），需要在「题目输入」区上传图片代替粘贴文字。要求：

- **图片与文字二选一**；同时存在时**禁止运行**（须清掉其一）。
- **单次仅 1 张图**（多海报可放在同一张图内）。
- **Stage 1 原生识图**（非 OCR 预检），后续 Stage 2–4 仍走文字流水线。
- **图片仅本次会话保留**；写入历史时**不存 base64**，只存「识别原文 + 图描述」前缀文字。
- 侧边栏对支持识图的模型标 **👁 支持识图**；有图时只能选用带 👁 的模型。

---

## 已确认的产品决策

| 项 | 决策 |
|----|------|
| 识图方式 | 方案 1：仅 Stage 1 发图，JSON 增加识图字段 |
| 输入互斥 | 有图且有文字 → 报错并禁用运行 |
| 图片数量 | 1 张/次 |
| 历史原图 | 不持久化；会话内可预览缩略图 |
| 历史文字 | `{recognized_question_text}\n[图：{image_brief_description}]` |
| 模型 UI | 👁 标识 + 运行时校验 |

---

## 1. 题目输入 UI

**位置：** `ui/new_page.py` → `render_new_analysis`「题目输入」区块。

- `st.file_uploader`：单文件，`type=["jpg","jpeg","png"]`，原文件 ≤4MB。
- 上传后客户端压缩：最长边 ≤1280px，JPEG quality≈85，目标 ≤400KB。
- 存入 `session_state.question_image`：`{ "mime": "image/jpeg", "b64": "...", "name": "..." }`。
- 有图时在输入区下方显示缩略图 +「清除图片」按钮。
- **互斥：**
  - `question_image` 非空 **且** `question.strip()` 非空 → `st.error("请只保留文字或图片其中一种")`，禁用运行按钮逻辑（`try_start_run_job` 前校验）。
  - 上传图片 → 可选提示清空文字框；在文字框输入 → 清除 `question_image`（或提示用户先删图）。
- **提示文案（有图时）：**  
  `已上传图片，请选用侧边栏带 👁 支持识图 的模型。`

---

## 2. 多模态模型白名单与侧边栏

**配置：** `utils/config.py` 新增：

```python
MULTIMODAL_MODELS: frozenset[tuple[str, str]]  # (provider, model_id)
```

**函数：**

- `is_multimodal_model(provider, model_id) -> bool`
- `format_model_label(...)`：若在白名单，展示名后缀 ` · 👁 支持识图`

### 2.1 现有列表中标记 👁

| provider | model_id |
|----------|----------|
| openai | gpt-4o, gpt-4o-mini, gpt-4.1-mini |
| gemini | gemini-2.0-flash, gemini-2.5-flash-preview-05-20 |
| dashscope | kimi-k2.6 |
| mimo | mimo-v2.5 |
| agnes | agnes-2.0-flash, agnes-2.0-flash-thinking |

### 2.2 新增到侧边栏并标记 👁

| provider | 新增 model_id | 说明 |
|----------|---------------|------|
| zhipu | glm-4.6v-flash | 智谱视觉 Flash，有免费档 |
| zhipu | glm-4.6v | 智谱视觉旗舰（可选同批加入） |
| dashscope | qwen3.7-plus | 千问视觉旗舰 |
| dashscope | qwen3.6-plus | 千问视觉均衡 |

**不标 👁（保持纯文本）：** DeepSeek v4-pro/flash；智谱 glm-5.2/5.1/4.7；百炼 qwen3.7-max、qwen-plus、qwen3.6-max-preview、qwen3-next-80b-a3b、glm-5、MiniMax-M2.7、deepseek-v4-*（百炼）；MiMo pro/flash（官方识图示例以 mimo-v2.5 为准，保守不标）。

### 2.3 运行时校验

- `try_start_run_job` / `render_new_analysis`：若 `question_image` 存在且 `not is_multimodal_model(provider, model)` → `st.error` 提示切换 👁 模型。
- 纯文字输入：任意模型不受影响。

---

## 3. API 与 Stage 1

### 3.1 消息构造

**新模块或扩展：** `utils/llm_messages.py`

- `build_stage1_user_content(*, question: str, image: dict | None) -> str | list[dict]`
  - 无图：返回纯文字（与现行为一致）。
  - 有图：OpenAI 兼容 `content` 数组：
    ```json
    [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
      {"type": "text", "text": "【原题图片】请识别图中题目..."}
    ]
    ```

**仅 Stage 1** 调用多模态 content；Stage 2–4 的 `build_chat_messages` 不变，仍用 Stage 1 产出的文字上下文。

### 3.2 Prompt / JSON 扩展

**文件：** `prompts/stage1_prompt.md`

Stage 1 在**输入为图片**时额外要求 STRUCTURED_JSON 包含：

| 字段 | 说明 |
|------|------|
| `recognized_question_text` | 图中可识别的题目原文（OCR 能识别的尽量完整） |
| `image_brief_description` | 图片简短描述（如「两张活动海报供二选一」） |

纯文字输入时两字段可为空字符串或省略；解析器兼容缺省。

### 3.3 工作流状态

- `session_state.question_image`：会话内原图（不写入 DB）。
- Stage 1 完成后：
  - `state.question` = 拼接串（供 Stage 2–4、导出、缓存）：
    ```
    {recognized_question_text}
    [图：{image_brief_description}]
    ```
  - 若 `recognized_question_text` 为空，fallback 用 `image_brief_description` 或 `[图片题目]`。

**`workflow.py` / `run_manager.py`：** Stage 1 调用处传入 `question_image`；job 对象可含 `question_image` 引用（内存 session，不序列化进 history JSON）。

---

## 4. 历史、缓存与导出

### 4.1 历史

- `workflow_state_payload` / `raw_input`：使用 Stage 1 完成后的拼接文字（**不含** base64）。
- 历史列表 `topic`：沿用 `topic_summary(raw_input)`，自然显示前两行摘要。
- **载入历史：** 仅恢复文字；无原图（符合「仅本次会话保留原图」）。

### 4.2 LLM 缓存

- 图片题：Stage 1 缓存键在题目 hash 中使用拼接后的 `state.question`（Stage 1 完成后）或 image content hash（运行中）——实现计划细化为「Stage 1 完成前用 image sha256，完成后用文字 hash」，避免同图重复调 API。

### 4.3 导出 Word / JSON

- Word/JSON 题目区使用拼接后的文字；**不嵌入图片**（首期）。
- 可选 caption：`（本题由图片识题，原图未存档）`

---

## 5. 错误处理与测试

| 场景 | 行为 |
|------|------|
| 图+文同时存在 | 错误提示，不启动 job |
| 有图 + 非 👁 模型 | 错误提示，列出可用 👁 模型示例 |
| 文件过大/格式不对 | uploader 拒绝或上传后校验失败 |
| Stage 1 JSON 缺识图字段 | 解析 fallback，`raw_input` 用 `[图片题目]` |
| 百炼 kimi-k2.6 仅 URL | 若 data URI 失败，错误提示换 OpenAI/Gemini/MiMo 或后续加临时 URL 方案 |

**测试（pytest）：**

- `is_multimodal_model` 白名单
- 互斥校验 helper（纯函数，无 Streamlit）
- `build_stage1_user_content` 有/无图
- 历史 `raw_input` 拼接（mock Stage1 JSON）
- `format_model_label` 含 👁 后缀

**不纳入首期：** 历史详情原图、Word 嵌图、多图上传、视频题。

---

## 6. 涉及文件（实现参考）

| 文件 | 变更 |
|------|------|
| `utils/config.py` | MULTIMODAL_MODELS、新模型 ID、format_model_label |
| `utils/llm_messages.py` | Stage1 多模态 content |
| `utils/question_input.py`（新，可选） | 压缩、互斥校验、history 拼接 |
| `ui/new_page.py` | uploader、互斥 UI、校验 |
| `ui/run_manager.py` | 传图进 Stage 1、job 校验 |
| `workflow.py` | run_stage1 多模态 messages |
| `prompts/stage1_prompt.md` | 识图字段说明 |
| `utils/parsers.py` | 解析新 JSON 字段 |
| `services/workflow_storage.py` | raw_input 来源（Stage1 后拼接） |
| `tests/test_question_image.py`（新） | 上述单测 |

---

## 7. 开放问题（实现前可默认）

1. **智谱/百炼新增模型默认选中：** 不自动切换；有图时若当前模型非 👁，仅提示用户手动切换。
2. **glm-4.6v 与 glm-4.6v-flash：** 均加入列表；默认推荐 flash 给成本敏感场景。
3. **kimi-k2.6 base64：** 首期先实现 data URI；若联调失败再在 spec 迭代中加 OSS/临时 URL。

---

## Spec 自检

- [x] 无 TBD 占位
- [x] 与「图片会话内、历史仅文字」一致
- [x] 范围限定 Stage 1 发图 + 侧边栏 👁，不含 Word 嵌图
- [x] 互斥、单图、海报场景均已覆盖
