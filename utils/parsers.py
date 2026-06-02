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
            out.append(f"{indent}## 【{m_br.group(2)}】")
            continue

        m_major = _CN_MAJOR_SECTION.match(stripped)
        if m_major and len(m_major.group(3)) <= 72:
            indent = raw[: len(raw) - len(raw.lstrip())]
            out.append(
                f"{indent}## {m_major.group(2)}{m_major.group(3).strip()}"
            )
            continue

        m_sub = _CN_PAREN_SECTION.match(stripped)
        if m_sub and len(m_sub.group(3)) <= 64:
            indent = raw[: len(raw) - len(raw.lstrip())]
            out.append(f"{indent}### （{m_sub.group(2)}）{m_sub.group(3).strip()}")
            continue

        out.append(raw)
    return "\n".join(out)


_LABEL_LINE = re.compile(
    r"^(\s*)(?:[-*+]\s+)?\*\*[^*]+?\*\*\s*[：:]"
)
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


def prettify_stage_markdown(text: str) -> str:
    """轻量整理 Markdown 间距，便于 Streamlit 正确分段渲染。"""
    if not text or not text.strip():
        return text
    cleaned = promote_section_headings(text.strip())
    cleaned = normalize_vertical_spacing(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"([^\n])\n(#{1,6}\s)", r"\1\n\n\2", cleaned)
    cleaned = re.sub(r"([^\n])\n([-*+]\s)", r"\1\n\n\2", cleaned)
    cleaned = re.sub(r"([^\n])\n(\d+\.\s)", r"\1\n\n\2", cleaned)
    return cleaned


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
