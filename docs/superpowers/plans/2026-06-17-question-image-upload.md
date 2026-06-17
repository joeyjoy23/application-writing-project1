# 题目图片上传（识图审题）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建分析页支持「图片或文字二选一」上传题目；Stage 1 对 👁 多模态模型发图识题；历史仅存识别文字摘要，会话内保留缩略图。

**Architecture:** `utils/question_input.py` 负责压缩/互斥/历史拼接；`utils/config.py` 维护 `MULTIMODAL_MODELS` 白名单；`workflow.run_stage1` 在有图时用 OpenAI 多模态 `content` 数组；Stage 1 JSON 新增识图字段后写入 `state.question` 供 Stage 2–4 与历史。

**Tech Stack:** Python 3.12, Streamlit, Pillow, OpenAI-compatible chat API, pytest

**Spec:** `docs/superpowers/specs/2026-06-17-question-image-upload-design.md`

---

## File Map

| File | 职责 |
|------|------|
| `utils/config.py` | `MULTIMODAL_MODELS`、`is_multimodal_model`、新增 VL 模型 ID、`format_model_label` 👁 后缀 |
| `utils/question_input.py` | **新建** 压缩、互斥、历史拼接、data URI |
| `utils/llm_messages.py` | 支持 multimodal user part；`build_stage1_image_user_part` |
| `utils/parsers.py` | `format_image_question_text(structured_json)` |
| `workflow.py` | `run_stage1(..., question_image=)`；完成后更新 `state.question` |
| `ui/run_manager.py` | 启动前校验；job 传图；Stage1 后写 question |
| `ui/new_page.py` | file_uploader、缩略图、互斥 UI、caption |
| `app.py` | `question_image` session 默认值 |
| `prompts/stage1_prompt.md` | 识图 JSON 字段说明 |
| `requirements.txt` | 添加 `Pillow>=10.0.0` |
| `tests/test_question_image.py` | **新建** 单测 |
| `tests/test_provider_model_config.py` | 扩展 👁 白名单测试 |
| `docs/USAGE.md` | 简短用法说明 |

---

### Task 1: 多模态模型白名单与新模型 ID

**Files:**
- Modify: `utils/config.py`
- Modify: `tests/test_provider_model_config.py`

- [x] **Step 1: 写失败测试**

在 `tests/test_provider_model_config.py` 追加：

```python
from utils.config import (
    MULTIMODAL_MODELS,
    format_model_label,
    is_multimodal_model,
    PROVIDER_MODELS,
)


def test_multimodal_whitelist():
    assert is_multimodal_model("openai", "gpt-4o")
    assert is_multimodal_model("zhipu", "glm-4.6v-flash")
    assert is_multimodal_model("dashscope", "qwen3.7-plus")
    assert not is_multimodal_model("deepseek", "deepseek-v4-pro")
    assert not is_multimodal_model("zhipu", "glm-5.2")


def test_new_vision_models_in_provider_lists():
    assert "glm-4.6v-flash" in PROVIDER_MODELS["zhipu"]
    assert "glm-4.6v" in PROVIDER_MODELS["zhipu"]
    assert "qwen3.7-plus" in PROVIDER_MODELS["dashscope"]
    assert "qwen3.6-plus" in PROVIDER_MODELS["dashscope"]


def test_format_model_label_vision_suffix():
    label = format_model_label("openai", "gpt-4o")
    assert "👁" in label
    label2 = format_model_label("deepseek", "deepseek-v4-pro")
    assert "👁" not in label2
```

- [x] **Step 2: 运行测试确认 FAIL**

Run: `python -m pytest tests/test_provider_model_config.py::test_multimodal_whitelist tests/test_provider_model_config.py::test_new_vision_models_in_provider_lists tests/test_provider_model_config.py::test_format_model_label_vision_suffix -v`

Expected: FAIL (`is_multimodal_model` / 新模型不存在)

- [x] **Step 3: 实现 `utils/config.py`**

1. 在 `ZHIPU_MODEL_LABELS` 增加：

```python
"glm-4.6v-flash": "glm-4.6v-flash · 视觉 Flash",
"glm-4.6v": "glm-4.6v · 视觉旗舰",
```

