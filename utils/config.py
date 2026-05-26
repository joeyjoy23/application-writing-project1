import os
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

PROVIDER_OPTIONS = ["deepseek", "openai", "gemini", "dashscope", "mimo"]

PROVIDER_LABELS = {
    "deepseek": "DeepSeek",
    "openai": "OpenAI",
    "gemini": "Google Gemini",
    "dashscope": "阿里云百炼",
    "mimo": "小米 MiMo（OpenAI 兼容）",
}

PROVIDER_API_KEY_ENV = {
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "mimo": "MIMO_API_KEY",
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
    "mimo": (
        "MIMO_BASE_URL",
        "https://token-plan-cn.xiaomimimo.com/v1",
    ),
}

PROVIDER_DEFAULT_MODEL = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "dashscope": "qwen-plus",
    "mimo": "mimo-v2.5-pro",
}

# 图片识题用的视觉模型（与各厂商 OpenAI 兼容视觉接口对应）
PROVIDER_VISION_MODELS = {
    "deepseek": "deepseek-chat",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "dashscope": "qwen-vl-max",
    "mimo": "mimo-v2.5-pro",
}

# API 模型 ID 须小写连字符，见 https://platform.xiaomimimo.com/docs/zh-CN/tokenplan/quick-access
MIMO_MODEL_LABELS: dict[str, str] = {
    "mimo-v2.5-pro": "mimo-v2.5-pro · MiMo 旗舰（Agent / 编程）",
    "mimo-v2.5": "mimo-v2.5 · 全模态 Agent",
    "mimo-v2.5-flash": "mimo-v2.5-flash · 轻量高速",
}

# 旧版误写的展示名 → 官方 API ID
MIMO_MODEL_ALIASES: dict[str, str] = {
    "MiMo-V2.5-Pro": "mimo-v2.5-pro",
    "MiMo-V2.5": "mimo-v2.5",
    "MiMo-V2.5-Flash": "mimo-v2.5-flash",
}


def normalize_mimo_model_id(model: str) -> str:
    """将侧边栏 / .env 中的模型名规范为 MiMo API 接受的 ID。"""
    m = (model or "").strip()
    if not m:
        return PROVIDER_DEFAULT_MODEL["mimo"]
    if m in MIMO_MODEL_LABELS:
        return m
    if m in MIMO_MODEL_ALIASES:
        return MIMO_MODEL_ALIASES[m]
    lower = m.lower()
    for api_id in MIMO_MODEL_LABELS:
        if api_id.lower() == lower:
            return api_id
    # 任意含 mimo + v2.5 + pro 的误写
    if "mimo" in lower and "v2.5" in lower and "pro" in lower:
        return "mimo-v2.5-pro"
    if "mimo" in lower and "flash" in lower:
        return "mimo-v2.5-flash"
    if "mimo" in lower and "v2.5" in lower:
        return "mimo-v2.5"
    return PROVIDER_DEFAULT_MODEL["mimo"]


def resolve_model_for_provider(provider: str, model: str) -> str:
    """按提供商规范化模型 ID（调用 API 前最后一道校验）。"""
    p = (provider or "").lower()
    m = (model or "").strip()
    if p == "mimo":
        return normalize_mimo_model_id(m)
    return m or PROVIDER_DEFAULT_MODEL.get(p, "gpt-4o-mini")

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
    "mimo": list(MIMO_MODEL_LABELS.keys()),
}


def format_model_label(provider: str, model_id: str) -> str:
    """侧边栏下拉展示名；百炼 / MiMo 用中文说明，其它提供商显示原始 ID。"""
    if provider == "dashscope":
        return DASHSCOPE_MODEL_LABELS.get(model_id, model_id)
    if provider == "mimo":
        return MIMO_MODEL_LABELS.get(model_id, model_id)
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


def _config_value(key: str, default: str = "") -> str:
    """Streamlit Cloud Secrets 优先，其次 .env / 环境变量（网页与本地通用）。"""
    try:
        if hasattr(st, "secrets") and key in st.secrets:
            val = str(st.secrets[key]).strip()
            if val:
                return val
    except Exception:
        pass
    _load_env()
    return (os.getenv(key) or default).strip()


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
    """侧边栏手动 Key 优先，否则读 Secrets / .env。"""
    if manual_key.strip():
        return _require_ascii("API Key", manual_key)
    env_name = PROVIDER_API_KEY_ENV.get(provider.lower(), "OPENAI_API_KEY")
    key = _config_value(env_name, "")
    if key:
        return _require_ascii("API Key", key)
    fallback = _config_value("OPENAI_API_KEY", "")
    return _require_ascii("API Key", fallback) if fallback else ""


@st.cache_data(ttl=300, show_spinner=False)
def build_settings(
    provider: str,
    api_key: str = "",
    model: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
    _settings_rev: str = "20260526-mimo-cloud-v4",
) -> Settings:
    """根据网页选择的提供商与 Key 构建 API 配置（可缓存，参数须为可序列化值）。"""
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
        _config_value(url_env, url_default),
    )

    # 侧边栏 model 优先；网页用户常在侧边栏选模型，不用 .env
    raw_model = (
        model.strip()
        or _config_value("LLM_MODEL", "")
        or _config_value("OPENAI_MODEL", "")
        or PROVIDER_DEFAULT_MODEL[p]
    )
    resolved_model = _require_ascii(
        "模型名称",
        resolve_model_for_provider(p, raw_model),
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


def apply_pending_llm_selection() -> None:
    """在侧边栏 widget 创建前应用历史载入等写入的待同步 provider/model。"""
    if not hasattr(st, "session_state"):
        return
    pending_p = st.session_state.pop("_pending_provider", None)
    pending_m = st.session_state.pop("_pending_model", None)
    if pending_p in PROVIDER_OPTIONS:
        st.session_state.provider = pending_p
    if pending_m is not None and str(pending_m).strip():
        prov = st.session_state.get("provider", "deepseek")
        st.session_state.model = resolve_model_for_provider(prov, str(pending_m).strip())


def sync_session_llm_selection() -> None:
    """每次页面加载校正 provider/model（修复网页 session 缓存旧 MiMo 模型名）。"""
    if not hasattr(st, "session_state"):
        return
    prov = _config_value("LLM_PROVIDER", st.session_state.get("provider", "deepseek"))
    prov = prov.lower()
    if prov not in PROVIDER_OPTIONS:
        prov = st.session_state.get("provider", "deepseek")
    st.session_state.provider = prov

    raw_model = st.session_state.get("model") or _config_value("LLM_MODEL", "")
    fixed = resolve_model_for_provider(prov, raw_model)
    prev = st.session_state.get("model")
    if fixed != prev:
        st.session_state.model = fixed
        try:
            build_settings.clear()
        except Exception:
            pass
        if prov == "mimo" and prev and prev != fixed:
            try:
                st.toast(f"网页端已自动将模型改为 {fixed}", icon="ℹ️")
            except Exception:
                pass


def get_settings() -> Settings:
    """从环境变量构建配置（无 UI 时使用）。"""
    provider = _config_value("LLM_PROVIDER", "openai").lower()
    if provider not in PROVIDER_OPTIONS:
        provider = "openai"
    return build_settings(provider)


def get_project_root() -> Path:
    return _PROJECT_ROOT
