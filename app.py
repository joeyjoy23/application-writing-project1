"""
高考英语应用文 AI 分析系统 — Streamlit 入口
多阶段工作流，非聊天机器人。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from db import init_db
from utils.config import get_project_root

# ── 日志配置 ──

_LOGS_DIR = get_project_root() / "logs"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("app")
_logger.setLevel(logging.DEBUG)

# 文件 handler：RotatingFileHandler，5MB，保留3个备份
from logging.handlers import RotatingFileHandler

_file_handler = RotatingFileHandler(
    _LOGS_DIR / "app.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
_logger.addHandler(_file_handler)

# 控制台 handler：只显示 WARNING 及以上
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.WARNING)
_console_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
_logger.addHandler(_console_handler)


# ── 环境初始化 ──


# ── 环境初始化 ──


def _ensure_utf8_environment() -> None:
    """Windows 下避免中文环境导致 HTTP 头 ASCII 编码失败。"""
    os.environ.setdefault("PYTHONUTF8", "1")
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8")
                except Exception:
                    pass


_ensure_utf8_environment()

ROOT = get_project_root()
CSS_PATH = ROOT / "styles" / "custom.css"

load_dotenv(ROOT / ".env", encoding="utf-8")


# ── 全局初始化 ──


@st.cache_data(show_spinner=False)
def _read_css_text(css_path: str) -> str:
    """读取 CSS 文件内容（可缓存，参数为路径字符串）。"""
    path = Path(css_path)
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def load_css() -> None:
    css_text = _read_css_text(str(CSS_PATH))
    if css_text:
        st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)


def init_session() -> None:
    """集中初始化所有 session_state 默认值（其他模块通过参数接收，不重复定义）。"""
    defaults = {
        "workflow_state": None,
        "question": "",
        "is_running": False,
        "provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "model": os.getenv("LLM_MODEL", ""),
        "api_key": "",
        "uploaded_image_name": None,
        "app_mode": "新建",
        "history_view_id": None,
        "history_confirm_delete_id": None,
        "history_page": 1,
        "history_page_size": 20,
        "history_search_keyword": "",
        "_last_save_fingerprint": None,
        "run_job": None,
        "run_cancelled": False,
        "_confirm_clear": False,
        # 断点续传
        "last_question": "",
        "failed_stage": None,
        "guest_id": None,
        "is_history_admin": False,
        "_admin_gate_open": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── 主入口 ──


def main() -> None:
    st.set_page_config(
        page_title="高考英语应用文 AI 分析",
        page_icon="📝",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    load_css()
    init_session()
    init_db()
    _logger.info("应用启动")

    # 延迟导入，避免循环依赖
    from ui.sidebar import render_sidebar
    from ui.new_page import render_history_page, render_new_analysis

    api_ready = render_sidebar()

    st.title("高考英语应用文 AI 分析系统")

    # 面包屑/模式提示
    if st.session_state.app_mode == "历史":
        st.markdown(
            '<span class="mode-breadcrumb">'
            '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M4 1.75V4H1.75a.75.75 0 000 1.5H4v2.5H1.75a.75.75 0 000 1.5H4v2.75a.75.75 0 001.5 0V9.5h2.5v2.75a.75.75 0 001.5 0V9.5h2.75a.75.75 0 000-1.5H9.5V5.5h2.75a.75.75 0 000-1.5H9.5V1.75a.75.75 0 00-1.5 0V4H5.5V1.75a.75.75 0 00-1.5 0zM8 8H5.5V5.5H8V8z"/></svg>'
            '历史记录</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="mode-breadcrumb">'
            '<svg viewBox="0 0 16 16" fill="currentColor"><path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm8-3.5a.75.75 0 01.75.75v2h2a.75.75 0 010 1.5h-2v2a.75.75 0 01-1.5 0v-2h-2a.75.75 0 010-1.5h2v-2A.75.75 0 018 4.5z"/></svg>'
            '新建分析</span>',
            unsafe_allow_html=True,
        )

    if st.session_state.app_mode == "历史":
        render_history_page()
        return

    render_new_analysis(api_ready)


if __name__ == "__main__":
    main()