2. 在 `DASHSCOPE_MODEL_LABELS` 增加：

```python
"qwen3.7-plus": "qwen3.7-plus · 千问视觉旗舰",
"qwen3.6-plus": "qwen3.6-plus · 千问视觉均衡",
```

3. 更新 `PROVIDER_MODELS`：

```python
"zhipu": ["glm-5.2", "glm-5.1", "glm-4.7", "glm-4.6v", "glm-4.6v-flash"],
"dashscope": [
    "qwen3.7-plus",
    "qwen3.6-plus",
    *list(DASHSCOPE_MODEL_LABELS.keys()),  # 或显式列表，确保 plus 在前
],
```

（保持现有模型不删；plus 条目可放在 dashscope 列表靠前位置。）

4. 新增：

```python
MULTIMODAL_MODELS: frozenset[tuple[str, str]] = frozenset({
    ("openai", "gpt-4o"),
    ("openai", "gpt-4o-mini"),
    ("openai", "gpt-4.1-mini"),
    ("gemini", "gemini-2.0-flash"),
    ("gemini", "gemini-2.5-flash-preview-05-20"),
    ("dashscope", "kimi-k2.6"),
    ("dashscope", "qwen3.7-plus"),
    ("dashscope", "qwen3.6-plus"),
    ("zhipu", "glm-4.6v"),
    ("zhipu", "glm-4.6v-flash"),
    ("mimo", "mimo-v2.5"),
    ("agnes", "agnes-2.0-flash"),
    ("agnes", "agnes-2.0-flash-thinking"),
})

_VISION_LABEL_SUFFIX = " · 👁 支持识图"


def is_multimodal_model(provider: str, model_id: str) -> bool:
    p = (provider or "").lower().strip()
    m = (model_id or "").strip()
    return (p, m) in MULTIMODAL_MODELS
```

5. 在 `format_model_label` 末尾：

```python
base = ...  # 现有逻辑
if is_multimodal_model(provider, model_id):
    return base + _VISION_LABEL_SUFFIX
return base
```

- [x] **Step 4: 运行测试确认 PASS**

Run: `python -m pytest tests/test_provider_model_config.py -v`

- [x] **Step 5: Commit**

```bash
git add utils/config.py tests/test_provider_model_config.py
git commit -m "feat: 多模态模型白名单与 VL 模型选项"
```

---

### Task 2: 题目输入工具（压缩 / 互斥 / 历史拼接）

**Files:**
- Create: `utils/question_input.py`
- Create: `tests/test_question_image.py`
- Modify: `requirements.txt`

- [x] **Step 1: 添加 Pillow 依赖**

`requirements.txt` 追加一行：

```
Pillow>=10.0.0
```

Run: `pip install "Pillow>=10.0.0"`

- [x] **Step 2: 写失败测试**

创建 `tests/test_question_image.py`：

```python
from utils.question_input import (
    format_image_question_for_history,
    image_to_data_uri,
    question_input_conflict,
    QuestionImage,
)


def test_question_input_conflict():
    assert question_input_conflict("hello", None) is False
    assert question_input_conflict("", {"b64": "x", "mime": "image/jpeg"}) is False
    assert question_input_conflict("text", {"b64": "x", "mime": "image/jpeg"}) is True


def test_format_image_question_for_history():
    assert format_image_question_for_history({
        "recognized_question_text": "Write a letter...",
        "image_brief_description": "两张海报供选择",
    }) == "Write a letter...\n[图：两张海报供选择]"
    assert format_image_question_for_history({}) == "[图片题目]"


def test_image_to_data_uri():
    img = QuestionImage(mime="image/jpeg", b64="abc123", name="q.jpg")
    assert image_to_data_uri(img) == "data:image/jpeg;base64,abc123"
```

- [x] **Step 3: 运行测试确认 FAIL**

Run: `python -m pytest tests/test_question_image.py -v`

- [x] **Step 4: 实现 `utils/question_input.py`**

