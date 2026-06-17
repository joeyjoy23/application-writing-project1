"""题目输入：图片压缩、互斥校验、历史摘要拼接（无 Streamlit 依赖）。"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any

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
    try:
        from PIL import Image
    except ImportError as exc:
        raise ImportError(
            "图片压缩需要 Pillow 库。请确认 requirements.txt 已包含 Pillow 并已重新部署应用。"
        ) from exc
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError(f"图片超过 {MAX_UPLOAD_BYTES // (1024 * 1024)}MB 限制")
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
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    name = filename if filename.lower().endswith((".jpg", ".jpeg")) else "question.jpg"
    return QuestionImage(mime="image/jpeg", b64=b64, name=name)
