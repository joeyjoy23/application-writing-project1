"""从真题图片中识别应用文题目文字（视觉模型）。"""

from __future__ import annotations

import base64
from dataclasses import replace

from llm.client import LLMClient
from utils.config import PROVIDER_VISION_MODELS, Settings, build_settings

OCR_SYSTEM_PROMPT = """你是高考英语试卷题目识别助手。
你的唯一任务是从图片中准确转录文字，不做分析、不做解答。"""

OCR_USER_PROMPT = """请完整识别这张图片中的「高考英语应用文」写作题目。

要求：
1. 按阅读顺序输出全部可见文字（中文题干、英文要求、要点编号、词数要求等）
2. 保留原有层次：可用换行分段，要点用列表或编号
3. 只输出识别到的题目原文，不要加「识别结果」等标题，不要分析、不要写作文
4. 看不清的字用 [?] 标注；图中无题目内容时只输出：未识别到题目文字
"""


def _mime_for_upload(type_hint: str | None, filename: str | None) -> str:
    if type_hint and type_hint.startswith("image/"):
        return type_hint
    if filename:
        ext = filename.rsplit(".", 1)[-1].lower()
        return {
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "webp": "image/webp",
            "gif": "image/gif",
        }.get(ext, "image/jpeg")
    return "image/jpeg"


MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB，过大易导致浏览器/Streamlit 卡顿


def extract_question_from_image(
    image_bytes: bytes,
    *,
    settings: Settings,
    mime_type: str | None = None,
    filename: str | None = None,
) -> str:
    """使用当前 API 的视觉模型识别题目，返回纯文本。"""
    if not image_bytes:
        raise ValueError("图片为空")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("图片过大（超过 8MB），请压缩后重试")

    mime = _mime_for_upload(mime_type, filename)
    vision_model = PROVIDER_VISION_MODELS.get(settings.provider, settings.model)
    vision_settings = replace(settings, model=vision_model)
    client = LLMClient(vision_settings)

    text = client.chat_with_image(
        system=OCR_SYSTEM_PROMPT,
        user_text=OCR_USER_PROMPT,
        image_bytes=image_bytes,
        mime_type=mime,
        temperature=0.2,
        max_tokens=2048,
    )
    cleaned = text.strip()
    if not cleaned or cleaned == "未识别到题目文字":
        raise ValueError("未能从图片中识别到题目，请换一张更清晰的照片或改用文字输入")
    return cleaned


def extract_question_from_image_with_ui_settings(
    image_bytes: bytes,
    provider: str,
    *,
    api_key: str = "",
    model: str = "",
    mime_type: str | None = None,
    filename: str | None = None,
) -> str:
    settings = build_settings(provider, api_key=api_key, model=model)
    return extract_question_from_image(
        image_bytes,
        settings=settings,
        mime_type=mime_type,
        filename=filename,
    )