```python
"""题目输入：图片压缩、互斥校验、历史摘要拼接（无 Streamlit 依赖）。"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from PIL import Image

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_EDGE_PX = 1280
JPEG_QUALITY = 85
TARGET_MAX_BYTES = 400 * 1024


@dataclass(frozen=True)
class QuestionImage:
    mime: str
    b64: str
    name: str = "question.jpg"


def question_input_conflict(text: str, image: dict[str, Any] | QuestionImage | None) -> bool:
    has_text = bool((text or "").strip())
    has_image = image is not None and bool(getattr(image, "b64", None) or (image or {}).get("b64"))
    return has_text and has_image


def image_to_data_uri(image: QuestionImage | dict[str, Any]) -> str:
    if isinstance(image, QuestionImage):
        mime, b64 = image.mime, image.b64
    else:
        mime = image.get("mime") or "image/jpeg"
        b64 = image["b64"]
    return f"data:{mime};base64,{b64}"


def format_image_question_for_history(structured: dict[str, Any]) -> str:
    text = (structured.get("recognized_question_text") or "").strip()
    desc = (structured.get("image_brief_description") or "").strip()
    if text and desc:
        return f"{text}\n[图：{desc}]"
    if text:
        return text
    if desc:
        return f"[图：{desc}]"
    return "[图片题目]"


def compress_uploaded_image(raw_bytes: bytes, *, filename: str = "upload.jpg") -> QuestionImage:
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"图片超过 {MAX_UPLOAD_BYTES // (1024*1024)}MB 限制")
    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, MAX_EDGE_PX / max(w, h))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    quality = JPEG_QUALITY
    while quality >= 60:
        buf.seek(0)
        buf.truncate(0)
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= TARGET_MAX_BYTES:
            break
        quality -= 5
    import base64
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    name = filename if filename.lower().endswith((".jpg", ".jpeg")) else "question.jpg"
    return QuestionImage(mime="image/jpeg", b64=b64, name=name)
```

- [x] **Step 5: 运行测试确认 PASS**

Run: `python -m pytest tests/test_question_image.py -v`

- [x] **Step 6: Commit**

```bash
git add utils/question_input.py tests/test_question_image.py requirements.txt
git commit -m "feat: 题目图片压缩与历史摘要拼接工具"
```

---

### Task 3: Stage 1 多模态 messages

**Files:**
- Modify: `utils/llm_messages.py`
- Modify: `tests/test_llm_messages.py`

- [x] **Step 1: 写失败测试**

```python
def test_build_stage1_image_user_part():
    from utils.llm_messages import build_stage1_image_user_part

    part = build_stage1_image_user_part(
        data_uri="data:image/jpeg;base64,abc",
        hint="【原题图片】请识别图中题目。",
    )
    assert part[0]["type"] == "image_url"
    assert part[0]["image_url"]["url"] == "data:image/jpeg;base64,abc"
    assert part[1]["type"] == "text"


def test_build_chat_messages_accepts_multimodal_user_part(monkeypatch):
    monkeypatch.setenv("ENABLE_PROMPT_CACHE_LAYOUT", "1")
    multimodal = [{"type": "text", "text": "see image"}]
    msgs = build_chat_messages(
        system_base="SYS",
        stage_prompt="P",
        user_parts=[multimodal],
        tail_instruction="TAIL",
    )
    assert msgs[2]["content"] == multimodal
```

- [x] **Step 2: 运行 FAIL**

Run: `python -m pytest tests/test_llm_messages.py::test_build_stage1_image_user_part tests/test_llm_messages.py::test_build_chat_messages_accepts_multimodal_user_part -v`

- [x] **Step 3: 修改 `build_chat_messages`**

`user_parts` 类型改为 `list[str | list[dict[str, Any]]]`。循环中：

```python
for part in user_parts:
    if isinstance(part, list):
        messages.append({"role": "user", "content": part})
    elif part.strip():
        messages.append({"role": "user", "content": part.strip()})
```

新增：

```python
def build_stage1_image_user_part(*, data_uri: str, hint: str) -> list[dict[str, Any]]:
    return [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {"type": "text", "text": hint.strip()},
    ]
```

- [x] **Step 4: PASS + commit**

```bash
git add utils/llm_messages.py tests/test_llm_messages.py
git commit -m "feat: Stage1 多模态 user content 构造"
```

