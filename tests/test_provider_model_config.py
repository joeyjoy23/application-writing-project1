"""DeepSeek / 智谱 provider 模型配置与规范化。"""

import pytest

from utils.config import (
    DASHSCOPE_MODEL_LABELS,
    DEEPSEEK_MODEL_LABELS,
    MULTIMODAL_MODELS,
    PROVIDER_MODELS,
    ZHIPU_MODEL_LABELS,
    format_model_label,
    is_multimodal_model,
    normalize_deepseek_model_id,
    normalize_zhipu_model_id,
    recommended_image_models_text,
    resolve_model_for_provider,
    supports_question_image_upload,
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


def test_multimodal_whitelist():
    expected = {
        ("openai", "gpt-4o"),
        ("openai", "gpt-4o-mini"),
        ("openai", "gpt-4.1-mini"),
        ("gemini", "gemini-2.0-flash"),
        ("gemini", "gemini-2.5-flash-preview-05-20"),
        ("dashscope", "qwen3.7-plus"),
        ("dashscope", "qwen3.6-plus"),
        ("zhipu", "glm-4.6v"),
        ("zhipu", "glm-4.6v-flash"),
        ("mimo", "mimo-v2.5"),
        ("agnes", "agnes-2.0-flash"),
        ("agnes", "agnes-2.0-flash-thinking"),
    }
    assert MULTIMODAL_MODELS == frozenset(expected)
    for provider, model_id in expected:
        assert is_multimodal_model(provider, model_id) is True
    assert is_multimodal_model("deepseek", "deepseek-v4-pro") is False
    assert is_multimodal_model("zhipu", "glm-5.1") is False
    assert is_multimodal_model("dashscope", "qwen-plus") is False
    assert is_multimodal_model("dashscope", "kimi-k2.6") is False


def test_question_image_upload_support():
    assert supports_question_image_upload("openai", "gpt-4o") is True
    assert supports_question_image_upload("dashscope", "qwen3.7-plus") is True
    assert supports_question_image_upload("zhipu", "glm-4.6v-flash") is True
    assert supports_question_image_upload("dashscope", "kimi-k2.6") is False
    assert supports_question_image_upload("deepseek", "deepseek-v4-pro") is False
    assert "gpt-4o" in recommended_image_models_text()


def test_new_vision_models_in_provider_lists():
    assert "glm-4.6v" in PROVIDER_MODELS["zhipu"]
    assert "glm-4.6v-flash" in PROVIDER_MODELS["zhipu"]
    assert "glm-4.6v" in ZHIPU_MODEL_LABELS
    assert "glm-4.6v-flash" in ZHIPU_MODEL_LABELS
    assert "qwen3.7-plus" in PROVIDER_MODELS["dashscope"]
    assert "qwen3.6-plus" in PROVIDER_MODELS["dashscope"]
    assert "qwen3.7-plus" in DASHSCOPE_MODEL_LABELS
    assert "qwen3.6-plus" in DASHSCOPE_MODEL_LABELS
    assert "glm-5.2" in PROVIDER_MODELS["zhipu"]
    assert "qwen-plus" in PROVIDER_MODELS["dashscope"]


def test_format_model_label_vision_suffix():
    suffix = " · 👁 支持识图"
    assert format_model_label("openai", "gpt-4o").endswith(suffix)
    assert format_model_label("zhipu", "glm-4.6v-flash").endswith(suffix)
    assert format_model_label("dashscope", "qwen3.7-plus").endswith(suffix)
    assert format_model_label("mimo", "mimo-v2.5").endswith(suffix)
    assert suffix not in format_model_label("deepseek", "deepseek-v4-pro")
    assert suffix not in format_model_label("zhipu", "glm-5.1")
    assert suffix not in format_model_label("dashscope", "qwen-plus")
