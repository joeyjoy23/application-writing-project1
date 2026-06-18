import json
import re
from typing import Any


JSON_MARKER = "===STRUCTURED_JSON==="
SUMMARY_MARKER = "===HUMAN_READABLE_SUMMARY==="

_PART_B_SPLIT = re.compile(
    r"#?\s*PART\s*B[：:]\s*HUMAN_READABLE_SUMMARY\s*",
    re.IGNORECASE,
)

# 读者可见正文不展示「输出前自检」块（模型若仍输出则在此剥除）
_SELF_CHECK_SECTION = re.compile(
    r"(?:^|\n)#{1,3}\s*(?:7[\.\s、]*)?输出前自检[^\n]*\n[\s\S]*\Z",
    re.IGNORECASE | re.MULTILINE,
)

_HTML_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


_CN_MAJOR_SECTION = re.compile(
    r"^(\s*)([一二三四五六七八九十百千]+[、．.])\s*(.+)$"
)
_CN_BRACKET_SECTION = re.compile(r"^(\s*)【([^】]{2,48})】\s*$")
_CN_PAREN_SECTION = re.compile(
    r"^(\s*)[（(]([一二三四五六七八九十\d]+)[)）]\s*(.+)$"
)


def promote_section_headings(text: str) -> str:
    """将「一、」「【节名】」等提升为 Markdown 标题，强化页面层级。"""
    if not text or not text.strip():
        return text
    out: list[str] = []
    for line in text.split("\n"):
        raw = line
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("```"):
            out.append(raw)
            continue
        if stripped.startswith("|") or set(stripped) <= {"-", "*", "_"}:
            out.append(raw)
            continue

        m_br = _CN_BRACKET_SECTION.match(stripped)
        if m_br:
            indent = raw[: len(raw) - len(raw.lstrip())]
            out.append(f"{indent}### 【{m_br.group(2)}】")
            continue

        m_major = _CN_MAJOR_SECTION.match(stripped)
        if m_major and len(m_major.group(3)) <= 72:
            indent = raw[: len(raw) - len(raw.lstrip())]
            out.append(
                f"{indent}### {m_major.group(2)}{m_major.group(3).strip()}"
            )
            continue

        m_sub = _CN_PAREN_SECTION.match(stripped)
        if m_sub and len(m_sub.group(3)) <= 64:
            indent = raw[: len(raw) - len(raw.lstrip())]
            out.append(f"{indent}#### （{m_sub.group(2)}）{m_sub.group(3).strip()}")
            continue

        out.append(raw)
    return "\n".join(out)


_DIM_NUM = r"[1-9１-９]"
_DIM_HEAD = re.compile(rf"维度({_DIM_NUM})(?:（可选）)?[：:]\s*")
_DIM_ARROW = re.compile(
    r"^(?P<name>[^→\n]+?)"
    r"\s*→\s*(?P<focus>[^→\n]+?)"
    r"\s*→\s*适用[：:]\s*(?P<apply>[^→\n]+?)"
    r"\s*→\s*💡(?:思路发散示例)?[：:]\s*(?P<example>.+)\Z",
    re.DOTALL,
)
_DIM_INLINE_BOUNDARY = re.compile(
    rf"(?<=[。；!？?])\s*(?=维度{_DIM_NUM}(?:（可选）)?[：:])"
)
_DIM_TIGHT_BOUNDARY = re.compile(
    r"(?<=\S)\s+(?=维度[2-9](?:（可选）)?[：:])"
)


def _split_dimension_chunks(text: str) -> list[tuple[str, str]]:
    matches = list(_DIM_HEAD.finditer(text))
    if not matches:
        return []
    chunks: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        num = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunks.append((num, text[start:end].strip()))
    return chunks


def _format_apply_points(raw: str) -> str:
    apply = raw.strip()
    bracket = re.match(r"要点?\[([^\]]+)\]", apply)
    if bracket:
        return bracket.group(1).replace(",", "、").replace("，", "、")
    apply = re.sub(r"^要点[：:]?\s*", "", apply)
    return apply.strip("[] ")


