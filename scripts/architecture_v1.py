"""应用文课堂 PPT 标准架构 V1 — 固定教学模块 + 备课包填槽。

课件目标：理解 · 记忆 · 迁移 · 得分（不是备课包展示）。
Stage1→思维建模  Stage2→范文拆解  Stage3→语言积累  Stage4→训练迁移
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from utils.export_word import STAGE_TITLES

LessonPreset = Literal["40min", "70min", "80min"]

# 70min = 80min 去掉 4 个 optional 页（B4/C3/D8/D10），保留 A3 快速思考

# ---------------------------------------------------------------------------
# Page slots (fixed architecture — LLM/Cursor only fills content, not structure)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PageSlot:
    slot_id: str
    module: str
    title: str
    spec_kind: str  # title | content | peel | essay | table | stage3_placeholder
    presets: frozenset[LessonPreset]
    optional: bool = False


# Module A 导入 · B 审题 · C 思维 · D 范文 · E 语言(Stage3) · F 训练 · G 总结
ARCHITECTURE_V1_SLOTS: tuple[PageSlot, ...] = (
    PageSlot("A1", "A", "导入 · 真题展示", "title", frozenset({"40min", "70min", "80min"})),
    PageSlot("A2", "A", "导入 · 情境代入", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("A3", "A", "导入 · 快速思考", "content", frozenset({"70min", "80min"}), optional=True),
    PageSlot("B0", "B", "审题 · 动笔自检五问", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("B1", "B", "审题 · 三元审题", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("B2", "B", "审题 · 任务拆解", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("B3", "B", "审题 · 易错对比", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("B4", "B", "审题 · 考查能力链", "content", frozenset({"80min"}), optional=True),
    PageSlot("C1", "C", "思维 · 高分路径", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("C2", "C", "思维 · 高分公式", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("C3", "C", "思维 · 维度分析", "content", frozenset({"80min"}), optional=True),
    PageSlot("F1s", "F", "动笔易错", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("D1", "D", "PEEL 写作骨架", "peel", frozenset({"40min", "70min", "80min"})),
    PageSlot("D6", "D", "基础版范文", "essay", frozenset({"40min", "70min", "80min"})),
    PageSlot("D7", "D", "高分版 A", "essay", frozenset({"40min", "70min", "80min"})),
    PageSlot("D8", "D", "高分版 B", "essay", frozenset({"80min"}), optional=True),
    PageSlot("D9", "D", "三版对比要点", "table", frozenset({"40min", "70min", "80min"})),
    PageSlot("D10", "D", "高分升级点总结", "content", frozenset({"80min"}), optional=True),
    PageSlot("F2s", "F", "讲评活动 · 元素与逻辑", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("E0", "E", "功能句型与话题词块", "stage3_placeholder", frozenset({"40min", "70min", "80min"})),
    PageSlot("F3s", "F", "当堂迁移", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("G1", "G", "课堂小结 · 高分公式", "content", frozenset({"40min", "70min", "80min"})),
    PageSlot("G2", "G", "课后任务", "content", frozenset({"40min", "70min", "80min"})),
)

MODULE_DIVIDERS: dict[str, tuple[str, str, str]] = {
    "A": ("导入", "进入情境 · 产生写作需求", "INDIGO"),
    "B": ("审题", "我是谁 · 写给谁 · 为什么写", "INDIGO"),
    "C": ("思维", "如何想 · 高分路径", "CORAL"),
    "D": ("范文", "PEEL · 三版对比", "CORAL"),
    "E": ("语言", "句型 · 词块 · 升级", "MINT"),
    "F": ("训练", "诊断 · 迁移 · 得分", "VIOLET"),
    "G": ("带走", "公式 · 背诵 · 作业", "INDIGO"),
}


def slots_for_preset(preset: LessonPreset) -> list[PageSlot]:
    return [s for s in ARCHITECTURE_V1_SLOTS if preset in s.presets]


def _trim(line: str, max_len: int = 120) -> str:
    s = re.sub(r"\s+", " ", line.strip())
    return s[: max_len - 1] + "…" if len(s) > max_len else s


def _bullets(text: str, max_n: int = 4) -> list[str]:
    if not text.strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r"^[-*•]\s+(.+)$", text, flags=re.MULTILINE):
        b = _trim(m.group(1))
        if b and b not in seen:
            seen.add(b)
            out.append(b)
        if len(out) >= max_n:
            break
    for m in re.finditer(r"^\d+[.)]\s+(.+)$", text, flags=re.MULTILINE):
        b = _trim(m.group(1))
        if b and b not in seen:
            seen.add(b)
            out.append(b)
        if len(out) >= max_n:
            break
    return out[:max_n]


_POSTER_LINE_RE = re.compile(r"^\[图[：:]")


def _question_lines(question: str, max_lines: int = 6) -> list[str]:
    """Stem lines for cover slide (poster description lines excluded)."""
    lines = [html.unescape(ln.strip()) for ln in question.splitlines() if ln.strip()]
    stem = [ln for ln in lines if not _POSTER_LINE_RE.match(ln)]
    if not stem:
        return ["（见源稿题目原文）"]
    return [_trim(ln, 140) for ln in stem[:max_lines]]


_POSTER_CHUNK_SPLIT = re.compile(r"(?:;\s*|(?=Poster\s*\d)|(?=海报\s*\d))")


def _poster_lines(question: str, max_lines: int = 4) -> list[str]:
    """Visual description lines from ``[图：…]`` — one chunk per poster."""
    out: list[str] = []
    for ln in question.splitlines():
        ln = html.unescape(ln.strip())
        if not _POSTER_LINE_RE.match(ln):
            continue
        inner = re.sub(r"^\[图[：:]\s*", "", ln).rstrip("]").strip()
        chunks = [c.strip() for c in _POSTER_CHUNK_SPLIT.split(inner) if c.strip()]
        if not chunks:
            chunks = [inner]
        for chunk in chunks:
            label = chunk
            if not re.match(r"^(Poster|海报)", chunk, re.I):
                label = chunk
            out.append(_trim(label, 140))
            if len(out) >= max_lines:
                return out
    return out


def _is_mistake_bullet(text: str) -> bool:
    return any(kw in text for kw in ("学生容易写成", "易错", "应当写成", "别写成"))


def _chain_with_arrows(steps: list[str]) -> list[str]:
    if len(steps) <= 1:
        return steps
    out: list[str] = []
    for i, step in enumerate(steps):
        out.append(step)
        if i < len(steps) - 1:
            out.append("↓")
    return out


def _extract_thinking_chain(stage1: str) -> list[str]:
    """Extract C1 path from「底层思维路径」or dimension chain — never mistake bullets."""
    m = re.search(r"底层思维路径[：:]\s*(.+?)(?:\n|$)", stage1)
    if m:
        path = _trim(m.group(1).strip())
        steps = [
            _trim(s)
            for s in re.split(r"[→→]|(?:\s*[,，]\s*(?=再|然后|最后|用))", path)
            if s.strip()
        ]
        if len(steps) >= 2:
            return _chain_with_arrows(steps[:4])
        if path:
            return [path]

    dims: list[str] = []
    for dm in re.finditer(r"维度\d+\s*[·\.]\s*(.+)", stage1):
        dims.append(_trim(dm.group(1)))
    if len(dims) >= 2:
        return _chain_with_arrows(dims[:3])

    pts: list[str] = []
    for b in _bullets(stage1, 8):
        if _is_mistake_bullet(b):
            continue
        if re.match(r"^(我是谁|写给谁|为了什么|体裁|时态|人称|语气)", b):
            continue
        pts.append(b)
        if len(pts) >= 3:
            break
    if pts:
        return _chain_with_arrows(pts)

    return [
        "海报画面 → 象征意义",
        "↓",
        "心理健康主题",
        "↓",
        "形成理由",
    ]


def _question_type_label(data: dict[str, Any]) -> str:
    return (data.get("question_type_label") or "应用文").strip()


def _topic_subtitle(data: dict[str, Any]) -> str:
    """Short hero tag only — full题干 lives in the body panel (never duplicate here)."""
    qtype = _question_type_label(data)
    return f"{qtype} · 选海报写理由"


_DEFAULT_SELF_CHECK_FIVE: tuple[str, ...] = (
    "语气 — 我读/写起来更像朋友间的建议，还是正式报告？",
    "结构 — 主体段有具体理由，还是只有「我觉得好」？",
    "逻辑 — 是否既说明「为什么选这个」，也解释「为什么不选另一个」？",
    "立意 — 是否写出主题的深层意义，而不只停留在表面选择？",
    "语言 — 是否用了本题关键表达，并避开 very good / nice 等空泛词？",
)


def _stage1_self_check_five(stage1: str) -> list[str]:
    """Extract「动笔前自检五问」from Stage1 markdown/HTML export text."""
    if not stage1.strip():
        return list(_DEFAULT_SELF_CHECK_FIVE)

    block = stage1
    section = re.search(
        r"动笔[前]?自检五问[：:\s]*\n?(.*?)(?=\n(?:💡|#####\s*💡|一句大实话|##\s|\Z))",
        stage1,
        re.DOTALL | re.IGNORECASE,
    )
    if section:
        block = section.group(1)

    out: list[str] = []
    for dm in re.finditer(
        r"(?:^|\n)\*{0,2}\s*(\d+)\.\s*([^*\n—\-]+?)\*{0,2}\s*[—\-：:]\s*(.+?)(?=\n(?:\*{0,2}\s*\d+\.|💡|#####|##|\Z))",
        block,
        re.DOTALL,
    ):
        label = _trim(dm.group(2))
        detail = _trim(re.sub(r"\s+", " ", dm.group(3).replace("\n", " ")), 130)
        out.append(f"{label} — {detail}")

    if len(out) < 5:
        for line in block.splitlines():
            raw = line.strip()
            m = re.match(r"^\*{0,2}\s*(\d+)\.\s*(.+?)\*{0,2}\s*[—\-：:]\s*(.+)$", raw)
            if m:
                label = _trim(m.group(2))
                detail = _trim(m.group(3), 130)
                item = f"{label} — {detail}"
                if item not in out:
                    out.append(item)
                continue
            if re.match(r"^\d+\.", raw):
                cleaned = re.sub(r"^\d+\.\s*", "", raw)
                cleaned = re.sub(r"\*+", "", cleaned).strip()
                if cleaned and cleaned not in out:
                    out.append(_trim(cleaned, 130))

    if len(out) >= 3:
        return out[:5]
    return list(_DEFAULT_SELF_CHECK_FIVE)


def _self_check_five_slide_specs(stage1: str, module: str) -> list[dict[str, Any]]:
    """Single content slide for all five self-check questions."""
    bullets = _stage1_self_check_five(stage1)
    return [
        {
            "type": "content",
            "title": "审题 · 动笔自检五问",
            "bullets": bullets,
            "panel": True,
            "_module": module,
        }
    ]


def _stage1_triplet_block(stage1: str) -> str:
    """Isolate 三元审题 subsection to avoid pulling unrelated bullets."""
    m = re.search(
        r"(?:2\.1\s*三元审题|三元审题)(.*?)(?=\n(?:#{1,4}\s|####|\Z))",
        stage1,
        re.DOTALL | re.IGNORECASE,
    )
    return m.group(1) if m else stage1


def _triplet_item_key(text: str) -> str:
    t = re.sub(r"^[①②③]\s*", "", text.strip())
    if "：" in t:
        t = t.split("：", 1)[1].strip()
    elif ":" in t:
        t = t.split(":", 1)[1].strip()
    return re.sub(r"\s+", "", t.lower())


def _stage1_triplet(stage1: str) -> list[str]:
    block = _stage1_triplet_block(stage1)
    labels = ("我是谁", "写给谁", "为了什么", "为什么写")
    out: list[str] = []
    for label in labels:
        dm = re.search(
            rf"\*\*{re.escape(label)}\*\*\s*[：:]\s*(.+)",
            block,
            re.IGNORECASE,
        )
        if not dm:
            dm = re.search(rf"{re.escape(label)}\s*[：:]\s*(.+)", block, re.IGNORECASE)
        if dm:
            out.append(f"{label}：{_trim(dm.group(1), 120)}")
    if len(out) >= 3:
        return out[:3]

    defaults = [
        "我是谁：（从 Stage1 提炼）",
        "写给谁：（从 Stage1 提炼）",
        "为什么写：（从 Stage1 提炼）",
    ]
    pts = _bullets(block, 5)
    if len(pts) >= 3:
        return pts[:3]
    for kw, label in (
        ("李华", "我是谁：李华（交换生朋友）"),
        ("James", "写给谁：James"),
        ("理由", "为什么写：说明选择并给出理由"),
    ):
        if kw.lower() in stage1.lower() and label not in pts:
            pts.append(label)
    return (pts + defaults)[:3]


def _stage1_one_truth(stage1: str) -> str:
    """Extract「一句大实话」body (no heading / emoji prefix)."""
    for pat in (
        r"💡\s*一句大实话\s*\n+(.+?)(?=\n(?:\d+\.\s|#{1,4}\s|##\s|\Z))",
        r"一句大实话[：:\s]*\n+(.+?)(?=\n(?:\d+\.\s|#{1,4}\s|##\s|\Z))",
    ):
        m = re.search(pat, stage1, re.DOTALL | re.IGNORECASE)
        if m:
            text = re.sub(r"\s+", " ", m.group(1).strip())
            return _trim(text, 220)
    return ""


def _stage1_section_function(block: str, section_label: str) -> str:
    m = re.search(
        rf"{re.escape(section_label)}\s*\n(.*?)(?=\n(?:开头段|主体段|结尾段)\s*\n|\Z)",
        block,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return ""
    section = m.group(1)
    fm = re.search(r"-\s*功能[：:]\s*(.+)", section, re.IGNORECASE)
    if fm:
        return _trim(fm.group(1), 100)
    if section_label == "主体段":
        pm = re.search(r"-\s*要点\[?1\]?\s*[：:]\s*(.+)", section, re.IGNORECASE)
        if pm:
            return _trim(pm.group(1), 100)
    return ""


def _stage1_tasks(stage1: str) -> list[str]:
    triplet_keys = {_triplet_item_key(t) for t in _stage1_triplet(stage1)}
    out: list[str] = []

    plan = re.search(
        r"(?:^|\n)\d+\.\s*要点与结构规划\s*\n(.*?)(?=\n\d+\.\s|\Z)",
        stage1,
        re.DOTALL | re.IGNORECASE,
    )
    block = plan.group(1) if plan else ""
    for label, num in (
        ("开头段", "①"),
        ("主体段", "②"),
        ("结尾段", "③"),
    ):
        fn = _stage1_section_function(block, label)
        if fn:
            out.append(f"{num} {label}：{fn}")

    if len(out) < 3:
        purpose = re.search(
            r"(?:2\.4\s*交际目的拆解|交际目的拆解)(.*?)(?=\n(?:\d+\.\s|#{1,4}\s|##\s|\Z))",
            stage1,
            re.DOTALL | re.IGNORECASE,
        )
        pblock = purpose.group(1) if purpose else ""
        for label, num in (
            ("核心交际目的", "①"),
            ("达成标准", "②"),
            ("信息层", "③"),
        ):
            dm = re.search(
                rf"\*\*{re.escape(label)}\*\*\s*[：:]\s*(.+)",
                pblock,
                re.IGNORECASE,
            )
            if not dm:
                dm = re.search(rf"{re.escape(label)}\s*[：:]\s*(.+)", pblock, re.IGNORECASE)
            if dm:
                out.append(f"{num} {_trim(dm.group(1), 100)}")

    filtered: list[str] = []
    for item in out:
        if _triplet_item_key(item) in triplet_keys:
            continue
        if item not in filtered:
            filtered.append(item)

    if len(filtered) >= 2:
        return filtered[:3]

    return [
        "① 做出选择（明确 Poster 1 或 Poster 2）",
        "② 说明理由（结合海报设计元素与心理健康主题）",
        "③ 收束祝愿（鼓励参赛 / 祝福收束）",
    ]


def _stage1_mistakes(stage4: str, stage1: str) -> list[str]:
    combined = f"{stage4}\n{stage1}"
    out: list[str] = []
    for m in re.finditer(r"(易错[^：:\n]*[：:]\s*.+)", combined):
        out.append("❌ " + _trim(m.group(1), 100))
        if len(out) >= 2:
            break
    if len(out) < 2:
        out.extend(
            [
                "❌ 理由空泛：只说 good / nice，未绑设计元素",
                "✅ 用具体画面 + 主题词块支撑观点",
            ]
        )
    return out[:3]


def _thinking_path(stage1: str) -> list[str]:
    return _extract_thinking_chain(stage1)


def _thinking_formula(stage1: str) -> list[str]:
    return [
        "选择 + 画面细节 + 主题分析 + 鼓励收束",
        "（从本题 Stage1 高分要点提炼）",
        *_bullets(stage1, 2),
    ]


def _extract_essay_block(stage2: str, label: str) -> str:
    if not stage2 or not label:
        return ""

    section_patterns: list[tuple[re.Pattern[str], re.Pattern[str]]] = [
        (re.compile(r"1\.\s*基础版[^\n]*", re.IGNORECASE), re.compile(r"^\s*2\.\s*高分版", re.MULTILINE | re.IGNORECASE)),
        (
            re.compile(r"2\.\s*高分版\s*A[^\n]*", re.IGNORECASE),
            re.compile(r"^\s*3\.\s*高分版", re.MULTILINE | re.IGNORECASE),
        ),
        (
            re.compile(r"3\.\s*高分版\s*B[^\n]*", re.IGNORECASE),
            re.compile(r"^[三四]、", re.MULTILINE),
        ),
    ]
    label_to_idx = {
        "基础版": 0,
        "基础": 0,
        "进阶版": 1,
        "高分版 A": 1,
        "高分版": 1,
        "高分版 B": 2,
        "逻辑": 2,
    }
    idx = label_to_idx.get(label)
    if idx is not None:
        start_pat, end_pat = section_patterns[idx]
        start_m = start_pat.search(stage2)
        if start_m:
            rest = stage2[start_m.end() :]
            end_m = end_pat.search(rest)
            block = rest[: end_m.start()].strip() if end_m else rest.strip()
            if "Dear " in block:
                block = block[block.find("Dear ") :]
            return block.strip()

    if label not in stage2:
        return ""
    pattern = rf"{re.escape(label)}[^\n]*\n+(.*?)(?=\n(?:基础版|进阶版|高分版|PEEL|##|\Z))"
    m = re.search(pattern, stage2, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    block = m.group(1).strip()
    if "Dear " in block:
        block = block[block.find("Dear ") :]
    return block.strip()


def _default_peel_points() -> list[dict]:
    return [
        {
            "label": "Point 1 选择",
            "p": "I'd go with …",
            "e_items": ["具体化：画面细节 + 主题词"],
            "l": "Here's why I think so.",
        },
        {
            "label": "Point 2 理由",
            "p": "The design captures the theme of …",
            "e_items": ["元素 → 主题关联", "对读者的影响"],
            "l": "Overall, this poster feels more …",
        },
    ]


def _peel_section_text(block: str, keywords: tuple[str, ...]) -> str:
    """Extract body text under the first PEEL sub-heading whose title contains a keyword."""
    matches = list(re.finditer(r"^#{3,6}\s+(.+)$", block, flags=re.MULTILINE))
    for idx, m in enumerate(matches):
        title = m.group(1)
        if not any(kw in title for kw in keywords):
            continue
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        raw = block[start:end].strip()
        lines: list[str] = []
        for ln in raw.splitlines():
            ln = re.sub(r"^[-*•]\s+", "", ln.strip())
            if ln and not ln.startswith("#"):
                lines.append(_trim(ln, 120))
        if lines:
            return _trim(" ".join(lines), 120)
        return _trim(raw, 120)
    return ""


def _extract_peel_field(block: str, heading_pattern: str) -> str:
    keyword_map = {
        r"核心句": ("核心句", "P（", "P(", "P ·"),
        r"连至下一点": ("连至下一点", "L（", "L(", "总结句"),
    }
    for key, keywords in keyword_map.items():
        if re.search(key, heading_pattern, flags=re.IGNORECASE):
            return _peel_section_text(block, keywords)
    return _peel_section_text(block, (heading_pattern,))


def _extract_peel_e_items(block: str, *, max_items: int = 2) -> list[str]:
    raw = _peel_section_text(block, ("拓展策略", "E（", "E(", "拓展 E"))
    if not raw:
        return []
    items: list[str] = []
    for ln in re.split(r"[\n;；]+", raw):
        ln = re.sub(r"^[-*•]\s+", "", ln.strip())
        if ln:
            items.append(_trim(ln, 100))
        if len(items) >= max_items:
            break
    return items[:max_items]


def _peel_section_body(stage2: str) -> str:
    sec = re.search(
        r"(?:^|\n)一[、.]?\s*PEEL[^\n]*\n(.*?)(?=\n二[、.]|$)",
        stage2,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if sec:
        return sec.group(1)
    sec = re.search(
        r"(?:^|\n)#{1,3}\s*(?:一、)?PEEL[^\n]*\n(.*?)(?=\n#{1,3}\s*(?:\d+\.|基础版|进阶版|高分版|二、)|\Z)",
        stage2,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return sec.group(1) if sec else ""


def _clean_peel_sentence(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    for pat in (r'"([^"]+)"', r"'([^']+)'", r"「([^」]+)」"):
        m = re.search(pat, raw)
        if m:
            return _trim(m.group(1), 120)
    raw = re.sub(r"（[^）]*）", "", raw)
    raw = re.sub(r"\([^)]*\)", "", raw)
    return _trim(raw.strip(), 120)


def _peel_bullet_value(line: str) -> str:
    line = re.sub(r"^[-*•]\s+", "", line.strip())
    if "：" in line:
        line = line.split("：", 1)[1].strip()
    elif ":" in line and re.match(r"^[\w/]+:", line):
        line = line.split(":", 1)[1].strip()
    return _clean_peel_sentence(line) or _trim(line, 100)


def _plain_peel_field(block: str, start_keywords: tuple[str, ...], stop_keywords: tuple[str, ...]) -> str:
    start_pat = "|".join(re.escape(k) for k in start_keywords)
    stop_pat = "|".join(re.escape(k) for k in stop_keywords)
    m = re.search(
        rf"(?:^|\n)(?:{start_pat})[^\n]*\n+(.*?)(?=\n(?:{stop_pat})|\Z)",
        block,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ""
    for ln in m.group(1).splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("- "):
            val = _peel_bullet_value(ln)
            if val:
                return val
            continue
        cleaned = _clean_peel_sentence(ln)
        if cleaned:
            return cleaned
    return ""


def _plain_peel_e_items(block: str, *, max_items: int = 2) -> list[str]:
    m = re.search(
        r"(?:^|\n)拓展策略(?:（E）|\(E\))[^\n]*\n+(.*?)(?=\n连至下一点|\n★|\Z)",
        block,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    items: list[str] = []
    for ln in m.group(1).splitlines():
        ln = ln.strip()
        if not ln.startswith("- "):
            continue
        val = _peel_bullet_value(ln)
        if val:
            items.append(_trim(val, 100))
        if len(items) >= max_items:
            break
    return items[:max_items]


def _parse_peel_point_block(block: str, label: str) -> dict | None:
    p = _plain_peel_field(
        block,
        ("核心句（P）", "核心句(P)", "P（核心句）"),
        ("拓展策略", "连至下一点", "★"),
    )
    if not p:
        p = _peel_section_text(block, ("核心句", "P（", "P("))
    e_items = _plain_peel_e_items(block) or _extract_peel_e_items(block)
    l = _plain_peel_field(
        block,
        ("连至下一点（L）", "连至下一点(L)", "连至下一点"),
        ("★", "支撑要点", "核心要点"),
    )
    if not l:
        l = _peel_section_text(block, ("连至下一点", "L（", "总结句"))
    if not p and not e_items and not l:
        return None
    return {"label": label, "p": p, "e_items": e_items, "l": l}


def _parse_structured_peel(stage2: str) -> list[dict]:
    peel_body = _peel_section_body(stage2)
    if not peel_body.strip():
        return []
    point_head = r"(?:核心要点|支撑要点)"
    chunks = re.split(
        rf"(?=(?:★)?{point_head}\s*Point\s*[12])",
        peel_body,
        flags=re.IGNORECASE,
    )
    if len(chunks) <= 1:
        chunks = re.split(
            rf"(?=^#{{3,5}}\s+[★·※]?[^\n]*{point_head}[^\n]*Point\s*[12])",
            peel_body,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    points: list[dict] = []
    for chunk in chunks:
        if not re.search(r"Point\s*[12]", chunk, flags=re.IGNORECASE):
            continue
        label_m = re.search(r"Point\s*([12])", chunk, flags=re.IGNORECASE)
        label = f"Point {label_m.group(1)}" if label_m else "Point"
        heading_m = re.search(
            rf"((?:★)?{point_head}[^\n]*Point\s*[12][^\n]*)",
            chunk,
            flags=re.IGNORECASE,
        )
        point = _parse_peel_point_block(chunk, label)
        if point:
            if heading_m:
                point["heading"] = _trim(heading_m.group(1).strip(), 100)
            points.append(point)
    return points[:2]


def _peel_from_stage2(stage2: str) -> list[dict]:
    if not stage2.strip():
        return _default_peel_points()
    structured = _parse_structured_peel(stage2)
    if len(structured) >= 2:
        return structured
    if len(structured) == 1:
        defaults = _default_peel_points()
        return [structured[0], defaults[1]]
    pts = _bullets(stage2, 8)
    if len(pts) >= 4:
        mid = min(2, len(pts) // 2)
        return [
            {
                "label": "Point 1",
                "p": _trim(pts[0], 120),
                "e_items": [_trim(x, 100) for x in pts[1:mid]][:2],
                "l": _trim(pts[mid], 120) if mid < len(pts) else "",
            },
            {
                "label": "Point 2",
                "p": _trim(pts[mid + 1] if mid + 1 < len(pts) else pts[-1], 120),
                "e_items": [_trim(x, 100) for x in pts[mid + 2 : mid + 4]][:2],
                "l": _trim(pts[-1], 120),
            },
        ]
    return _default_peel_points()


def _parse_tsv_table_section(text: str, marker: str) -> list[list[str]]:
    """Extract tab-separated table rows after a section marker in Stage2 export text."""
    if not text.strip() or marker not in text:
        return []
    rest = text.split(marker, 1)[1].lstrip("\n")
    rows: list[list[str]] = []
    for line in rest.splitlines():
        raw = line.strip()
        if not raw:
            if rows:
                break
            continue
        if re.match(r"^[一二三四五六七八九十、]", raw) and rows:
            break
        if "\t" not in raw:
            if rows:
                break
            continue
        cells = [c.strip() for c in raw.split("\t")]
        if cells:
            rows.append(cells)
    return rows


def _compare_table_rows(stage2: str = "") -> list[list[str]]:
    """Parse Stage2 「四、三版对比分析表」; fallback to minimal generic rows."""
    parsed = _parse_tsv_table_section(stage2, "四、三版对比分析表")
    if len(parsed) >= 2:
        header, *body = parsed
        if len(header) >= 4 and body:
            return [header[:4]] + [r[:4] for r in body if len(r) >= 2]
    return [
        ["维度", "基础版", "高分版 A", "高分版 B"],
        ["句式", "简单句为主", "复合句 + 状语", "逻辑连接词"],
        ["词汇", "基础词", "情感/画面词", "逻辑/抽象词"],
        ["衔接", "also / so", "Yet / As for", "Firstly / However"],
    ]


def _upgrade_bullets_from_stage2(stage2: str, *, max_n: int = 5) -> list[str]:
    """Parse Stage2 「五、高分升级点解析」 into classroom bullet lines."""
    if "五、高分升级点解析" not in stage2:
        return []
    rest = stage2.split("五、高分升级点解析", 1)[1].lstrip("\n")
    out: list[str] = []
    for line in rest.splitlines():
        line = line.strip()
        if not line:
            if out:
                break
            continue
        if re.match(r"^[一二三四五六七八九十、]", line) and out:
            break
        if line.startswith("从") and ("升级为" in line or "：" in line):
            out.append(_trim(line, 140))
        elif line.startswith("- "):
            out.append(_trim(line[2:], 140))
        if len(out) >= max_n:
            break
    return out


def _scenario_bullets(question: str, stage1: str) -> list[str]:
    """Topic-aware A2 situational bullets (not hardcoded poster scenario)."""
    q_lines = [ln.strip() for ln in question.splitlines() if ln.strip()]
    lead = _trim(q_lines[0], 120) if q_lines else ""
    if not lead:
        for m in re.finditer(r"^[-*•]\s+(.+)$", stage1, flags=re.MULTILINE):
            lead = _trim(m.group(1), 120)
            break
    bullets = []
    if lead:
        bullets.append(f"情境：{lead}")
    bullets.append("你会怎么回复？（选择 + 理由）")
    return bullets


def _stage4_warn(stage4: str) -> list[str]:
    from scripts.classroom_content_filter import parse_stage4_student_from_export

    pts = parse_stage4_student_from_export(stage4)["warn"]
    return pts if pts else [
        "❌ 理由空泛，未扣题要点",
        "→ 用 Stage3 词块绑定具体细节",
        "❌ 语气与对象不匹配",
    ]


def _stage4_review(stage4: str) -> list[str]:
    from scripts.classroom_content_filter import parse_stage4_student_from_export

    pts = parse_stage4_student_from_export(stage4)["activities"]
    return pts if pts else [
        "元素 → 主题：用词块造句，绑定画面细节",
        "逻辑链：Firstly / Secondly 写两个理由",
        "风格：选 A 情感或 B 逻辑，改自己的段落",
    ]


def _migration_matches_question(item: str, question: str) -> bool:
    """Reject generic homework prompts that contradict the current question topic."""
    if not item.strip() or not question.strip():
        return True
    q = question.lower()
    item_l = item.lower()
    conflict_groups = (
        (("james", "心理健康", "mental health"), ("lucy", "环保", "save our planet", "greener future")),
        (("心理健康", "mental health week"), ("环保", "校园环保", "save our planet")),
    )
    for q_signals, bad_signals in conflict_groups:
        q_hit = any(s in q or s in question for s in q_signals)
        bad_hit = any(s in item_l or s in item for s in bad_signals)
        if q_hit and bad_hit:
            return False
    return True


def _migration_from_question(question: str) -> list[str]:
    first = _trim(html.unescape(question.splitlines()[0] if question else ""), 80)
    topic = first or "本题"
    return [
        f"完整迁移：围绕「{topic}」限时写 1 段主体（PEEL）",
        "片段升级：换用本题设计元素，保持 PEEL 结构",
    ]


def _stage4_migration(stage4: str, question: str = "") -> list[str]:
    from scripts.classroom_content_filter import parse_stage4_student_from_export

    raw = parse_stage4_student_from_export(stage4)["migration"]
    pts = [p for p in raw if _migration_matches_question(p, question)]
    if pts:
        return pts
    if question.strip():
        return _migration_from_question(question)
    return [
        "片段升级：换主题，保持 PEEL 结构",
        "完整迁移：限时写主体段",
    ]


def _closing_slides(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    g1 = [
        "本课高分公式：观点 + 细节 + 分析 + 升华",
        "Stage1 思维路径 → Stage2 范文 → Stage3 语言 → Stage4 迁移",
    ]
    g2 = [
        "背诵：5 个功能句型 + 10 个话题词块",
        "完成：当堂迁移写 1 段主体（PEEL）",
    ]
    s3 = (data.get("stage3") or "").strip()
    if "句型" in s3:
        g2.insert(0, "复盘：功能句型改错页（本题用法）")
    return g1, g2


def build_slot_spec(slot: PageSlot, data: dict[str, Any]) -> dict | None:
    """Map one architecture slot → renderer slide spec (except E0 / Stage3)."""
    qtype = _question_type_label(data)
    question = (data.get("question") or "").strip()
    stage1 = (data.get("stage1") or "").strip()
    stage2 = (data.get("stage2") or "").strip()
    stage4 = (data.get("stage4") or "").strip()

    if slot.spec_kind == "title":
        spec: dict[str, Any] = {
            "type": "title",
            "title": f"高考英语应用文 · {qtype}",
            "subtitle": _topic_subtitle(data),
            "body": _question_lines(question),
            "_module": slot.module,
        }
        posters = _poster_lines(question)
        if posters:
            spec["poster_lines"] = posters
        return spec

    if slot.slot_id == "A2":
        return {
            "type": "content",
            "title": slot.title,
            "bullets": _scenario_bullets(question, stage1),
            "_module": slot.module,
        }
    if slot.slot_id == "A3":
        return {
            "type": "content",
            "title": slot.title,
            "bullets": ["你最先想到什么？", "允许：投票 / 讨论 / 判断"],
            "_module": slot.module,
        }
    if slot.slot_id == "B0":
        return _self_check_five_slide_specs(stage1, slot.module)
    if slot.slot_id == "B1":
        spec: dict[str, Any] = {
            "type": "content",
            "title": slot.title,
            "bullets": _stage1_triplet(stage1),
            "_module": slot.module,
        }
        truth = _stage1_one_truth(stage1)
        if truth:
            spec["callout"] = truth
        return spec
    if slot.slot_id == "B2":
        return {"type": "content", "title": slot.title, "bullets": _stage1_tasks(stage1), "_module": slot.module}
    if slot.slot_id == "B3":
        return {
            "type": "content",
            "title": slot.title,
            "bullets": _stage1_mistakes(stage4, stage1),
            "warn_panel": True,
            "_module": slot.module,
        }
    if slot.slot_id == "B4":
        return {
            "type": "content",
            "title": slot.title,
            "bullets": [
                "观点表达 → 理由论证 → 交际达成",
                *_bullets(stage1, 2),
            ],
            "_module": slot.module,
        }
    if slot.slot_id == "C1":
        return {"type": "content", "title": slot.title, "bullets": _thinking_path(stage1), "_module": slot.module}
    if slot.slot_id == "C2":
        return {"type": "content", "title": slot.title, "bullets": _thinking_formula(stage1), "_module": slot.module}
    if slot.slot_id == "C3":
        pts = _bullets(stage1, 3)
        return {
            "type": "content",
            "title": slot.title,
            "bullets": pts or ["对比维度", "因果维度", "深层意义维度（每页一个）"],
            "_module": slot.module,
        }
    if slot.slot_id == "F1s":
        return {
            "type": "content",
            "title": slot.title,
            "badge": "动笔易错",
            "warn_panel": True,
            "panel": True,
            "bullets": _stage4_warn(stage4),
            "_module": slot.module,
        }
    if slot.spec_kind == "peel":
        return {
            "type": "peel",
            "title": slot.title,
            "points": _peel_from_stage2(stage2),
            "_module": slot.module,
        }
    if slot.slot_id == "D6":
        text = _extract_essay_block(stage2, "基础版") or _extract_essay_block(stage2, "基础")
        if not text and stage2:
            text = stage2[:800] + ("…" if len(stage2) > 800 else "")
        return {
            "type": "essay",
            "title": "基础版范文",
            "essay_text": text or "（见源稿 Stage2 基础版范文）",
            "annotation": "",
            "_module": slot.module,
        }
    if slot.slot_id == "D7":
        text = _extract_essay_block(stage2, "进阶版") or _extract_essay_block(stage2, "高分版 A")
        if not text:
            text = _extract_essay_block(stage2, "高分版")
        return {
            "type": "essay",
            "title": "高分版 A",
            "essay_text": text or "（见源稿 Stage2 高分版 A）",
            "annotation": "",
            "_module": slot.module,
        }
    if slot.slot_id == "D8":
        text = _extract_essay_block(stage2, "高分版 B") or _extract_essay_block(stage2, "逻辑")
        return {
            "type": "essay",
            "title": "高分版 B",
            "essay_text": text or "（见源稿 Stage2 高分版 B）",
            "annotation": "",
            "_module": slot.module,
        }
    if slot.spec_kind == "table":
        parsed = _compare_table_rows(stage2)
        headers = parsed[0] if parsed else ["维度", "基础版", "高分版 A", "高分版 B"]
        body = parsed[1:] if len(parsed) > 1 else []
        return {
            "type": "table",
            "title": slot.title,
            "headers": headers,
            "rows": body,
            "_module": slot.module,
        }
    if slot.slot_id == "D10":
        upgrades = _upgrade_bullets_from_stage2(stage2)
        return {
            "type": "content",
            "title": slot.title,
            "bullets": upgrades or _bullets(stage2, 4),
            "_module": slot.module,
        }
    if slot.slot_id == "F2s":
        return {
            "type": "content",
            "title": slot.title,
            "badge": "当堂操练",
            "bullets": _stage4_review(stage4),
            "_module": slot.module,
        }
    if slot.slot_id == "F3s":
        return {
            "type": "content",
            "title": slot.title,
            "badge": "迁移练",
            "bullets": _stage4_migration(stage4, question),
            "_module": slot.module,
        }
    if slot.slot_id == "G1":
        g1, _ = _closing_slides(data)
        return {"type": "content", "title": slot.title, "bullets": g1, "_module": slot.module}
    if slot.slot_id == "G2":
        _, g2 = _closing_slides(data)
        return {"type": "content", "title": slot.title, "bullets": g2, "_module": slot.module}
    return None


def build_architecture_deck(
    data: dict[str, Any],
    *,
    preset: LessonPreset = "70min",
) -> list[dict]:
    """Build fixed-architecture slide specs (Stage3 filled later via deck_plan)."""
    slides: list[dict] = []

    for slot in slots_for_preset(preset):
        if slot.spec_kind == "stage3_placeholder":
            slides.append({"type": "_stage3_placeholder", "_module": "E"})
            continue
        spec = build_slot_spec(slot, data)
        if spec is None:
            if slot.optional:
                continue
            raise ValueError(f"unhandled slot {slot.slot_id}")
        if isinstance(spec, list):
            for item in spec:
                if "_module" not in item:
                    item["_module"] = slot.module
                slides.append(item)
        else:
            if "_module" not in spec:
                spec["_module"] = slot.module
            slides.append(spec)
    return slides


def inject_module_dividers(slides: list[dict], *, enabled: bool = False) -> list[dict]:
    """Insert module divider before first slide of each module.

    Default ``enabled=False``: rely on per-slide section tags in V2 headers instead
    of full-screen A–G divider pages (less blank space, tighter deck).
    """
    cleaned: list[dict] = []
    for spec in slides:
        if spec.get("type") == "_stage3_placeholder":
            continue
        cleaned.append(spec)

    if not enabled:
        return [{k: v for k, v in spec.items() if not k.startswith("_")} for spec in cleaned]

    from scripts.generate_classroom_pptx_v2 import CORAL, INDIGO, MINT, SKY, VIOLET

    colors = {
        "INDIGO": INDIGO,
        "CORAL": CORAL,
        "MINT": MINT,
        "SKY": SKY,
        "VIOLET": VIOLET,
    }
    num_map = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F", "G": "G"}
    out: list[dict] = []
    seen: set[str] = set()

    for spec in cleaned:
        mod = spec.get("_module") or _module_from_title(spec.get("title", ""))
        if mod and mod not in seen and mod in MODULE_DIVIDERS:
            name, sub, color_key = MODULE_DIVIDERS[mod]
            out.append(
                {
                    "type": "divider",
                    "num": num_map.get(mod, mod),
                    "name": name,
                    "subtitle": sub,
                    "color": colors[color_key],
                }
            )
            seen.add(mod)
        out.append({k: v for k, v in spec.items() if not k.startswith("_")})
    return out


def _module_from_title(title: str) -> str:
    if title.startswith("导入"):
        return "A"
    if title.startswith("审题"):
        return "B"
    if title.startswith("思维"):
        return "C"
    if "PEEL" in title or "范文" in title or "三版" in title:
        return "D"
    if title.startswith("功能句型") or title.startswith("话题词块"):
        return "E"
    if "迁移" in title or "讲评" in title or "易错" in title:
        return "F"
    if "小结" in title or "课后" in title:
        return "G"
    return ""


def merge_stage3_into_architecture_deck(
    deck: list[dict],
    stage3_specs: list[dict],
) -> list[dict]:
    """Replace _stage3_placeholder with Stage3 specs."""
    out: list[dict] = []
    inserted = False
    for spec in deck:
        if spec.get("type") == "_stage3_placeholder":
            if not inserted:
                for s in stage3_specs:
                    s["_module"] = "E"
                out.extend(stage3_specs)
                inserted = True
            continue
        out.append(spec)
    if not inserted:
        for s in stage3_specs:
            s["_module"] = "E"
        out.extend(stage3_specs)
    return out


def load_export_data(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_source_markdown_sections(md_path: Path) -> dict[str, Any]:
    """Parse yingyongwen-source.md back into export sections."""
    text = md_path.read_text(encoding="utf-8")
    data: dict[str, Any] = {"meta": None, "question_type_label": None}
    labels_rev = {
        "题目原文": "question",
        STAGE_TITLES[1]: "stage1",
        STAGE_TITLES[2]: "stage2",
        STAGE_TITLES[3]: "stage3",
        STAGE_TITLES[4]: "stage4",
    }
    current: str | None = None
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("> ") and not data.get("meta"):
            data["meta"] = line[2:].strip()
            continue
        if line.startswith("**题目类型：**"):
            data["question_type_label"] = line.split("：", 1)[-1].strip().strip("*")
            continue
        if line.startswith("## "):
            if current:
                data[current] = "\n".join(buf).strip()
            heading = line[3:].strip()
            current = labels_rev.get(heading)
            buf = []
            continue
        if current is not None:
            buf.append(line)
    if current:
        data[current] = "\n".join(buf).strip()
    return data


def build_full_deck_from_export(
    export_data: dict[str, Any],
    stage3_path: Path,
    deck_plan_path: Path | None,
    *,
    preset: LessonPreset = "70min",
    vocab_max_rows: int = 6,
) -> list[dict]:
    from scripts.deck_plan import (
        deck_plan_from_stage3,
        load_deck_plan,
        refine_deck_plan,
        stage3_specs_from_plan,
    )

    stage3_data = json.loads(stage3_path.read_text(encoding="utf-8"))
    if deck_plan_path and deck_plan_path.is_file():
        plan = load_deck_plan(deck_plan_path, stage3_data, vocab_max_rows=vocab_max_rows)
    else:
        plan = deck_plan_from_stage3(stage3_data, vocab_max_rows=vocab_max_rows)
        plan = refine_deck_plan(stage3_data, plan, vocab_max_rows=vocab_max_rows)
    stage3_specs = stage3_specs_from_plan(stage3_data, plan)

    base = build_architecture_deck(export_data, preset=preset)
    merged = merge_stage3_into_architecture_deck(base, stage3_specs)
    return inject_module_dividers(merged)
