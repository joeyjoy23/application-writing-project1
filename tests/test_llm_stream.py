"""LLM streaming edge cases (thinking models, first-chunk timeout)."""

from unittest.mock import MagicMock, patch

import pytest

from llm.client import LLMClient, _delta_stream_text
from utils.config import build_settings


def test_delta_stream_text_reads_reasoning_content():
    delta = MagicMock(content=None, reasoning_content="thinking…")
    assert _delta_stream_text(delta) == ("", "thinking…")


def test_chat_stream_reasoning_before_content_avoids_first_chunk_timeout():
    settings = build_settings("dashscope", api_key="sk-test", model="qwen-plus")
    client = LLMClient(settings)
    client._client = MagicMock()

    def _chunk(*, content: str = "", reasoning: str = "", finish_reason=None):
        return MagicMock(
            choices=[
                MagicMock(
                    delta=MagicMock(content=content, reasoning_content=reasoning),
                    finish_reason=finish_reason,
                )
            ],
            usage=None,
        )

    stream = MagicMock()
    stream.__iter__ = MagicMock(
        return_value=iter(
            [
                _chunk(reasoning="long internal reasoning"),
                _chunk(content="final answer", finish_reason="stop"),
            ]
        )
    )
    client._client.chat.completions.create.return_value = stream

    with patch.dict("os.environ", {"STREAM_FIRST_CHUNK_TIMEOUT_SECONDS": "0.01"}):
        resp = client.chat_with_messages(
            [{"role": "user", "content": "hi"}],
            stream=True,
        )

    assert resp.text == "final answer"


def test_chat_stream_no_activity_hits_first_chunk_timeout():
    settings = build_settings("dashscope", api_key="sk-test", model="qwen-plus")
    client = LLMClient(settings)
    client._client = MagicMock()

    empty_delta = MagicMock(
        choices=[
            MagicMock(
                delta=MagicMock(content="", reasoning_content=""),
                finish_reason=None,
            )
        ],
        usage=None,
    )
    stream = MagicMock()
    stream.__iter__ = MagicMock(return_value=iter([empty_delta]))
    client._client.chat.completions.create.return_value = stream

    with (
        patch.dict(
            "os.environ",
            {
                "STREAM_FIRST_CHUNK_TIMEOUT_SECONDS": "0.01",
                "STREAM_IDLE_TIMEOUT_SECONDS": "3600",
            },
        ),
        patch("llm.client.time.monotonic", side_effect=[0.0, 0.02, 0.04]),
    ):
        with pytest.raises(RuntimeError, match="未收到模型任何输出"):
            client.chat_with_messages([{"role": "user", "content": "hi"}], stream=True)
