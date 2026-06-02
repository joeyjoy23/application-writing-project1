import os

from workflow import _STAGE_MAX_TOKENS_DEFAULT, stage_max_tokens


def test_stage_max_tokens_defaults():
    assert stage_max_tokens(1) == _STAGE_MAX_TOKENS_DEFAULT[1]
    assert stage_max_tokens(2) == 8192
    assert stage_max_tokens(3) == 6144
    assert stage_max_tokens(4) == 6144


def test_stage_max_tokens_env_override(monkeypatch):
    monkeypatch.setenv("STAGE1_MAX_TOKENS", "10240")
    assert stage_max_tokens(1) == 10240
