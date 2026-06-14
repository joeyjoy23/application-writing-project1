"""历史列表 AppTest：表头与收藏/删除列。"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]


def _smoke_api_session(at: AppTest) -> None:
    at.session_state["provider"] = "deepseek"
    at.session_state["api_key"] = "smoke-test-api-key"
    at.session_state["_browser_keys_hydrated"] = True


@pytest.mark.e2e
def test_history_list_table_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    """历史列表表头含收藏/删除，且星标按钮 key 在独立列。"""
    sample = [
        {
            "id": 99,
            "created_at": "2026-06-02 11:57:33",
            "topic": "测试题目摘要",
            "model_name": "deepseek-v4-pro",
            "stages_mask": "1000",
            "word_count": 100,
            "is_starred": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_tokens": 0,
        }
    ]

    monkeypatch.setattr("ui.new_page.get_all_records", lambda *a, **k: sample)
    monkeypatch.setattr("ui.new_page.count_records", lambda *a, **k: 1)

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    _smoke_api_session(at)
    at.session_state["app_mode"] = "历史"
    at.run(timeout=60)
    assert not at.exception
    md_blob = "\n".join(m.value for m in at.markdown if m.value)
    assert "收藏" in md_blob
    assert "删除" in md_blob
    assert any(getattr(b, "key", "") == "hist_star_99" for b in at.button)
    assert any(getattr(b, "key", "") == "hist_del_99" for b in at.button)
