"""Agnes provider 配置与 API 请求参数。"""

from unittest.mock import MagicMock, patch

import pytest

from llm.client import LLMClient
from utils.config import (
    AGNES_API_MODEL,
    PROVIDER_OPTIONS,
    agnes_api_model_id,
    agnes_enable_thinking,
    build_settings,
    format_model_label,
    normalize_agnes_model_id,
    resolve_model_for_provider,
)


def test_agnes_in_provider_options():
    assert "agnes" in PROVIDER_OPTIONS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", "agnes-2.0-flash"),
        ("agnes-2.0-flash", "agnes-2.0-flash"),
        ("agnes-2.0-flash-thinking", "agnes-2.0-flash-thinking"),
        ("AGNES-2.0-FLASH-THINKING", "agnes-2.0-flash-thinking"),
        ("agnes-brainstorm", "agnes-2.0-flash-thinking"),
    ],
)
def test_normalize_agnes_model_id(raw: str, expected: str):
    assert normalize_agnes_model_id(raw) == expected


def test_agnes_api_model_and_thinking():
    assert agnes_api_model_id("agnes-2.0-flash-thinking") == AGNES_API_MODEL
    assert agnes_enable_thinking("agnes-2.0-flash") is False
    assert agnes_enable_thinking("agnes-2.0-flash-thinking") is True


def test_resolve_model_for_provider_agnes():
    assert resolve_model_for_provider("agnes", "agnes-2.0-flash-thinking") == (
        "agnes-2.0-flash-thinking"
    )


def test_format_model_label_agnes():
    label = format_model_label("agnes", "agnes-2.0-flash-thinking")
    assert "Brainstorming" in label


def test_build_settings_agnes():
    with patch("utils.config.st") as mock_st:
        mock_st.secrets = {}
        settings = build_settings(
            "agnes",
            api_key="sk-test-agnes",
            model="agnes-2.0-flash-thinking",
        )
    assert settings.provider == "agnes"
    assert settings.model == "agnes-2.0-flash-thinking"
    assert settings.base_url == "https://apihub.agnes-ai.com/v1"


def test_llm_client_agnes_thinking_extra_body():
    settings = build_settings(
        "agnes",
        api_key="sk-test-agnes",
        model="agnes-2.0-flash-thinking",
    )
    client = LLMClient(settings)
    client._client = MagicMock()
    stream = MagicMock()
    stream.__iter__ = MagicMock(
        return_value=iter(
            [
                MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(content="ok"),
                            finish_reason="stop",
                        )
                    ],
                    usage=None,
                )
            ]
        )
    )
    client._client.chat.completions.create.return_value = stream

    client.chat_with_messages([{"role": "user", "content": "hi"}], stream=True)

    call_kwargs = client._client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == AGNES_API_MODEL
    assert call_kwargs["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": True},
    }