def _format_single_dimension(num: str, body: str) -> str:
    body = body.strip()
    matched = _DIM_ARROW.match(body)
    if matched:
        name = matched.group("name").strip()
        focus = matched.group("focus").strip()
        apply = _format_apply_points(matched.group("apply"))
        example = matched.group("example").strip()
        return (
            f"#### 维度{num} · {name}\n\n"
            f"- **切入点**：{focus}\n"
            f"- **适用要点**：{apply}\n"
            f"- **💡 思路发散**：{example}"
        )

    parts = [p.strip() for p in body.split("→") if p.strip()]
    if len(parts) >= 2:
        name = parts[0]
        lines = [f"#### 维度{num} · {name}", ""]
        labels = ("切入点", "适用要点", "💡 思路发散")
        for idx, part in enumerate(parts[1:], start=0):
            label = labels[idx] if idx < len(labels) else "补充"
            if label == "适用要点" or part.startswith("适用"):
                part = _format_apply_points(part)
            elif "思路发散" in part:
                part = re.sub(r"^💡(?:思路发散示例)?[：:]\s*", "", part)
            lines.append(f"- **{label}**：{part}")
        return "\n".join(lines)

    return f"#### 维度{num}\n\n- {body}"


def format_construction_dimensions(text: str) -> str:
    """将 §5 构思维度从单行箭头串改为分层 Markdown 块。"""
    if not text or not re.search(rf"维度{_DIM_NUM}", text):
        return text

    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or not re.search(rf"维度{_DIM_NUM}", stripped):
            out.append(line)
            continue

        body = re.sub(r"^[-*•]\s+", "", stripped)
        body = _DIM_INLINE_BOUNDARY.sub("\n\n", body)
        body = _DIM_TIGHT_BOUNDARY.sub("\n\n", body)
        chunks = _split_dimension_chunks(body)
        if not chunks:
            out.append(line)
            continue
        out.append("\n\n".join(_format_single_dimension(num, chunk) for num, chunk in chunks))

    return "\n".join(out)


_LABEL_LINE = re.compile(
    r"^(\s*)(?:[-*+]\s+)?\*\*[^*]+?\*\*\s*[：:]"
)
_BOLD_PAIR_RE = re.compile(r"\*\*([^*\n]+?)\*\*")
_BOLD_OPEN_LABEL_RE = re.compile(r"\*\*\s+([^：:\n*]+?)([：:])")


def normalize_bold_markers(text: str) -> str:
    """Fix LLM bold like ``** 标签**`` / ``** 标签：`` so Markdown renders."""
    if not text or "**" not in text:
        return text
    cleaned = _BOLD_PAIR_RE.sub(
        lambda m: f"**{m.group(1).strip()}**",
        text,
    )
    return _BOLD_OPEN_LABEL_RE.sub(r"**\1**\2", cleaned)
_HEADING_LINE = re.compile(r"^\s*#{1,6}\s")
_LIST_LINE = re.compile(r"^\s*[-*+]\s")


def normalize_vertical_spacing(text: str) -> str:
    """统一列表、加粗标签行与正文之间的空行，避免段落间距忽大忽小。"""
    lines = text.split("\n")
    out: list[str] = []
    prev: str = "start"

    def _kind(s: str) -> str:
        if _HEADING_LINE.match(s):
            return "heading"
        if _LIST_LINE.match(s):
            return "list"
        if _LABEL_LINE.match(s):
            return "label"
        return "text"

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            prev = "blank"
            continue

        kind = _kind(stripped)
        need_gap = prev not in ("start", "blank") and (
            (prev == "list" and kind in ("label", "text", "heading"))
            or (prev == "text" and kind in ("list", "label", "heading"))
            or (prev == "label" and kind in ("label", "heading", "list", "text"))
        )
        if need_gap and out[-1] != "":
            out.append("")
        out.append(line.rstrip())
        prev = kind

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


