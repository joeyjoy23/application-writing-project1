"""Filter classroom / export text into student-facing PPT bullets (Architecture V1).

Teacher-only content (教师操作 / 教师引导 / 教案时长) must not appear on slides.
"""

from __future__ import annotations

import re
from typing import Any

# Lines that belong in teacher notes, not student projection.
_TEACHER_LINE_RE = re.compile(
    r"教师(?:操作|引导)|反馈方式|高发原因|学情适配|当前学生水平|"
    r"使用素材|目标[：:]|总时长|教师可选用|活动链设计",
    re.IGNORECASE,
)

_GUIDANCE_QUOTE_RE = re.compile(r"^\s*引导[：:]", re.IGNORECASE)

_TIMING_PREFIX_RE = re.compile(
    r"^[\s*]*(?:\d+\s*[′'']|\d+\s*分钟)\s*",
    re.IGNORECASE,
)

_STUDENT_INSIGHT_MARKERS = ("陷阱", "高分关键", "最危险", "一句大实话")

# Prompt / teacher-schema tokens that must not appear on student slides.
_TEACHER_META_RE = re.compile(
    r"mandatory_point\s*"
    r"|要点指定[：:]\s*"
    r"|(?:考查|设计)能力[：:][^\n]*"
    r"|设计意图[：:][^\n]*"
    r"|升级提示[：:][^\n]*"
    r"|示范答案[：:][^\n]*"
    r"|思考提示[：:][^\n]*"
    r"|(?:适合|面向)(?:基础|中等|进阶)[^\n]*",
    re.IGNORECASE,
)


def sanitize_student_text(text: str) -> str:
    """Remove teacher-only schema tokens from text shown to students."""
    t = _TEACHER_META_RE.sub("", str(text))
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_teacher_only_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if _TEACHER_LINE_RE.search(t):
        return True
    if t.startswith("源报告：") or t.startswith("Joyverse ·"):
        return True
    return False


def is_student_insight_quote(text: str) -> bool:
    t = text.strip().lstrip("💡").strip()
    if _GUIDANCE_QUOTE_RE.match(t):
        return False
    return any(m in t for m in _STUDENT_INSIGHT_MARKERS) or t.startswith("陷阱")


def normalize_activity_line(line: str) -> str:
    """Turn '10′ 元素拆解（看海报→造句）' into student task without timing."""
    t = re.sub(r"<[^>]+>", "", line.strip())
    t = _TIMING_PREFIX_RE.sub("", t).strip()
    t = re.sub(r"\s+", " ", t)
    return t


def student_bullets_from_slide(
    slide: dict[str, Any],
    *,
    include_insight_quote: bool = True,
    max_items: int = 5,
) -> list[str]:
    """Extract student-facing bullets; drop teacher quotes and meta."""
    bullets: list[str] = []
    quote = (slide.get("quote") or "").strip()
    if include_insight_quote and quote and is_student_insight_quote(quote):
        bullets.append(f"💡 {quote.lstrip('💡').strip()}")

    for raw in slide.get("bullets") or []:
        line = re.sub(r"<[^>]+>", "", str(raw)).strip()
        line = re.sub(r"\s+", " ", line)
        if not line or is_teacher_only_line(line):
            continue
        if _GUIDANCE_QUOTE_RE.match(line):
            continue
        if "活动" in slide.get("data_title", "") or "教学" in slide.get("tag", ""):
            line = normalize_activity_line(line)
        bullets.append(line)

    for card in slide.get("cards") or []:
        for part in str(card).split("\n"):
            line = re.sub(r"<[^>]+>", "", part).strip()
            if line and not is_teacher_only_line(line):
                bullets.append(line)

    seen: set[str] = set()
    out: list[str] = []
    for b in bullets:
        key = b.lower()
        if key not in seen:
            seen.add(key)
            out.append(b)
        if len(out) >= max_items:
            break
    return out


def _extract_li_blocks(stage4: str, heading_pattern: str, max_n: int = 5) -> list[str]:
    m = re.search(heading_pattern, stage4, flags=re.DOTALL | re.IGNORECASE)
    if not m:
        return []
    block = m.group(1)
    out: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or is_teacher_only_line(line):
            continue
        if line.startswith("- ") or line.startswith("• "):
            item = line[2:].strip()
            if item and not is_teacher_only_line(item):
                out.append(item)
        if len(out) >= max_n:
            break
    return out


