"""主内容区底部 Joyverse 标识。"""

from __future__ import annotations

import streamlit as st


def render_page_footer() -> None:
    st.markdown(
        '<div class="page-footer-joyverse" aria-label="Joyverse">'
        '<span class="page-footer-joyverse__brand">Joyverse</span>'
        "</div>",
        unsafe_allow_html=True,
    )
