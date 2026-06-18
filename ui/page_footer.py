"""主内容区底部 Joyverse 出品标识。"""

from __future__ import annotations

import streamlit as st


def render_page_footer() -> None:
    st.markdown(
        '<div class="page-footer-joyverse" aria-label="出品方">'
        '<span class="page-footer-joyverse__brand">Joyverse</span>'
        '<span class="page-footer-joyverse__hint">出品</span>'
        "</div>",
        unsafe_allow_html=True,
    )