def parse_stage4_student_from_export(stage4: str) -> dict[str, list[str]]:
    """Parse export Stage4 markdown into student-facing bullet groups."""
    if not stage4.strip():
        return {"warn": [], "activities": [], "migration": []}

    warn: list[str] = []
    err_block = re.search(
        r"二、典型错误预警\s*(.*?)(?=---|\n三、|$)",
        stage4,
        flags=re.DOTALL | re.IGNORECASE,
    )
    err_text = err_block.group(1) if err_block else stage4
    for m in re.finditer(
        r"^\d+\.\s*(.+?)[：:]\s*(.+)$",
        err_text,
        flags=re.MULTILINE,
    ):
        title = re.sub(r"\*\*", "", m.group(1)).strip().strip('"\'""''')
        example = sanitize_student_text(m.group(2).strip())
        if not title or "教师" in title or title.startswith("高发"):
            continue
        if example and not example.startswith("教师"):
            warn.append(f"❌ {title} — {example[:90]}")
        if len(warn) >= 5:
            break
    if not warn:
        for m in re.finditer(
            r"^\d+\.\s*\*\*(.+?)\*\*[：:]\s*(.+)$",
            err_text,
            flags=re.MULTILINE,
        ):
            title = m.group(1).strip()
            example = sanitize_student_text(m.group(2).strip())
            if "教师" not in title and example:
                warn.append(f"❌ {title} — {example[:90]}")
            if len(warn) >= 5:
                break

    activities: list[str] = []
    for m in re.finditer(
        r"学生任务[：:]\s*(.+?)(?=\n[-*]|\n\n|反馈方式|教师操作|$)",
        stage4,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        task = re.sub(r"\s+", " ", m.group(1).strip())
        if task and len(task) > 8:
            activities.append(task[:120])
        if len(activities) >= 4:
            break

    if not activities:
        for m in re.finditer(
            r"活动\d+[：:][^\n]*\n(?:.*?\n)*?.*?学生任务[：:]\s*(.+?)(?=\n[-*]|\n\n|反馈方式|$)",
            stage4,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            task = re.sub(r"\s+", " ", m.group(1).strip())[:120]
            if task:
                activities.append(task)
            if len(activities) >= 4:
                break

    migration: list[str] = []
    for m in re.finditer(
        r"写作题[：:]\s*(.+?)(?=\n[-*]考查|设计意图|思考提示|练习\d|$)",
        stage4,
        flags=re.DOTALL | re.IGNORECASE,
    ):
        item = sanitize_student_text(m.group(1).strip())[:160]
        if item and "mandatory_point" not in item.lower():
            migration.append(item)
        if len(migration) >= 2:
            break

    mig_fallback = _extract_li_blocks(stage4, r"三、课后练习题\s*(.*)", 4)
    for item in mig_fallback:
        clean = sanitize_student_text(item)
        if not clean or "mandatory_point" in clean.lower():
            continue
        if "写作题" in item or "迁移" in item or "Personal Growth" in item:
            migration.append(clean[:160])
    migration = migration[:3]

    if not warn:
        warn = [
            "❌ 理由空泛 — 只写 important / necessary，缺少个人化情境",
            "❌ 排序变流水账 — 三件事各说一段，没有真正权衡",
            "❌ 语气不当 — Dear editor 或 I suggest that…（体裁不符）",
        ]

    if not activities:
        activities = [
            "排序理由三层过滤：哪个版本更像「真实的我」？",
            "画因果鱼骨图：Study 第一 → Sleep 第二 → Socialize 第三",
            "给睡眠/社交写一个画面，替代定义式空话",
            "限时完稿 + 同桌「可信度温度计」互评",
        ]

    return {"warn": warn[:3], "activities": activities[:4], "migration": migration[:3]}


def stage1_thinking_slides_from_export(stage1: str) -> list[dict[str, Any]]:
    """Module C slides (GPT V1): 高分路径 + 高分公式 — from Stage1 export."""
    if not stage1.strip():
        return []
    path_pts: list[str] = []
    for kw in ("画面", "象征", "主题", "理由", "路径"):
        for m in re.finditer(rf"^[-*•]\s+(.+{kw}.+)$", stage1, flags=re.MULTILINE | re.IGNORECASE):
            path_pts.append(m.group(1).strip())
    if len(path_pts) < 2:
        path_pts = [
            "明确排序立场",
            "↓",
            "因果链 / 价值权衡",
            "↓",
            "个人化收束",
        ]
    formula = "排序立场 + 具体理由 + 权衡取舍 + 个人体悟"
    return [
        {
            "type": "content",
            "title": "思维 · 高分路径",
            "bullets": path_pts[:4],
            "_module": "C",
        },
        {
            "type": "content",
            "title": "思维 · 高分公式",
            "bullets": [formula],
            "_module": "C",
        },
    ]
