"""侧边栏：模式切换、API 设置、断点缓存管理。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from db import (
    admin_password_configured,
    count_records,
    ensure_guest_id,
    history_scope,
    invalidate_history_cache,
    is_history_admin,
    logout_admin,
    try_admin_login,
    using_postgres,
)
from utils.config import (
    PROVIDER_LABELS,
    PROVIDER_MODELS,
    PROVIDER_OPTIONS,
    build_settings,
    format_model_label,
    normalize_deepseek_model_id,
    normalize_mimo_model_id,
    normalize_zhipu_model_id,
)
from utils.config import resolve_api_key
from services.workflow_progress import stage_has_content
from ui.sidebar_nav import render_stage_index_nav
from workflow import WorkflowState


# ── 侧栏顶栏（工作区 + << 同一行）──


def render_sidebar_workspace_topbar() -> None:
    st.markdown(
        '<div class="sidebar-workspace-row">'
        '<span class="sidebar-workspace-title">📂 工作区</span>'
        "</div>",
        unsafe_allow_html=True,
    )


def inject_sidebar_collapse_dock() -> None:
    """将 << 移入工作区行（主区零高 iframe，避免侧栏双滚动条）。"""
    components.html(
        """
<script>
(function () {
  function doc() {
    try { return window.parent.document; } catch (e) { return document; }
  }
  function dock() {
    const d = doc();
    const row = d.querySelector(".sidebar-workspace-row");
    const btn = d.querySelector('[data-testid="stSidebarCollapseButton"]');
    if (!row || !btn || row.contains(btn)) return;
    row.appendChild(btn);
    btn.style.cssText =
      "position:static!important;top:auto!important;right:auto!important;" +
      "left:auto!important;margin:0 0 0 auto!important;flex-shrink:0;" +
      "transform:none!important;height:auto!important;min-height:0!important;";
    const hdr = d.querySelector('[data-testid="stSidebarHeader"]');
    if (hdr) hdr.style.display = "none";
  }
  dock();
  setTimeout(dock, 50);
  setTimeout(dock, 200);
})();
</script>
        """,
        height=0,
        scrolling=False,
    )


# ── session_state 读写工具 ──


def clear_run_job() -> None:
    """清除运行状态（不删除已生成的阶段结果）。"""
    st.session_state.run_job = None
    st.session_state.is_running = False
    st.session_state.run_cancelled = False


def api_key_configured() -> bool:
    return bool(resolve_api_key(st.session_state.provider, st.session_state.api_key))


def clear_checkpoint() -> None:
    """清除所有断点续传缓存，回到初始状态。"""
    st.session_state.workflow_state = None
    st.session_state.last_question = ""
    st.session_state.failed_stage = None
    st.session_state._confirm_clear = False
    st.toast("已清除缓存，可重新开始", icon="🔄")


# ── 侧边栏回调 ──


def _on_settings_changed() -> None:
    """侧边栏切换提供商/模型时，若正在运行则取消当前 API。"""
    job = st.session_state.get("run_job")
    if not st.session_state.get("is_running") or not job:
        return
    if (
        st.session_state.provider != job["locked_provider"]
        or st.session_state.model != job["locked_model"]
    ):
        job["cancel_event"].set()
        st.session_state.run_cancelled = True


# 界面版本号：部署后可在侧边栏底部核对是否已更新
UI_BUILD_TAG = "2026.06.04-index-pad"


def _render_admin_popover_body() -> None:
    """Popover 内：口令登录 / 退出维护视图。"""
    if is_history_admin():
        st.caption("当前为维护视图（可见全部历史）")
        if st.button("退出", key="btn_admin_logout", use_container_width=True):
            logout_admin()
            invalidate_history_cache()
            st.rerun()
        return

    pwd = st.text_input(
        "口令",
        type="password",
        key="admin_pwd_input",
        label_visibility="collapsed",
        placeholder="输入口令",
    )
    if st.button("确认", key="btn_admin_login", use_container_width=True):
        if try_admin_login(pwd):
            invalidate_history_cache()
            st.rerun()
        else:
            st.error("口令无效")


def _render_admin_popover_trigger() -> None:
    """历史条数右侧「⋯」，点开输入口令（需已配置 ADMIN_PASSWORD）。"""
    if not admin_password_configured():
        return
    with st.popover("⋯"):
        _render_admin_popover_body()


# ── 渲染 ──


def render_sidebar() -> bool:
    """渲染侧边栏；返回 True 表示 API 已配置。"""
    with st.sidebar:
        render_sidebar_workspace_topbar()
        api_ready = True

        with st.container(border=True):
            st.markdown(
                '<div class="sidebar-section-label sidebar-mode-head" role="heading" '
                'aria-level="3">模式</div>',
                unsafe_allow_html=True,
            )
            mode_options = ["新建", "历史"]
            current_mode = st.session_state.get("app_mode", "新建")
            if current_mode == "新建分析":
                current_mode = "新建"
            if current_mode == "查看历史":
                current_mode = "历史"
            mode_index = (
                mode_options.index(current_mode) if current_mode in mode_options else 0
            )
            st.session_state.app_mode = st.selectbox(
                "app_mode_select",
                mode_options,
                index=mode_index,
                label_visibility="collapsed",
                help="新建：输入题目并运行备课流程；历史：查看、搜索、导出已保存的备课包",
            )
            ensure_guest_id()
            owner_id, admin = history_scope()
            try:
                total_hist = count_records("", owner_id, admin)
                cloud_hint = " · 云端" if using_postgres() else ""
                hist_left, hist_right = st.columns([5, 1])
                with hist_left:
                    st.caption(f"历史记录：共 {total_hist} 条{cloud_hint}")
                with hist_right:
                    _render_admin_popover_trigger()
            except Exception:
                pass

            if st.session_state.app_mode == "历史":
                if st.button("刷新历史列表", use_container_width=True):
                    st.session_state.history_page = 1
                    st.rerun()

        with st.container(border=True):
            st.markdown(
                '<div class="sidebar-section-label sidebar-api-head" role="heading" '
                'aria-level="3">API 设置</div>',
                unsafe_allow_html=True,
            )

            st.checkbox(
                "使用 LLM 结果缓存（同题同模型可跳过 API）",
                help="命中缓存时直接载入该阶段结果；修改 prompts 目录后自动失效。",
                key="use_llm_cache",
            )

            if st.session_state.is_running:
                st.caption("运行中切换模型将**自动停止**当前请求，请重新点击 Stage。")
                if st.button("停止当前运行", use_container_width=True, key="btn_stop_run"):
                    job = st.session_state.get("run_job")
                    if job:
                        job["cancel_event"].set()
                    st.session_state.run_cancelled = True
                    clear_run_job()
                    st.warning("已停止。请确认模型后重新点击 Stage。")
                    st.rerun()

            st.selectbox(
                "模型提供商",
                options=PROVIDER_OPTIONS,
                format_func=lambda p: PROVIDER_LABELS.get(p, p),
                index=PROVIDER_OPTIONS.index(
                    st.session_state.provider
                    if st.session_state.provider in PROVIDER_OPTIONS
                    else "deepseek"
                ),
                key="provider",
                on_change=_on_settings_changed,
                help="支持 OpenAI 兼容接口的常用服务；运行中切换会停止当前请求",
            )

            model_options = PROVIDER_MODELS.get(
                st.session_state.provider, ["deepseek-v4-pro"]
            )
            current = st.session_state.model
            if st.session_state.provider == "deepseek":
                current = normalize_deepseek_model_id(current)
            if st.session_state.provider == "zhipu":
                current = normalize_zhipu_model_id(current)
            if st.session_state.provider == "mimo":
                current = normalize_mimo_model_id(current)
            if current not in model_options:
                current = model_options[0]
            st.session_state.model = current
            model_index = model_options.index(current)
            st.selectbox(
                "模型",
                options=model_options,
                index=model_index,
                format_func=lambda m: format_model_label(st.session_state.provider, m),
                key="model",
                on_change=_on_settings_changed,
                help=(
                    "百炼：最新旗舰优先排序。"
                    "运行中切换会停止当前请求。"
                    if st.session_state.provider == "dashscope"
                    else "MiMo 请选 mimo-v2.5-pro（API 只认小写 ID）。"
                    if st.session_state.provider == "mimo"
                    else "DeepSeek 官方仅 deepseek-v4-pro（chat/reasoner 已弃用）。"
                    if st.session_state.provider == "deepseek"
                    else "智谱 Key 见 open.bigmodel.cn。"
                    if st.session_state.provider == "zhipu"
                    else "运行中切换会停止当前请求"
                ),
            )

            key_label = {
                "deepseek": "DeepSeek API Key",
                "openai": "OpenAI API Key",
                "gemini": "Gemini API Key",
                "dashscope": "阿里云百炼 API Key",
                "mimo": "小米 MiMo API Key",
                "zhipu": "智谱 API Key",
            }.get(st.session_state.provider, "API Key")

            st.session_state.api_key = st.text_input(
                key_label,
                value=st.session_state.api_key,
                type="password",
                help="在上方输入 API Key 后即可使用",
            )

            if api_key_configured():
                try:
                    s = build_settings(
                        st.session_state.provider,
                        api_key=st.session_state.api_key,
                        model=st.session_state.model,
                    )
                    st.success(f"API 已配置 · {s.model}")
                    usage = st.session_state.get("llm_run_usage")
                    if usage and isinstance(usage, dict):
                        pt = int(usage.get("prompt_tokens") or 0)
                        ct = int(usage.get("completion_tokens") or 0)
                        if pt or ct:
                            st.caption(f"上次 token：{pt} / {ct}")
                    api_ready = True
                except ValueError as e:
                    msg = str(e)
                    if "未配置" not in msg and "API Key" not in msg:
                        st.error(msg)
                    api_ready = False
            else:
                api_ready = False

        with st.container(border=True):
            _ws_nav = st.session_state.get("workflow_state")
            _job_nav = st.session_state.get("run_job")
            _running_nav: set[int] = set()
            if _job_nav and _ws_nav:
                from ui.run_manager import _running_stages_for_job

                _running_nav = _running_stages_for_job(_job_nav, _ws_nav)
            render_stage_index_nav(_ws_nav, running_stages=_running_nav)

        if not api_ready:
            st.markdown(
                f'<p class="sidebar-build-tag" title="若与最新部署不一致，请在 Streamlit Cloud 执行 Reboot app">'
                f"界面 {UI_BUILD_TAG}</p>",
                unsafe_allow_html=True,
            )
            return False

        # 断点续传状态与清除缓存
        _ws = st.session_state.get("workflow_state")
        if _ws and _ws.stage1:
            _done = sum(1 for s in range(1, 5) if stage_has_content(_ws, s))
            _fail = st.session_state.get("failed_stage")
            if _fail:
                st.caption(f"断点：已完成 {_done}/4（Stage {_fail} 失败）")
            elif _done < 4:
                st.caption(f"断点：已完成 {_done}/4，可继续生成")
            if st.button("🔄 清除缓存，重新开始", use_container_width=True, key="btn_sidebar_clear_cache"):
                clear_checkpoint()
                st.rerun()

        # 运行日志查看器
        with st.expander("📋 运行日志"):
            _log_path = Path(__file__).resolve().parent.parent / "logs" / "app.log"
            if _log_path.is_file():
                _lines = _log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                _tail = _lines[-30:] if len(_lines) >= 30 else _lines
                st.text("\n".join(_tail))
                if st.button("刷新日志", key="btn_refresh_log"):
                    st.rerun()
            else:
                st.caption("暂无日志文件")

        st.markdown(
            f'<p class="sidebar-build-tag" title="若与最新部署不一致，请在 Streamlit Cloud 执行 Reboot app">'
            f"界面 {UI_BUILD_TAG}</p>",
            unsafe_allow_html=True,
        )

    return True
