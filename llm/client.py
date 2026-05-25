import base64
import os
import time
from collections.abc import Callable

import httpx


class RunCancelled(RuntimeError):
    """用户切换模型/提供商或主动取消当前 API 请求。"""
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from utils.config import Settings, get_settings


def _api_timeout() -> httpx.Timeout:
    seconds = float(os.getenv("API_READ_TIMEOUT_SECONDS", "300"))
    connect = float(os.getenv("API_CONNECT_TIMEOUT_SECONDS", "30"))
    return httpx.Timeout(connect=connect, read=seconds, write=60.0, pool=30.0)


def format_api_error(exc: BaseException) -> str:
    """将 API 异常转为用户可读说明。"""
    if isinstance(exc, APITimeoutError):
        return (
            "API 请求超时。请检查网络，或换更快模型（如 qwen-plus、deepseek-v4-flash），"
            "或在 .env 增大 API_READ_TIMEOUT_SECONDS。"
        )
    if isinstance(exc, APIConnectionError):
        return f"无法连接 API 服务器：{exc}. 请检查网络、Base URL 与代理设置。"
    if isinstance(exc, RateLimitError):
        return "API 限流，请稍后重试或更换模型/账号。"
    if isinstance(exc, APIStatusError):
        body = ""
        try:
            body = exc.response.text[:500] if exc.response else ""
        except Exception:
            pass
        hint = ""
        if exc.status_code == 401:
            hint = " API Key 无效或未授权。"
        elif exc.status_code == 404:
            hint = " 模型名称可能不正确，请在侧边栏换一个百炼模型。"
        elif exc.status_code == 429:
            hint = " 请求过于频繁，请稍后重试。"
        return f"API 返回错误 {exc.status_code}{hint}\n{body}"
    return str(exc)


class LLMClient:
    """OpenAI 兼容 API 客户端（默认流式，保持 Streamlit 连接活跃）。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._http = httpx.Client(timeout=_api_timeout(), trust_env=True)
        self._client = OpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url.rstrip("/"),
            max_retries=1,
            http_client=self._http,
        )

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = True,
        on_stream: Callable[[str, int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        kwargs = dict(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature if temperature is not None else self.settings.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.settings.max_tokens,
        )

        try:
            if stream:
                return self._chat_stream(kwargs, on_stream, should_cancel)
            response = self._client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("模型返回空内容")
            return content.strip()
        except UnicodeEncodeError as e:
            raise RuntimeError(
                "请求编码失败：请确认 API Key、Base URL、模型名均为纯英文/数字，"
                ".env 中不要与中文写在同一行。原始错误: "
                f"{e}"
            ) from e
        except (APITimeoutError, APIConnectionError, APIStatusError, RateLimitError) as e:
            raise RuntimeError(format_api_error(e)) from e

    def _chat_stream(
        self,
        kwargs: dict,
        on_stream: Callable[[str, int, str], None] | None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> str:
        idle_limit = float(os.getenv("STREAM_IDLE_TIMEOUT_SECONDS", "120"))
        first_chunk_limit = float(os.getenv("STREAM_FIRST_CHUNK_TIMEOUT_SECONDS", "90"))
        report_every = int(os.getenv("STREAM_UI_UPDATE_CHARS", "40"))
        stream_resp = self._client.chat.completions.create(stream=True, **kwargs)
        parts: list[str] = []
        total = 0
        last_report = 0
        last_activity = time.monotonic()
        started_at = last_activity

        for chunk in stream_resp:
            if should_cancel and should_cancel():
                raise RunCancelled("已切换模型或提供商，当前请求已停止。")
            now = time.monotonic()
            if not parts and now - started_at > first_chunk_limit:
                raise RuntimeError(
                    f"已超过 {int(first_chunk_limit)} 秒未收到模型任何输出。"
                    "请检查：① 网络与代理 ② API Key ③ 侧边栏换一个更快模型"
                    "（如 qwen-plus、deepseek-v4-flash、deepseek-chat）。"
                )

            if not chunk.choices:
                if parts and now - last_activity > idle_limit:
                    break
                continue

            choice = chunk.choices[0]
            delta = choice.delta.content or ""
            if choice.finish_reason:
                if delta:
                    parts.append(delta)
                    total += len(delta)
                break

            if not delta:
                if parts and now - last_activity > idle_limit:
                    break
                continue

            parts.append(delta)
            total += len(delta)
            last_activity = now
            if on_stream and (last_report == 0 or total - last_report >= report_every):
                on_stream(delta, total, "".join(parts))
                last_report = total

        if on_stream:
            on_stream("", total, "".join(parts))
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("模型返回空内容（流式）")
        return text

    def chat_with_image(
        self,
        system: str,
        user_text: str,
        image_bytes: bytes,
        *,
        mime_type: str = "image/jpeg",
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_stream: Callable[[str, int, str], None] | None = None,
    ) -> str:
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
        kwargs = dict(
            model=self.settings.model,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=temperature if temperature is not None else self.settings.temperature,
            max_tokens=max_tokens if max_tokens is not None else self.settings.max_tokens,
        )
        try:
            return self._chat_stream(kwargs, on_stream)
        except (APITimeoutError, APIConnectionError, APIStatusError, RateLimitError) as e:
            raise RuntimeError(format_api_error(e)) from e
