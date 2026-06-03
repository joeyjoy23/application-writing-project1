"""各 Stage 的 Streamlit 展示与占位刷新。"""

from __future__ import annotations

import base64
import html as html_module
import re

import streamlit as st

from services.workflow_progress import stage_has_content
from utils.parsers import (
    normalize_vertical_spacing,
    prettify_stage_markdown,
    sanitize_llm_html_breaks,
    strip_reader_self_check,
)
from workflow import WorkflowState

FOLD_CHAR_THRESHOLD = 5000
FOLD_PREVIEW_CHARS = 1000

_VOCAB_SECTION_RE = re.compile(
    r"#\s*二[、.．]?\s*话题词汇锦囊",
    re.IGNORECASE,
)
_LEVEL_HEADING_RE = re.compile(
    r"^\s*(?:#{1,4}\s*)?\*{0,2}(必备级|进阶级|亮点级)\*{0,2}\s*[:：]?\s*$"
)
_EXAMPLE_LINE_RE = re.compile(r"^\s*\*{0,2}具体使用例句\*{0,2}")
_VOCAB_ITEM_ZH_RE = re.compile(
    r"^\*{0,2}([^*]+?)\*{0,2}\s*/\s*\*{0,2}中文\*{0,2}\s*[:：]\s*(.+)$"
)
_COLON_LABEL_RE = re.compile(r"[：:]")


def render_stage_markdown(text: str) -> None:
    """Stage 分析正文（统一排版预处理）。"""
    if not text or not text.strip():
        return
    st.markdown(_format_stage_body(text))


def render_foldable_markdown(text: str, *, expanded: bool = False) -> None:
    """超过阈值时折叠：外侧预览 + expander 内全文；expanded=True 时默认展开。"""
    if not text or not text.strip():
        return
    body = _format_stage_body(text)
    if len(text) <= FOLD_CHAR_THRESHOLD:
        st.markdown(body)
        return
    if expanded:
        st.markdown(body)
        return
    st.markdown(body[:FOLD_PREVIEW_CHARS])
    st.caption(f"共 {len(text)} 字，点击展开查看完整内容")
    with st.expander("查看完整内容", expanded=False):
        st.markdown(body)


def _split_stage3_vocab_section(raw: str) -> tuple[str, str]:
    m = _VOCAB_SECTION_RE.search(raw)
    if not m:
        return raw.strip(), ""
    return raw[: m.start()].strip(), raw[m.start() :].strip()


