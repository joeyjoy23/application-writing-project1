import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

PROVIDER_OPTIONS = ["deepseek", "openai", "gemini", "dashscope"]

PROVIDER_LABELS = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "dashscope": "阿里云百炼",
}

PROVIDER_API_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
}

PROVIDER_BASE_URL = {
    "deepseek": ("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
    "openai": ("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    "gemini": (
        "GEMINI_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai/",
    ),
    "dashscope": (
        "DASHSCOPE_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
}

PROVIDER_DEFAULT_MODEL = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "dashscope": "qwen-plus",
}

# 图片识题用的视觉模型（与各厂商 OpenAI 兼容视觉接口对应）
PROVIDER_VISION_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "dashscope": "qwen-vl-max",
}

# 阿里云百炼侧边栏模型（API 模型 ID → 展示名称）
DASHSCOPE_MODEL_LABELS: dict[str, str] = {
    "qwen3.6-max-preview": "qwen3.6-max-preview · 千问旗舰（复杂推理）",
    "qwen-plus": "qwen-plus · 千问均衡（性能/成本）",
    "glm-5.1": "GLM-5.1 · 智谱旗舰",
    "MiniMax-M2.7": "MiniMax-M2.7 · MiniMax 最新",
    "kimi-k2.6": "Kimi K2.6 · 月之暗面最新",
    "deepseek-v4-pro": "DeepSeek-V4-Pro · DeepSeek 旗舰",
    "deepseek-v4-flash": "DeepSeek-V4-Flash · DeepSeek 高效",
    "qwen3-next-80b-a3b": "Qwen3-Next-80B-A3B · 千问高性价比 MoE",
}

PROVIDER_MODELS: dict[str, list[str]] = {
    "deepseek": ["deepseek-chat", "deepseek-reasoner"],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    "gemini": ["gemini-2.0-flash", "gemini-2.5-flash-preview-05-20"],
    "dashscope": list(DASHSCOPE_MODEL_LABELS.keys()),
}


def format_model_label(provider: str, model_id: str) -> str:
    """侧边栏下拉展示名；百炼用中文说明，其它提供商显示原始 ID。"""
    if provider == "dashscope":
        return DASHSCOPE_MODEL_LABELS.get(model_id, model_id)
    return model_id


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    provider: str = "openai"


def _load_env() -> None:
    load_dotenv(_ENV_PATH, encoding="utf-8")


def _clean_env_value(value: str) -> str:
    """去掉首尾空白、引号、BOM，并截断行内 # 注释误粘贴。"""
    value = value.strip().strip('"').strip("'")
    if value.startswith("\ufeff"):
        value = value[1:]
    if " #" in value:
        value = value.split(" #", 1)[0].strip()
    return value


def _require_ascii(field_name: str, value: str) -> str:
    """API Key / URL / 模型名必须为 ASCII，避免请求头编码报错。"""
    value = _clean_env_value(value)
    if not value:
        return value
    try:
        value.encode("ascii")
    except UnicodeEncodeError as exc:
        preview = repr(value[:24])
        raise ValueError(
            f"{field_name} 只能包含英文字母、数字和常见符号，不能含中文或全角字符。"
            f"请检查侧边栏或 .env（当前值开头: {preview}）。\n"
            "正确示例：DASHSCOPE_API_KEY=sk-xxxxxxxx（注释另起一行写 # ...）"
        ) from exc
    return value


def resolve_api_key(provider: str, manual_key: str = "") -> str:
    """侧边栏手动 Key 优先，否则读对应环境变量，最后回退 OPENAI_API_KEY。"""
    if manual_key.strip():
        return _require_ascii("API Key", manual_key)
    _load_env()
    env_name = PROVIDER_API_KEY_ENV.get(provider.lower(), "OPENAI_API_KEY")
    key = os.getenv(env_name, "")
    if key:
        return _require_ascii("API Key", key)
    fallback = os.getenv("OPENAI_API_KEY", "")
    return _require_ascii("API Key", fallback) if fallback else ""


def build_settings(
    provider: str,
    *,
    api_key: str = "",
    model: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Settings:
    """根据网页选择的提供商与 Key 构建 API 配置。"""
    _load_env()
    p = provider.lower()
    if p not in PROVIDER_OPTIONS:
        raise ValueError(f"不支持的提供商: {provider}")

    resolved_key = resolve_api_key(p, api_key)
    if not resolved_key:
        label = PROVIDER_LABELS.get(p, p)
        env_hint = PROVIDER_API_KEY_ENV[p]
        raise ValueError(
            f"未配置 {label} API Key。请在侧边栏输入，或在 .env 中设置 {env_hint}。"
        )

    url_env, url_default = PROVIDER_BASE_URL[p]
    base_url = _require_ascii(
        "API Base URL",
        os.getenv(url_env, url_default),
    )

    resolved_model = _require_ascii(
        "模型名称",
        model.strip()
        or os.getenv("LLM_MODEL", "").strip()
        or os.getenv("OPENAI_MODEL", "").strip()
        or PROVIDER_DEFAULT_MODEL[p],
    )

    return Settings(
        api_key=resolved_key,
        base_url=base_url,
        model=resolved_model,
        temperature=temperature
        if temperature is not None
        else float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
        max_tokens=max_tokens
        if max_tokens is not None
        else int(os.getenv("OPENAI_MAX_TOKENS", "4096")),
        provider=p,
    )


def get_settings() -> Settings:
    """从环境变量构建配置（无 UI 时使用）。"""
    _load_env()
    provider = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    if provider not in PROVIDER_OPTIONS:
        provider = "openai"
    return build_settings(provider)


def get_project_root() -> Path:
    return _PROJECT_ROOT
