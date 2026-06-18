"""LLM 结果缓存键与换模型时跳过缓存。"""

from unittest.mock import MagicMock, patch

from utils.llm_cache_keys import make_cache_key
from ui.run_cache import llm_cache_enabled, try_load_cached_stage
from workflow import WorkflowState


def test_make_cache_key_differs_by_model() -> None:
    base = dict(
        owner_id="guest-1",
        provider="deepseek",
        stage=1,
        question="同一道高考题",
        upstream_hash="",
    )
    key_a = make_cache_key(model="deepseek-v4-pro", **base)
    key_b = make_cache_key(model="glm-5.1", **base)
    assert key_a != key_b


def test_make_cache_key_differs_by_provider() -> None:
    base = dict(
        owner_id="guest-1",
        model="deepseek-v4-pro",
        stage=1,
        question="同一道高考题",
        upstream_hash="",
    )
    key_a = make_cache_key(provider="deepseek", **base)
    key_b = make_cache_key(provider="zhipu", **base)
    assert key_a != key_b


def test_llm_cache_disabled_when_job_skips_cache() -> None:
    ss = MagicMock()
    ss.get = lambda key, default=None: True if key == "use_llm_cache" else default
    job = {"skip_llm_cache": True, "locked_provider": "deepseek", "locked_model": "m"}
    with patch("ui.run_cache.st.session_state", ss):
        assert not llm_cache_enabled(job)


def test_try_load_cached_stage_skips_when_model_changed_run() -> None:
    job = {
        "skip_llm_cache": True,
        "locked_provider": "deepseek",
        "locked_model": "deepseek-v4-pro",
        "question": "q",
    }
    state = WorkflowState(question="q")
    with patch("ui.run_cache.get_cached_stage_result") as get_cached:
        assert try_load_cached_stage(job, 1, state) is None
        get_cached.assert_not_called()