---

### Task 4: Stage 1 Prompt 与解析

**Files:**
- Modify: `prompts/stage1_prompt.md`
- Modify: `utils/parsers.py`
- Modify: `tests/test_question_image.py`

- [x] **Step 1: 更新 prompt**

在 `prompts/stage1_prompt.md` 的 STRUCTURED_JSON 说明区增加（仅当输入为图片时必填）：

```markdown
- `recognized_question_text`（图片输入时必填）：图中可识别的题目原文
- `image_brief_description`（图片输入时必填）：图片内容一句话描述（如「两张活动海报供二选一」）
```

- [x] **Step 2: 测试 + 实现 parsers**

测试：

```python
from utils.parsers import format_image_question_for_history as fmt_from_parsers

def test_parsers_format_image_question():
    assert fmt_from_parsers({"recognized_question_text": "A", "image_brief_description": "B"}) == "A\n[图：B]"
```

在 `utils/parsers.py` 添加（或 re-export `question_input.format_image_question_for_history` 避免重复）：

```python
def format_image_question_for_history(structured: dict[str, Any]) -> str:
    from utils.question_input import format_image_question_for_history as _fmt
    return _fmt(structured)
```

- [x] **Step 3: pytest + commit**

```bash
git add prompts/stage1_prompt.md utils/parsers.py tests/test_question_image.py
git commit -m "feat: Stage1 识图 JSON 字段与历史拼接解析"
```

---

### Task 5: Workflow Stage 1 发图与 question 回填

**Files:**
- Modify: `workflow.py`
- Modify: `tests/test_question_image.py`

- [x] **Step 1: 扩展 `run_stage1` 签名**

```python
def run_stage1(
    self,
    question: str,
    *,
    question_image: dict[str, Any] | None = None,
    ...
) -> Stage1Result:
```

- [x] **Step 2: 构造 user_parts**

```python
from utils.llm_messages import build_stage1_image_user_part
from utils.question_input import image_to_data_uri

if question_image:
    data_uri = image_to_data_uri(question_image)
    user_parts = [
        build_stage1_image_user_part(
            data_uri=data_uri,
            hint=(
                "【原题图片】请识别图中题目与选项/海报等非文字信息。"
                "STRUCTURED_JSON 必须包含 recognized_question_text 与 image_brief_description。"
            ),
        )
    ]
else:
    user_parts = [f"【应用文原题】\n\n{question.strip()}"]
```

- [x] **Step 3: 测试 mock（可选轻量）**

在 `tests/test_question_image.py` 用 monkeypatch 验证 `run_stage1` 传入 image 时 messages 含 `image_url`（mock `_call`）。

- [x] **Step 4: Commit**

```bash
git add workflow.py tests/test_question_image.py
git commit -m "feat: workflow Stage1 支持图片输入"
```

---

### Task 6: Run manager 校验与 Stage1 后写 question

**Files:**
- Modify: `ui/run_manager.py`
- Modify: `app.py`

- [x] **Step 1: `app.py` session 默认**

`defaults` 增加：

```python
"question_image": None,
```

- [x] **Step 2: `try_start_run_job` 校验**

在 API Key 校验之后：

```python
from utils.config import is_multimodal_model
from utils.question_input import question_input_conflict

image = st.session_state.get("question_image")
if question_input_conflict(question, image):
    st.error("请只保留文字或图片其中一种输入方式。")
    return False
if image and not is_multimodal_model(st.session_state.provider, st.session_state.model):
    st.error("当前模型不支持识图，请在侧边栏选择带 👁 支持识图 的模型。")
    return False
if image and not (question or "").strip():
    question = "[图片题目]"  # job 占位，Stage1 后替换
```

`run_job` dict 增加 `"question_image": image`（可 JSON-serializable dict，勿存 bytes）。

- [x] **Step 3: Stage 1 完成后更新 question**

在 `advance_run_job` / Stage1 完成分支（写入 state 处）：

```python
from utils.parsers import format_image_question_for_history

if job.get("question_image") and state.stage1:
    state.question = format_image_question_for_history(state.stage1.structured_json)
    job["question"] = state.question
    st.session_state.question = state.question
    st.session_state.last_question = state.question
```

