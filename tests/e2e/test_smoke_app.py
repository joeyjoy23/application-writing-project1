"""Streamlit AppTest 冒烟：主路径页面可加载、新建分析关键区块存在。"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[2]


def _smoke_api_session(at: AppTest) -> None:
    """AppTest 冒烟用：使侧边栏判定 API 已配置。"""
    at.session_state["provider"] = "deepseek"
    at.session_state["api_key"] = "smoke-test-api-key"
    at.session_state["_browser_keys_hydrated"] = True


@pytest.fixture(scope="module")
def app_run() -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    _smoke_api_session(at)
    at.run(timeout=60)
    return at


@pytest.mark.e2e
def test_app_smoke_no_exception(app_run: AppTest) -> None:
    assert not app_run.exception


@pytest.mark.e2e
def test_app_smoke_hero_and_new_analysis_mode(app_run: AppTest) -> None:
    md_blob = "\n".join(m.value for m in app_run.markdown)
    assert "高考英语应用文 AI 分析系统" in md_blob
    assert "新建分析" in md_blob
    assert "题目输入" in md_blob
    assert "完整流程" in "\n".join(b.label for b in app_run.button)


@pytest.mark.e2e
def test_app_smoke_sidebar_advanced_section_exists(app_run: AppTest) -> None:
    labels = [getattr(e, "label", "") or "" for e in app_run.expander]
    assert any("高级" in lab for lab in labels)


@pytest.mark.e2e
def test_app_smoke_stale_question_banner_with_prefilled_state() -> None:
    """换题灰显：预置 workflow 后改题目，应出现旧题提示。"""
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    _smoke_api_session(at)
    from workflow import Stage1Result, WorkflowState

    state = WorkflowState(question="旧题")
    state.stage1 = Stage1Result(raw="", structured_json={}, human_summary="审题")
    at.session_state["workflow_state"] = state
    at.session_state["last_question"] = "旧题"
    at.session_state["question"] = "新题"
    at.run(timeout=60)
    assert not at.exception
    alerts = [a.value for a in at.warning]
    assert any("旧题结果" in (msg or "") for msg in alerts)
