import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from llm.usage import ChatResponse, ChatUsage
from utils.config import Settings, get_settings, resolve_model_for_provider


class RunCancelled(RuntimeError):
    """用户切换模型/提供商或主动取消当前 API 请求。"""


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
        elif exc.status_code in (400, 404):
            hint = " 模型名称或参数可能不正确，请在侧边栏核对模型 ID（MiMo 须为 mimo-v2.5-pro 等小写 ID）。"
        elif exc.status_code == 429:
            hint = " 请求过于频繁，请稍后重试。"
        return f"API 返回错误 {exc.status_code}{hint}\n{body}"
    return str(exc)


def parse_usage_from_response(obj: Any) -> ChatUsage:
    usage = getattr(obj, "usage", None)
    if not usage:
        return ChatUsage()
    cached = 0
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        cached = int(getattr(details, "cached_tokens", 0) or 0)
    if not cached:
        cached = int(getattr(usage, "prompt_cache_hit_tokens", 0) or 0)
    return ChatUsage(
        prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
        completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
        cached_tokens=cached,
    )


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
        self.last_usage: ChatUsage = ChatUsage()

    def chat_with_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = True,
        on_stream: Callable[[str, int, str], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> ChatResponse:
        api_model = resolve_model_for_provider(
            self.settings.provider, self.settings.model
        )
        kwargs: dict[str, Any] = dict(
            model=api_model,
            messages=messages,
            temperature=temperature
            if temperature is not None
            else self.settings.temperature,
            max_tokens=max_tokens
            if max_tokens is not None
            else self.settings.max_tokens,
        )

        try:
            if stream:
                text, usage = self._chat_stream(kwargs, on_stream, should_cancel)
            else:
                response = self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if not content:
                    raise RuntimeError("模型返回空内容")
                text = content.strip()
                usage = parse_usage_from_response(response)
            self.last_usage = usage
            return ChatResponse(text=text, usage=usage)
        except UnicodeEncodeError as e:
            raise RuntimeError(
                "请求编码失败：请确认 API Key、Base URL、模型名均为纯英文/数字，"
                ".env 中不要与中文写在同一行。原始错误: "
                f"{e}"
            ) from e
        except (APITimeoutError, APIConnectionError, APIStatusError, RateLimitError) as e:
            raise RuntimeError(format_api_error(e)) from e

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
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        return self.chat_with_messages(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            on_stream=on_stream,
            should_cancel=should_cancel,
        ).text

    def _chat_stream(
        self,
        kwargs: dict,
        on_stream: Callable[[str, int, str], None] | None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> tuple[str, ChatUsage]:
        idle_limit = float(os.getenv("STREAM_IDLE_TIMEOUT_SECONDS", "120"))
        first_chunk_limit = float(os.getenv("STREAM_FIRST_CHUNK_TIMEOUT_SECONDS", "90"))
        report_every = int(os.getenv("STREAM_UI_UPDATE_CHARS", "40"))
        stream_kwargs = {**kwargs, "stream": True}
        if os.getenv("ENABLE_STREAM_USAGE", "1").strip().lower() not in ("0", "false"):
            stream_kwargs["stream_options"] = {"include_usage": True}

        stream_resp = self._client.chat.completions.create(**stream_kwargs)
        parts: list[str] = []
        total = 0
        last_report = 0
        last_activity = time.monotonic()
        started_at = last_activity
        usage = ChatUsage()

        for chunk in stream_resp:
            if should_cancel and should_cancel():
                raise RunCancelled("已切换模型或提供商，当前请求已停止。")
            chunk_usage = parse_usage_from_response(chunk)
            if chunk_usage.prompt_tokens or chunk_usage.completion_tokens:
                usage = chunk_usage

            now = time.monotonic()
            if not parts and now - started_at > first_chunk_limit:
                raise RuntimeError(
                    f"已超过 {int(first_chunk_limit)} 秒未收到模型任何输出。"
                    "请检查：① 网络与代理 ② API Key ③ 侧边栏换一个更快模型"
                    "（如 qwen-plus、deepseek-v4-pro、deepseek-v4-flash）。"
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
        return text, usage
