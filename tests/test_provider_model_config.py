"""DeepSeek / 智谱 provider 模型配置与规范化。"""

import pytest

from utils.config import (
    DEEPSEEK_MODEL_LABELS,
    PROVIDER_MODELS,
    ZHIPU_MODEL_LABELS,
    format_model_label,
    normalize_deepseek_model_id,
    normalize_zhipu_model_id,
    resolve_model_for_provider,
)


def test_deepseek_v4_flash_in_provider_models():
    assert "deepseek-v4-flash" in PROVIDER_MODELS["deepseek"]
    assert "deepseek-v4-flash" in DEEPSEEK_MODEL_LABELS


def test_zhipu_glm_5_2_in_provider_models():
    assert "glm-5.2" in PROVIDER_MODELS["zhipu"]
    assert "glm-5.2" in ZHIPU_MODEL_LABELS


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("deepseek-v4-flash", "deepseek-v4-flash"),
        ("DeepSeek-V4-Flash", "deepseek-v4-flash"),
        ("deepseek-chat", "deepseek-v4-pro"),
        ("deepseek-reasoner", "deepseek-v4-pro"),
        ("deepseek-v4-pro", "deepseek-v4-pro"),
    ],
)
def test_normalize_deepseek_model_id(raw: str, expected: str):
    assert normalize_deepseek_model_id(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("glm-5.2", "glm-5.2"),
        ("GLM-5.2", "glm-5.2"),
        ("glm-5.1", "glm-5.1"),
        ("glm-4.7", "glm-4.7"),
    ],
)
def test_normalize_zhipu_model_id(raw: str, expected: str):
    assert normalize_zhipu_model_id(raw) == expected


def test_resolve_model_for_provider_new_models():
    assert resolve_model_for_provider("deepseek", "deepseek-v4-flash") == (
        "deepseek-v4-flash"
    )
    assert resolve_model_for_provider("zhipu", "glm-5.2") == "glm-5.2"


def test_format_model_label_new_models():
    assert "高效" in format_model_label("deepseek", "deepseek-v4-flash")
    assert "旗舰" in format_model_label("zhipu", "glm-5.2")
