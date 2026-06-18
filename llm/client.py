import logging
import os
import time
from collections.abc import Callable
from typing import Any

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from llm.usage import ChatResponse, ChatUsage
from utils.config import (
    Settings,
    agnes_api_model_id,
    agnes_enable_thinking,
    get_settings,
    resolve_model_for_provider,
)

_logger = logging.getLogger("app.llm")


class RunCancelled(RuntimeError):
    """用户切换模型/提供商或主动取消当前 API 请求。"""


# ── 重试配置 ──

def _max_retries() -> int:
    """API 调用最大重试次数（不含首次尝试），可通过 LLM_MAX_RETRIES 环境变量覆盖。"""
    return max(0, int(os.getenv("LLM_MAX_RETRIES", "3")))


def _retry_base_delay() -> float:
    """重试基础延迟（秒），实际延迟 = base * 2^attempt，可通过 LLM_RETRY_BASE_DELAY 覆盖。"""
    return max(0.5, float(os.getenv("LLM_RETRY_BASE_DELAY", "2")))


def _is_retryable(exc: BaseException) -> bool:
    """判断异常是否值得重试。"""
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        return True
    return False


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


_STREAM_USAGE_PROVIDERS = frozenset(
    {"deepseek", "openai", "gemini", "dashscope", "mimo", "zhipu"}
)


def _delta_stream_text(delta: Any) -> tuple[str, str]:
    """Return (content, reasoning_content) from a streaming delta."""
    content = getattr(delta, "content", None) or ""
    reasoning = getattr(delta, "reasoning_content", None) or ""
    return content, reasoning


class LLMClient:
    """OpenAI 兼容 API 客户端（默认流式，保持 Streamlit 连接活跃）。"""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._http = httpx.Client(timeout=_api_timeout(), trust_env=True)
        self._client = OpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url.rstrip("/"),
            max_retries=0,
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
        if self.settings.provider == "agnes":
            api_model = agnes_api_model_id(self.settings.model)
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
        if self.settings.provider == "agnes" and agnes_enable_thinking(
            self.settings.model
        ):
            kwargs["extra_body"] = {
                "chat_template_kwargs": {"enable_thinking": True},
            }

        retries = _max_retries()
        base_delay = _retry_base_delay()

        for attempt in range(retries + 1):
            # 每次尝试前检查取消信号
            if should_cancel and should_cancel():
                raise RunCancelled("已切换模型或提供商，当前请求已停止。")

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
            except RunCancelled:
                raise
            except UnicodeEncodeError as e:
                raise RuntimeError(
                    "请求编码失败：请确认 API Key、Base URL、模型名均为纯英文/数字，"
                    ".env 中不要与中文写在同一行。原始错误: "
                    f"{e}"
                ) from e
            except (APITimeoutError, APIConnectionError, APIStatusError, RateLimitError) as e:
                if _is_retryable(e) and attempt < retries:
                    delay = base_delay * (2 ** attempt)
                    _logger.warning(
                        "API 调用失败（%s），%d/%d 次重试，%.1f 秒后重试…",
                        type(e).__name__, attempt + 1, retries, delay,
                    )
                    time.sleep(delay)
                    continue
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
        idle_limit = float(os.getenv("STREAM_IDLE_TIMEOUT_SECONDS", "180"))
        first_chunk_limit = float(os.getenv("STREAM_FIRST_CHUNK_TIMEOUT_SECONDS", "120"))
        report_every = int(os.getenv("STREAM_UI_UPDATE_CHARS", "40"))
        stream_kwargs = {**kwargs, "stream": True}
        if (
            os.getenv("ENABLE_STREAM_USAGE", "1").strip().lower() not in ("0", "false")
            and self.settings.provider in _STREAM_USAGE_PROVIDERS
        ):
            stream_kwargs["stream_options"] = {"include_usage": True}

        stream_resp = self._client.chat.completions.create(**stream_kwargs)
        parts: list[str] = []
        total = 0
        last_report = 0
        last_activity = time.monotonic()
        started_at = last_activity
        saw_stream_activity = False
        usage = ChatUsage()
        finish_reason: str | None = None
        ended_by_idle = False

        for chunk in stream_resp:
            if should_cancel and should_cancel():
                raise RunCancelled("已切换模型或提供商，当前请求已停止。")
            chunk_usage = parse_usage_from_response(chunk)
            if chunk_usage.prompt_tokens or chunk_usage.completion_tokens:
                usage = chunk_usage

            now = time.monotonic()
            if not saw_stream_activity and now - started_at > first_chunk_limit:
                raise RuntimeError(
                    f"已超过 {int(first_chunk_limit)} 秒未收到模型任何输出。"
                    "请检查：① 网络与代理 ② API Key ③ 侧边栏换一个更快模型"
                    "（如 qwen-plus、deepseek-v4-pro、deepseek-v4-flash）。"
                )

            if not chunk.choices:
                if saw_stream_activity and now - last_activity > idle_limit:
                    ended_by_idle = True
                    break
                continue

            choice = chunk.choices[0]
            content, reasoning = _delta_stream_text(choice.delta)
            if reasoning:
                saw_stream_activity = True
                last_activity = now

            if choice.finish_reason:
                finish_reason = choice.finish_reason
                if content:
                    parts.append(content)
                    total += len(content)
                break

            if not content:
                if saw_stream_activity and now - last_activity > idle_limit:
                    ended_by_idle = True
                    break
                continue

            saw_stream_activity = True
            parts.append(content)
            total += len(content)
            last_activity = now
            if on_stream and (last_report == 0 or total - last_report >= report_every):
                on_stream(content, total, "".join(parts))
                last_report = total

        if on_stream:
            on_stream("", total, "".join(parts))
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("模型返回空内容（流式）")
        if finish_reason == "length":
            raise RuntimeError(
                "模型输出达到 max_tokens 上限被截断（常见于 Stage1 篇幅较长）。"
                "请重试 Stage 1，或在 .env 增大 OPENAI_MAX_TOKENS / 换更长输出的模型。"
            )
        if ended_by_idle and not finish_reason:
            raise RuntimeError(
                f"流式输出已中断：超过 {int(idle_limit)} 秒未收到新内容，"
                "结果可能不完整（如构思维度写到一半）。"
                "请重试；若模型较慢，可在 .env 增大 STREAM_IDLE_TIMEOUT_SECONDS。"
            )
        return text, usage