_CN_MAJOR_HASH = re.compile(
    r"^#\s+((?:[一二三四五六七八九十百千]+、.+)|禁止事项)$"
)
_PART_HASH = re.compile(r"^#\s+(PART\s+[AB][^\n]*)$", re.IGNORECASE)
_PEEL_POINT_HASH = re.compile(r"^##\s+([★·※].+)$")
_PEEL_P_HEADING = re.compile(r"^#{3,5}\s+(?:P（核心句）|核心句（P）)\s*$")
_PEEL_FIELD_HASH = re.compile(
    r"^###\s+(拓展策略[^#\n]*|连至下一点（L）)\s*$"
)
_KUOZHAN_LEGACY = re.compile(r"^(#{1,6}\s+)拓展策略（[^）\n]*）\s*$")
_STAGE1_SUB_HASH = re.compile(r"^###\s+(\d+\.\d+\s+.+)$")
_STAGE3_TABLE_HASH = re.compile(r"^##\s+(表格\s*\d+.+)$")
_STAGE3_SEMANTIC_HASH = re.compile(r"^##\s+(语义场\s*\d+.+)$")
_STAGE3_TIER_HASH = re.compile(r"^###\s+(必备级|进阶级|亮点级)\s*$")
_BRACKET_HASH = re.compile(r"^##\s+【([^】]+)】\s*$")
_PAREN_HEADING_HASH = re.compile(r"^###\s+（[^）]+）.+$")
_NUMBERED_SECTION_HASH = re.compile(r"^##\s+(\d+\.\s+.+)$")


def _level_for_numbered_section(title: str) -> str:
    """Stage1 大节 h3；Stage2/3 范文·表格等含「版/分档」者 h4。"""
    if re.search(r"版|分档", title):
        return "####"
    return "###"


_STAGE4_NUM_BOLD = re.compile(r"^(\d+)\.\s+(\*\*.+)$")
_STAGE4_PRACTICE = re.compile(r"^\*\*(练习\s*\d+[：:][^*]+)\*\*\s*$")
_STAGE4_OPTIONAL = re.compile(r"^\*\*（教师可选用）([^*]+)\*\*\s*$")
_CN_SECTION_HEAD = re.compile(
    r"^#{1,6}\s+([一二三四五六七八九十百千]+)、\s*(.+)$"
)


def _stage4_block_kind(section_title: str) -> str | None:
    if "典型错误" in section_title:
        return "errors"
    if "课后练习" in section_title:
        return "practices"
    return None


def promote_stage4_block_headings(text: str) -> str:
    """
    Stage4「二、典型错误」「三、课后练习」：「1. **…**」→ h4 条块标题。
    其余 Stage（如 Stage1 §4 高分要点下的 1.2.3）→ 嵌套 bullet，避免 h4 字号过大。
    """
    out: list[str] = []
    block: str | None = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        indent = line[: len(line) - len(stripped)]
        m_sec = _CN_SECTION_HEAD.match(stripped) if stripped.startswith("#") else None
        if m_sec:
            block = _stage4_block_kind(m_sec.group(2))
            out.append(line)
            continue
        m = _STAGE4_NUM_BOLD.match(stripped)
        if m:
            num, rest = m.group(1), m.group(2)
            # 仅「典型错误」条块用 h4；练习区内 1. **…** 多为思考提示子条，勿升格
            if block == "errors":
                out.append(f"{indent}#### {num}. {rest}")
            else:
                out.append(f"{indent}- {rest}")
            continue
        m2 = _STAGE4_PRACTICE.match(stripped)
        if m2 and block == "practices":
            out.append(f"{indent}#### {m2.group(1)}")
            continue
        m3 = _STAGE4_OPTIONAL.match(stripped)
        if m3 and block == "practices":
            out.append(f"{indent}#### （教师可选用）{m3.group(1)}")
            continue
        out.append(line)
    return "\n".join(out)


