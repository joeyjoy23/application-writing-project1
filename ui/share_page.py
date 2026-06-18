"""分享令牌只读预览页（?share=token）。"""

from __future__ import annotations

import json

import streamlit as st

from db import format_stages_mask, init_db, using_postgres
from services.share_links import fetch_public_share
from services.workflow_storage import resolve_raw_input, workflow_state_from_json
from ui.stage_display import render_all_stages
from utils.datetime_util import format_created_at_display
from utils.share_util import share_ttl_days


def _query_share_token() -> str | None:
    raw = st.query_params.get("share")
    if isinstance(raw, list):
        return (raw[0] if raw else None) or None
    return (raw or "").strip() or None


def render_share_page() -> None:
    # Route marker for share-only CSS (hide sidebar / GitHub chrome).
    st.markdown(
        '<div class="share-preview-route" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    token = _query_share_token()
    if not token:
        st.error("缺少分享参数")
        return

    if not using_postgres():
        st.error("分享预览仅支持云端部署。")
        return

    try:
        init_db()
    except Exception as exc:
        st.error(f"服务暂不可用：{exc}")
        return

    row = fetch_public_share(token)
    if not row:
        st.error("链接无效、已过期或已被撤销。")
        st.caption(f"分享链接有效期为 {share_ttl_days()} 天。")
        return

    try:
        data = json.loads(row["snapshot_json"])
    except json.JSONDecodeError:
        st.error("分享内容损坏，无法展示。")
        return

    raw = resolve_raw_input(
        {
            "raw_input": "",
            "full_content": row["snapshot_json"],
            "topic": row.get("topic") or "",
        },
        data,
    )
    if not raw and data.get("raw_input"):
        raw = str(data["raw_input"])
    if not raw and data.get("question"):
        raw = str(data["question"])
    state = workflow_state_from_json(row["snapshot_json"], raw_input=raw)
    if not state.stage1:
        st.error("分享内容不完整。")
        return

    st.markdown(
        '<div class="share-preview-hero">'
        '<div class="share-preview-title">备课包预览</div>'
        '<div class="share-preview-subtitle">只读 · 不可下载</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"题目摘要：{row.get('topic') or '—'} · "
        f"模型：{row.get('model_name') or '—'} · "
        f"阶段：{format_stages_mask(row.get('stages_mask'))} · "
        f"分享于 {format_created_at_display(row.get('created_at'))}（北京时间） · "
        f"有效期至 {format_created_at_display(row.get('expires_at'))}"
    )

    if raw:
        st.markdown("#### 题目")
        st.text_area(
            "题目",
            value=raw,
            height=min(200, max(100, len(raw) // 5)),
            disabled=True,
            label_visibility="collapsed",
            key="share_preview_question",
        )

    st.divider()
    s1, s2, s3, s4 = st.empty(), st.empty(), st.empty(), st.empty()
    render_all_stages(state, (s1, s2, s3, s4))

    st.divider()
    st.caption(
        "本页仅供预览，不提供 Word / JSON 导出。"
        "请勿截图外传教研内容。"
    )