def _detect_vocab_level(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("|"):
        return None
    m = _LEVEL_HEADING_RE.match(stripped)
    if m:
        return m.group(1)
    plain = re.sub(r"^#+\s*", "", stripped).strip("* ").strip()
    if plain in ("必备级", "进阶级", "亮点级"):
        return plain
    return None


def _parse_vocab_bullet(line: str) -> tuple[str, str | None] | None:
    text = re.sub(r"^[-*+]\s+", "", line.strip())
    if not text or _EXAMPLE_LINE_RE.match(text):
        return None
    m = _VOCAB_ITEM_ZH_RE.match(text)
    if m:
        eng = m.group(1).strip()
        zh = m.group(2).strip()
        zh = re.split(r"\*{0,2}具体使用例句", zh, maxsplit=1)[0].strip(" /")
        return eng, zh or None
    if "**" in text:
        eng = re.sub(r"\*+", "", text.split("/")[0]).strip()
        if eng:
            return eng, None
    cleaned = text.strip()
    return (cleaned, None) if cleaned else None


def _parse_vocab_tiers(vocab_text: str) -> dict[str, list[tuple[str, str | None]]]:
    tiers: dict[str, list[tuple[str, str | None]]] = {
        "必备级": [],
        "进阶级": [],
        "亮点级": [],
    }
    current: str | None = None
    for line in vocab_text.splitlines():
        level = _detect_vocab_level(line)
        if level:
            current = level
            continue
        if not current:
            continue
        if line.strip().startswith(("-", "*", "+")):
            item = _parse_vocab_bullet(line)
            if item:
                tiers[current].append(item)
    return tiers


def _render_vocab_tier_table(
    title: str, rows: list[tuple[str, str | None]]
) -> None:
    if not rows:
        return
    st.markdown(f"#### {title}")
    has_zh = any(zh for _, zh in rows if zh)
    if has_zh:
        table_data = [["英文词块", "中文释义"]]
        table_data.extend([[eng, zh or ""] for eng, zh in rows])
    else:
        table_data = [["英文词块"]]
        table_data.extend([[eng] for eng, _ in rows])
    st.table(table_data)


def _render_vocab_tier_tables(vocab_text: str) -> bool:
    tiers = _parse_vocab_tiers(vocab_text)
    if not any(tiers.values()):
        return False
    for title in ("必备级", "进阶级", "亮点级"):
        _render_vocab_tier_table(title, tiers[title])
    return True


def _bold_label_in_line(line: str) -> str:
    m = _COLON_LABEL_RE.search(line)
    if not m:
        return line
    idx = m.start()
    before = line[:idx]
    colon = line[idx]
    after = line[idx + 1 :]
    if "**" in before:
        return line
    prefix_m = re.match(r"^(\s*(?:[-*+]\s+|\d+[.、]\s+)?)(.*?)\s*$", before)
    if not prefix_m:
        return line
    prefix = prefix_m.group(1)
    label = prefix_m.group(2).strip()
    if not label:
        return line
    if re.fullmatch(r"[#*_~`]+", label):
        return line
    # 短标签整段加粗；较长标签仅加粗冒号前核心词（避免整段过黑）
    if len(label) <= 28:
        return f"{prefix}**{label}**{colon}{after}"
    core = label[:24].rstrip("，、；; ")
    rest = label[len(core) :]
    return f"{prefix}**{core}**{rest}{colon}{after}"


def _format_stage_body(text: str) -> str:
    """展示前：Markdown 整理 → 加粗标签 → 列表合并/去空行 → 段落空行。"""
    from utils.parsers import merge_list_item_continuations, normalize_list_spacing

    body = prettify_stage_markdown(text)
    body = bold_labels_before_colon(body)
    body = merge_list_item_continuations(body)
    body = normalize_list_spacing(body)
    return normalize_vertical_spacing(body)


@st.cache_data(show_spinner=False)
def bold_labels_before_colon(text: str) -> str:
    if not text:
        return text
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if re.match(r"^\s*(#{1,6}\s|```|>\||\||---|[-*_]{3,})", line):
            out.append(line)
        else:
            out.append(_bold_label_in_line(line))
    return "\n".join(out)


def markdown_to_html(text: str) -> str:
    text = html_module.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^(#{1,6})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{m.group(2)}</h{level}>")
            i += 1
            continue
        m = re.match(r"^-\s+(.+)$", line)
        if m:
            out.append("<ul>")
            while i < len(lines):
                m2 = re.match(r"^-\s+(.+)$", lines[i])
                if not m2:
                    break
                out.append(f"<li>{m2.group(1)}</li>")
                i += 1
            out.append("</ul>")
            continue
        m = re.match(r"^\d+\.\s+(.+)$", line)
        if m:
            out.append("<ol>")
            while i < len(lines):
                m2 = re.match(r"^\d+\.\s+(.+)$", lines[i])
                if not m2:
                    break
                out.append(f"<li>{m2.group(1)}</li>")
                i += 1
            out.append("</ol>")
            continue
        if not line.strip():
            out.append("<br>")
            i += 1
            continue
        out.append(f"<p>{line}</p>")
        i += 1
    return "\n".join(out)


def render_copy_button(text: str) -> None:
    html_content = markdown_to_html(text)
    html_b64 = base64.b64encode(html_content.encode("utf-8")).decode("ascii")
    plain_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    component = f"""
    <button class="copy-btn" onclick="
        var hb='{html_b64}',pb='{plain_b64}';
        var h=(new TextDecoder).decode(Uint8Array.from(atob(hb),function(c){{return c.charCodeAt(0)}}));
        var p=(new TextDecoder).decode(Uint8Array.from(atob(pb),function(c){{return c.charCodeAt(0)}}));
        var i=new ClipboardItem({{'text/html':new Blob([h],{{type:'text/html'}}),'text/plain':new Blob([p],{{type:'text/plain'}})}});
        navigator.clipboard.write([i]).then(function(){{this.textContent='✅ 已复制';var b=this;setTimeout(function(){{b.textContent='📋 一键复制'}},2000)}}.bind(this)).catch(function(){{this.textContent='复制失败'}}.bind(this));
    ">
        📋 一键复制
    </button>
    """
    st.components.v1.html(component, height=42)


def render_stage1(state: WorkflowState) -> None:
    with st.container(border=True):
        st.markdown(
            '<span class="stage-badge stage-1">Stage 1</span> '
            '<span class="stage-title">审题结构分析</span>',
            unsafe_allow_html=True,
        )
        if not state.stage1:
            st.info("尚未运行 Stage 1")
            return
        s1 = state.stage1
        reader_summary = strip_reader_self_check(s1.human_summary)
        if reader_summary.strip():
            render_foldable_markdown(reader_summary)
        else:
            st.info("暂无审题总结内容")
        if reader_summary.strip():
            render_copy_button(reader_summary)


def render_stage2(state: WorkflowState) -> None:
    with st.container(border=True):
        st.markdown(
            '<span class="stage-badge stage-2">Stage 2</span> '
            '<span class="stage-title">PEEL 写作策略卡与多版范文</span>',
            unsafe_allow_html=True,
        )
        if not state.stage2:
            st.info("尚未运行 Stage 2（需先完成 Stage 1）")
            return
        render_stage_markdown(strip_reader_self_check(state.stage2.raw or ""))


def render_stage3(state: WorkflowState) -> None:
    with st.container(border=True):
        st.markdown(
            '<span class="stage-badge stage-3">Stage 3</span> '
            '<span class="stage-title">功能句型包与话题词汇</span>',
            unsafe_allow_html=True,
        )
        if not state.stage3:
            st.info("尚未运行 Stage 3（需先完成 Stage 1）")
            return
        raw = sanitize_llm_html_breaks(state.stage3.raw or "")
        phrases_part, vocab_part = _split_stage3_vocab_section(raw)
        if phrases_part:
            render_stage_markdown(phrases_part)
        if vocab_part:
            st.markdown("### 话题词汇锦囊")
            if not _render_vocab_tier_tables(vocab_part):
                render_stage_markdown(vocab_part)
        elif not phrases_part:
            render_stage_markdown(raw)
        render_copy_button(raw)


def render_stage4(state: WorkflowState) -> None:
    with st.container(border=True):
        st.markdown(
            '<span class="stage-badge stage-4">Stage 4</span> '
            '<span class="stage-title">教学指南与易错预警</span>',
            unsafe_allow_html=True,
        )
        if not state.stage4:
            st.info("尚未运行 Stage 4（需先完成 Stage 2 与 Stage 3）")
            return
        render_stage_markdown(state.stage4.raw or "")
        render_copy_button(state.stage4.raw)


_STAGE_RENDERERS = {
    1: render_stage1,
    2: render_stage2,
    3: render_stage3,
    4: render_stage4,
}

_STAGE_WAITING = {
    1: "尚未运行 Stage 1",
    2: "尚未运行 Stage 2（需先完成 Stage 1）",
    3: "尚未运行 Stage 3（需先完成 Stage 1）",
    4: "尚未运行 Stage 4（需先完成 Stage 2 与 Stage 3）",
}

_STAGE_BADGE_TITLES = {
    1: '<span class="stage-badge stage-1">Stage 1</span> <span class="stage-title">审题结构分析</span>',
    2: '<span class="stage-badge stage-2">Stage 2</span> <span class="stage-title">PEEL 写作策略卡与多版范文</span>',
    3: '<span class="stage-badge stage-3">Stage 3</span> <span class="stage-title">功能句型包与话题词汇</span>',
    4: '<span class="stage-badge stage-4">Stage 4</span> <span class="stage-title">教学指南与易错预警</span>',
}


def render_one_stage(slot: st.empty, state: WorkflowState, stage_num: int) -> None:
    with slot.container():
        if stage_num > 1:
            st.markdown('<hr class="stage-divider">', unsafe_allow_html=True)
        _STAGE_RENDERERS[stage_num](state)


def render_stage_placeholder(slot: st.empty, stage_num: int) -> None:
    with slot.container():
        if stage_num > 1:
            st.markdown('<hr class="stage-divider">', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(_STAGE_BADGE_TITLES[stage_num], unsafe_allow_html=True)
            st.info(_STAGE_WAITING[stage_num])


def render_stage_in_progress(slot: st.empty, stage_num: int) -> None:
    """后台 API 进行中：保留已完成阶段，当前阶段显示「生成中」。"""
    with slot.container():
        if stage_num > 1:
            st.markdown('<hr class="stage-divider">', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(_STAGE_BADGE_TITLES[stage_num], unsafe_allow_html=True)
            st.info(
                f"Stage {stage_num} 正在生成中，请稍候…"
                "（下方「运行状态」可查看实时字数）"
            )


def sync_slots_from_state(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
    *,
    running_stages: set[int] | None = None,
) -> None:
    """刷新各 Stage 占位；running_stages 用于标记 API 进行中的阶段。"""
    running = running_stages or set()
    for n, slot in enumerate(slots, start=1):
        if stage_has_content(state, n):
            render_one_stage(slot, state, n)
        elif n in running:
            render_stage_in_progress(slot, n)
        else:
            render_stage_placeholder(slot, n)


def render_all_stages(
    state: WorkflowState,
    slots: tuple[st.empty, st.empty, st.empty, st.empty],
) -> None:
    sync_slots_from_state(state, slots)
