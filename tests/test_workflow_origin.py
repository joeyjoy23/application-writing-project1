"""换模型后是否应重跑 workflow 的判定。"""

from services.workflow_origin import llm_selection_mismatch, resolved_llm


def test_resolved_llm_normalizes_deepseek_alias():
    p, m = resolved_llm("deepseek", "deepseek-chat")
    assert p == "deepseek"
    assert m == "deepseek-v4-pro"


def test_llm_selection_mismatch_when_model_changes():
    assert llm_selection_mismatch(
        "deepseek",
        "deepseek-v4-pro",
        "zhipu",
        "glm-5.1",
    )


def test_llm_selection_mismatch_false_when_same_model():
    assert not llm_selection_mismatch(
        "deepseek",
        "deepseek-v4-pro",
        "deepseek",
        "deepseek-v4-pro",
    )


def test_llm_selection_mismatch_false_without_origin():
    assert not llm_selection_mismatch(None, None, "deepseek", "deepseek-v4-pro")
