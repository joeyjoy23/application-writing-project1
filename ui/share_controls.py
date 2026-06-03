"""生成并展示只读分享链接（新建页 / 历史详情共用）。"""

from __future__ import annotations

import streamlit as st

from db import ensure_guest_id, using_postgres
from services.share_links import (
    create_or_refresh_share_link,
    get_active_share_url,
    get_app_base_url,
)
from utils.share_util import build_share_url, share_ttl_days


def ensure_history_record_id(state) -> int | None:
    """返回当前备课包对应的历史 ID（必要时静默保存）。"""
    from ui.history import auto_save_history

    rid = st.session_state.get("current_history_record_id")
    if rid:
        return int(rid)
    if not state or not getattr(state, "stage1", None):
        return None
    new_id = auto_save_history(state, notify=False)
    if new_id:
        st.session_state.current_history_record_id = int(new_id)
        return int(new_id)
    return None


def render_share_controls(history_id: int | None, *, key_prefix: str = "share") -> None:
    if history_id is None:
        return
    st.markdown(
        '<div class="share-section">'
        '<div class="share-section-title">'
        '<svg viewBox="0 0 16 16" fill="currentColor">'
        '<path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM11.5 8a3.5 3.5 0 11-7 0 3.5 3.5 0 017 0z"/>'
        '</svg>分享预览</div>',
        unsafe_allow_html=True,
    )
    if not using_postgres():
        st.caption("分享功能需在 Streamlit Cloud 配置 DATABASE_URL（Neon）后使用。")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    base = get_app_base_url()
    if not base:
        st.warning(
            "请在 Streamlit Secrets 或环境变量中设置 **APP_BASE_URL** "
            "（你的应用完整地址，如 `https://xxx.streamlit.app`），才能生成可分享的链接。"
        )
        st.markdown("</div>", unsafe_allow_html=True)
        return

    owner_id = ensure_guest_id()
    cache_key = f"{key_prefix}_url_{history_id}"
    url = st.session_state.get(cache_key)
    if not url:
        url = get_active_share_url(history_id, owner_id=owner_id, base_url=base)

    btn_key = f"{key_prefix}_gen_{history_id}"
    if st.button(
        "🔗 生成分享链接" if not url else "🔄 刷新分享内容",
        key=btn_key,
        use_container_width=True,
        help=f"生成只读预览链接，{share_ttl_days()} 天内有效；不含 Word/JSON 下载",
    ):
        token = create_or_refresh_share_link(history_id, owner_id=owner_id)
        if token:
            url = build_share_url(token, base)
            st.session_state[cache_key] = url
            st.toast("分享链接已生成，请复制后发微信", icon="🔗")
            st.rerun()
        else:
            st.error("无法生成分享链接，请确认记录已保存且仍存在于历史中。")

    if url:
        st.text_input(
            "分享链接（复制后发微信）",
            value=url,
            label_visibility="collapsed",
            key=f"{key_prefix}_input_{history_id}",
        )
        st.caption(
            f"只读预览 · {share_ttl_days()} 天有效 · 无下载按钮 · 仅供查阅"
        )
    else:
        st.caption("点击上方按钮生成链接；对方在微信中打开即可预览备课包。")

    st.markdown("</div>", unsafe_allow_html=True)