Stage1 API 调用处传入 `question_image=job.get("question_image")`。

- [x] **Step 4: 手动 smoke + pytest**

Run: `python -m pytest tests/ -q --ignore=tests/e2e`

- [x] **Step 5: Commit**

```bash
git add ui/run_manager.py app.py
git commit -m "feat: 运行前识图校验与 Stage1 后题目回填"
```

---

### Task 7: 新建页 UI（上传 / 互斥 / 提示）

**Files:**
- Modify: `ui/new_page.py`
- Modify: `styles/custom.css`（可选 `.question-image-preview` 缩略图样式）

- [x] **Step 1: 在 `render_new_analysis` 题目区**

`text_area` 下方增加：

```python
uploaded = st.file_uploader(
    "或上传题目图片（jpg/png，单张）",
    type=["jpg", "jpeg", "png"],
    key="question_image_uploader",
    label_visibility="collapsed",
)
if uploaded is not None:
    try:
        from utils.question_input import compress_uploaded_image
        st.session_state.question_image = {
            "mime": "image/jpeg",
            "b64": compress_uploaded_image(uploaded.getvalue(), filename=uploaded.name).b64,
            "name": uploaded.name,
        }
    except ValueError as e:
        st.error(str(e))
        st.session_state.question_image = None

if st.session_state.get("question_image"):
    st.image(f"data:image/jpeg;base64,{st.session_state.question_image['b64']}", width=280)
    if st.button("清除图片", key="clear_question_image"):
        st.session_state.question_image = None
        st.rerun()
    st.caption("已上传图片，请选用侧边栏带 👁 支持识图 的模型。")

if question_input_conflict(question, st.session_state.get("question_image")):
    st.error("请只保留文字或图片其中一种输入方式。")
```

- [x] **Step 2: 运行按钮 guard**

在 `clicked_mode` / `try_start_run_job` 调用前，若 `question_input_conflict` 为真则 `return`（不启动）。

- [x] **Step 3: 清空结果时清图**

`clear_checkpoint` 或新建页清空逻辑同步 `question_image = None`（若已有 clear 入口）。

- [x] **Step 4: Commit**

```bash
git add ui/new_page.py styles/custom.css
git commit -m "feat: 新建页题目图片上传 UI"
```

---

### Task 8: 文档与 spec 状态

**Files:**
- Modify: `docs/USAGE.md`
- Modify: `docs/superpowers/specs/2026-06-17-question-image-upload-design.md`

- [ ] **Step 1: USAGE 增加小节**

「图片识题」：二选一、👁 模型、历史不存原图。

- [ ] **Step 2: spec 状态改为「已实现」或「已批准→实现中」**

- [ ] **Step 3: Commit**

```bash
git add docs/USAGE.md docs/superpowers/specs/2026-06-17-question-image-upload-design.md docs/superpowers/plans/2026-06-17-question-image-upload.md
git commit -m "docs: 题目图片上传用法与实现计划"
```

---

### Task 9: 全量验证

- [ ] **Step 1: pytest**

Run: `python -m pytest tests/ -q --ignore=tests/e2e`

Expected: 全绿

- [ ] **Step 2: AppTest 冒烟（可选）**

Run: `python -m pytest tests/e2e/test_smoke_app.py -q`

- [ ] **Step 3: 本地手动**

1. 上传图片 + 选 gpt-4o → Stage 1 可跑  
2. 图+文同时 → 报错  
3. deepseek-v4-pro + 图 → 报错提示换 👁 模型  

---

## Plan Self-Review

| Spec 要求 | 对应 Task |
|-----------|-----------|
| 图片/文字二选一 | Task 2, 6, 7 |
| 单图、压缩 | Task 2, 7 |
| Stage 1 发图 | Task 3, 5, 6 |
| 👁 白名单 + 新模型 | Task 1 |
| 历史仅文字 | Task 4, 6 |
| 会话缩略图 | Task 7 |
| 测试 | Task 1–4, 9 |

无 TBD 占位；类型 `QuestionImage` / dict 与 session 存 dict 一致。

---