def tune_stage_heading_levels(text: str) -> str:
    """
    全 Stage 统一标题阶梯（顶栏 1.48rem 下）：
    h3 一、/PART/禁止 · h4 ★/表格/语义场/2.1/（一） · h5 核心句（P）/必备级 等。
    """
    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        indent = line[: len(line) - len(stripped)]

        m_part = _PART_HASH.match(stripped)
        if m_part:
            out.append(f"{indent}### {m_part.group(1)}")
            continue
        m_major = _CN_MAJOR_HASH.match(stripped)
        if m_major:
            out.append(f"{indent}### {m_major.group(1)}")
            continue
        m_point = _PEEL_POINT_HASH.match(stripped)
        if m_point:
            out.append(f"{indent}#### {m_point.group(1)}")
            continue
        m_table = _STAGE3_TABLE_HASH.match(stripped)
        if m_table:
            out.append(f"{indent}#### {m_table.group(1)}")
            continue
        m_sem = _STAGE3_SEMANTIC_HASH.match(stripped)
        if m_sem:
            out.append(f"{indent}#### {m_sem.group(1)}")
            continue
        if _PEEL_P_HEADING.match(stripped):
            out.append(f"{indent}##### 核心句（P）")
            continue
        m_field = _PEEL_FIELD_HASH.match(stripped)
        if m_field:
            out.append(f"{indent}##### {m_field.group(1)}")
            continue
        m_tier = _STAGE3_TIER_HASH.match(stripped)
        if m_tier:
            out.append(f"{indent}##### {m_tier.group(1)}")
            continue
        m_sub = _STAGE1_SUB_HASH.match(stripped)
        if m_sub:
            out.append(f"{indent}#### {m_sub.group(1)}")
            continue
        m_br = _BRACKET_HASH.match(stripped)
        if m_br:
            out.append(f"{indent}### 【{m_br.group(1)}】")
            continue
        if _PAREN_HEADING_HASH.match(stripped):
            out.append(f"{indent}#### {stripped[4:].strip()}")
            continue
        m_num = _NUMBERED_SECTION_HASH.match(stripped)
        if m_num:
            lvl = _level_for_numbered_section(m_num.group(1))
            out.append(f"{indent}{lvl} {m_num.group(1)}")
            continue
        out.append(line)
    return "\n".join(out)


# 兼容旧名
tune_peel_heading_levels = tune_stage_heading_levels


_GAIYIJU_INLINE = re.compile(
    r"([。；!?])\s*[-·•]?\s*(\*\*)?改一句(\*\*)?[：:]\s*"
)
_GAIYIJU_TAIL = re.compile(
    r"([^\n#|])\s+[-·•]?\s*(\*\*)?改一句(\*\*)?[：:]\s*"
)
_GAIYIJU_LINE = re.compile(
    r"^(\s*)[-·•]?\s*(\*\*)?改一句(\*\*)?[：:]\s*(.*)$"
)
_GAIYIJU_ARROW_BLOCK = re.compile(
    r"\*\*改一句\*\*\s*[：:]\s*"
    r"(?:❌\s*)?"
    r"(.+?)"
    r"\s*→\s*"
    r"(?:✅\s*)?"
    r"(.+?)(?=\n\n|\n#{1,6}\s|\n\*\*本题\*\*|\n\|[^\n]+\n\|[^\n]+\n|$)",
    re.DOTALL,
)
_GAIYIJU_PLAIN_ARROW = re.compile(
    r"(?<!\*)\b改一句\s*[：:]\s*"
    r"(?:❌\s*)?"
    r"(.+?)"
    r"\s*→\s*"
    r"(?:✅\s*)?"
    r"(.+?)(?=\n\n|\n#{1,6}\s|\n\*\*本题\*\*|\n\|[^\n]+\n\|[^\n]+\n|$)",
    re.DOTALL,
)


def _strip_gaiyiju_markers(s: str) -> str:
    t = s.strip()
    t = re.sub(r"^❌\s*", "", t)
    t = re.sub(r"^✅\s*", "", t)
    t = re.sub(r"\s*❌\s*$", "", t)
    t = re.sub(r"\s*✅\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _format_gaiyiju_block(wrong: str, right: str) -> str:
    bad = _strip_gaiyiju_markers(wrong)
    good = _strip_gaiyiju_markers(right)
    if not bad or not good:
        return f"**改一句**：{wrong} → {right}"
    return f"##### 改一句\n\n{bad} ❌\n\n→ {good} ✅"


_DASHIHUA_LABEL = (
    r"(?:\*\*💡\s*一句大实话\*\*|💡\s*\*\*一句大实话\*\*|💡\s*一句大实话)"
)
_DASHIHUA_LINE = re.compile(
    rf"^(\s*){_DASHIHUA_LABEL}"
    r"(?:\s*[（(][^）)]*[）)])?\s*"
    r"[：:]\s*(.+)$"
)
_DASHIHUA_LINE_TITLE_ONLY = re.compile(
    rf"^(\s*){_DASHIHUA_LABEL}"
    r"(?:\s*[（(][^）)]*[）)])?\s*[：:]\s*$"
)
_DASHIHUA_LINE_SPACE_BODY = re.compile(
    rf"^(\s*){_DASHIHUA_LABEL}"
    r"(?:\s*[（(][^）)]*[）)])?\s+(.+)$"
)


def format_yijuhodashihua_block(text: str) -> str:
    """Stage1：「💡 一句大实话」独立为 h5 小标题，正文另起段。"""
    if "一句大实话" not in text:
        return text
    if re.search(r"#####\s*💡?\s*一句大实话", text):
        return text

    out: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        indent = line[: len(line) - len(stripped)]
        m = _DASHIHUA_LINE.match(stripped)
        if m and m.group(2).strip():
            out.append(f"{indent}##### 💡 一句大实话")
            out.append("")
            out.append(f"{indent}{m.group(2).strip()}")
            continue
        m_sp = _DASHIHUA_LINE_SPACE_BODY.match(stripped)
        if m_sp and m_sp.group(2).strip():
            out.append(f"{indent}##### 💡 一句大实话")
            out.append("")
            out.append(f"{indent}{m_sp.group(2).strip()}")
            continue
        if _DASHIHUA_LINE_TITLE_ONLY.match(stripped):
            out.append(f"{indent}##### 💡 一句大实话")
            continue
        out.append(line)
    return "\n".join(out)


def format_gaiyiju_arrow_blocks(text: str) -> str:
    """Stage3：「改一句」小标题 + 两行对照（❌/✅ 在句末）。"""
    if "改一句" not in text or "→" not in text:
        return text
    if re.search(r"#####\s*改一句\s*\n+[^\n]+❌\s*\n+→", text):
        return text

    def _sub(m: re.Match[str]) -> str:
        return "\n\n" + _format_gaiyiju_block(m.group(1), m.group(2)) + "\n"

    cleaned = _GAIYIJU_ARROW_BLOCK.sub(_sub, text)
    return _GAIYIJU_PLAIN_ARROW.sub(_sub, cleaned)


def normalize_kuozhan_strategy_heading(text: str) -> str:
    """核心/支撑要点统一为「拓展策略（E）」标题。"""
    if "拓展策略" not in text:
        return text
    out: list[str] = []
    for line in text.split("\n"):
        m = _KUOZHAN_LEGACY.match(line.strip())
        if m:
            indent = line[: len(line) - len(line.strip())]
            level = m.group(1)
            out.append(f"{indent}{level}拓展策略（E）")
        else:
            out.append(line)
    return "\n".join(out)


def normalize_benti_gaiyiju(text: str) -> str:
    """Stage3：「本题」与「改一句」分段，并格式化为小标题 + 两行对照。"""
    if not text or "改一句" not in text:
        return text
    cleaned = _GAIYIJU_INLINE.sub(r"\1\n\n**改一句**：", text)
    cleaned = _GAIYIJU_TAIL.sub(r"\1\n\n**改一句**：", cleaned)
    out: list[str] = []
    for line in cleaned.split("\n"):
        m = _GAIYIJU_LINE.match(line)
        if m:
            indent = m.group(1)
            rest = (m.group(4) or "").strip()
            out.append(f"{indent}**改一句**：{rest}" if rest else f"{indent}**改一句**：")
        else:
            out.append(line)
    cleaned = "\n".join(out)
    return format_gaiyiju_arrow_blocks(cleaned)


_NUM_LIST_LINE = re.compile(r"^\s*\d+\.\s")


def _is_list_item_line(stripped: str) -> bool:
    return bool(_LIST_LINE.match(stripped) or _NUM_LIST_LINE.match(stripped))


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def merge_list_item_continuations(text: str) -> str:
    """同一条列表项内被空行/软换行拆开的续行并回上一行，避免多条 <p>。"""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            if out and out[-1] != "":
                out.append("")
            i += 1
            continue
        if (
            _HEADING_LINE.match(stripped)
            or stripped.startswith("|")
            or stripped.startswith("```")
            or set(stripped) <= {"-", "*", "_"}
        ):
            out.append(line.rstrip())
            i += 1
            continue
        if _is_list_item_line(stripped):
            out.append(line.rstrip())
            i += 1
            continue
        prev_idx = len(out) - 1
        while prev_idx >= 0 and not out[prev_idx].strip():
            prev_idx -= 1
        if prev_idx < 0:
            out.append(line.rstrip())
            i += 1
            continue
        prev = out[prev_idx]
        prev_s = prev.strip()
        if not _is_list_item_line(prev_s):
            out.append(line.rstrip())
            i += 1
            continue
        prev_indent = _line_indent(prev)
        cur_indent = _line_indent(line)
        if cur_indent > prev_indent and _LIST_LINE.match(stripped):
            out.append(line.rstrip())
            i += 1
            continue
        if cur_indent >= prev_indent and not _NUM_LIST_LINE.match(stripped):
            out[prev_idx] = prev.rstrip() + " " + stripped
            i += 1
            continue
        out.append(line.rstrip())
        i += 1
    return "\n".join(out)


def normalize_list_spacing(text: str) -> str:
    """
    去掉列表项之间、编号条与子条之间、列表项与续行之间的多余空行。
    """
    lines = text.split("\n")
    out: list[str] = []

    def _last_nonempty() -> tuple[int, str] | None:
        for j in range(len(out) - 1, -1, -1):
            s = out[j].strip()
            if s:
                return j, s
        return None

    def _next_nonempty(k: int) -> tuple[int, str] | None:
        while k < len(lines):
            s = lines[k].strip()
            if s:
                return k, s
            k += 1
        return None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            prev = _last_nonempty()
            nxt = _next_nonempty(i + 1)
            if prev and nxt:
                _, prev_s = prev
                nxt_i, nxt_s = nxt
                if _is_list_item_line(prev_s) and _is_list_item_line(nxt_s):
                    continue
                if _NUM_LIST_LINE.match(prev_s) and _LIST_LINE.match(nxt_s):
                    continue
                prev_idx, _ = prev
                prev_indent = _line_indent(out[prev_idx])
                nxt_indent = _line_indent(lines[nxt_i])
                if _is_list_item_line(prev_s) and not _is_list_item_line(nxt_s):
                    if (
                        nxt_indent > prev_indent
                        and not _HEADING_LINE.match(nxt_s)
                        and not nxt_s.startswith("|")
                    ):
                        continue
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(line.rstrip())
    return "\n".join(out)


def _ensure_blank_before_list_after_paragraph(text: str) -> str:
    """仅在正文段落后、列表开始前插入一个空行（不在列表项之间插入）。"""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if (
            stripped
            and _is_list_item_line(stripped)
            and out
            and out[-1].strip()
            and not _is_list_item_line(out[-1].strip())
            and not _HEADING_LINE.match(out[-1].strip())
            and out[-1] != ""
        ):
            out.append("")
        out.append(line)
    return "\n".join(out)


def prettify_stage_markdown(text: str) -> str:
    """轻量整理 Markdown 间距，便于 Streamlit 正确分段渲染。"""
    if not text or not text.strip():
        return text
    cleaned = promote_section_headings(text.strip())
    cleaned = format_construction_dimensions(cleaned)
    cleaned = promote_stage4_block_headings(cleaned)
    cleaned = tune_stage_heading_levels(cleaned)
    cleaned = normalize_benti_gaiyiju(cleaned)
    cleaned = normalize_kuozhan_strategy_heading(cleaned)
    cleaned = format_yijuhodashihua_block(cleaned)
    cleaned = merge_list_item_continuations(cleaned)
    cleaned = normalize_list_spacing(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", cleaned)
    cleaned = _ensure_blank_before_list_after_paragraph(cleaned)
    return normalize_bold_markers(cleaned)


def sanitize_llm_html_breaks(text: str) -> str:
    """将模型误输出的 <br> 转为可读分隔（Markdown 表格内 HTML 不会换行）。"""
    if not text or "<br" not in text.lower():
        return text
    cleaned = _HTML_BREAK_RE.sub(" ", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"([。；：!?])\s+", r"\1", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned


def stage1_summary_incomplete(summary: str) -> str | None:
    """若审题总结疑似被截断，返回用户可读原因；完整则返回 None。"""
    text = (summary or "").strip()
    if not text:
        return "Stage 1 审题总结为空，请重试。"
    markers = ("## 6.", "## 6 ", "要点与结构规划", "结尾段")
    if not any(m in text for m in markers):
        return "Stage 1 输出可能在 §6「要点与结构规划」之前被截断，请重试 Stage 1。"
    if "结尾段" not in text:
        return "Stage 1 输出未写完 §6「结尾段」，请重试 Stage 1 或换更快模型。"
    tail = text[-80:].strip()
    if tail and tail[-1] in "（(,，、；;：:" and "）)" not in tail[-20:]:
        return "Stage 1 输出在段落中途截断，请重试 Stage 1。"
    return None


def format_image_question_for_history(structured: dict[str, Any]) -> str:
    from utils.question_input import format_image_question_for_history as _fmt

    return _fmt(structured)


def parse_stage1_output(raw: str) -> tuple[dict[str, Any], str]:
    """从 Stage1 模型输出中解析 JSON 与人类可读摘要。"""
    text = raw.strip()

    if JSON_MARKER in text and SUMMARY_MARKER in text:
        _, _, rest = text.partition(JSON_MARKER)
        after_json, _, summary_part = rest.partition(SUMMARY_MARKER)
        structured = _extract_json(after_json.strip())
        return structured, clean_stage1_summary(summary_part)

    part_b_split = _PART_B_SPLIT.split(text, maxsplit=1)
    if len(part_b_split) == 2:
        structured = _extract_json_from_part_a(part_b_split[0])
        summary = clean_stage1_summary(part_b_split[1])
        return structured, summary

    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_match:
        structured = _extract_json(code_match.group(1).strip())
        summary = _PART_B_SPLIT.sub("", text)
        summary = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", summary)
        return structured, clean_stage1_summary(summary)

    return {}, clean_stage1_summary(text)


def strip_reader_self_check(text: str) -> str:
    """移除文末「输出前自检」章节，供界面展示与 Word 导出。"""
    if not text or not text.strip():
        return text
    return _SELF_CHECK_SECTION.sub("", text).strip()


def clean_stage1_summary(summary: str) -> str:
    """去掉 PART A / JSON 等，仅保留教师可读的审题总结。"""
    text = summary.strip()
    text = re.sub(
        r"#?\s*PART\s*A[：:]\s*STRUCTURED_JSON[\s\S]*?(?=#?\s*PART\s*B|$)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = _PART_B_SPLIT.sub("", text)
    text = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", text)
    text = re.sub(r"^#+\s*PART\s*[AB][：:][^\n]*\n?", "", text, flags=re.IGNORECASE | re.MULTILINE)
    return strip_reader_self_check(text)


def _extract_json_from_part_a(text: str) -> dict[str, Any]:
    return _extract_json(text)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}

    fenced = re.match(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        return {"_parse_error": True, "_raw": text[:2000]}

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(text[start : i + 1])
                    if isinstance(data, dict):
                        return data
                except json.JSONDecodeError:
                    pass
                break

    return {"_parse_error": True, "_raw": text[:2000]}
