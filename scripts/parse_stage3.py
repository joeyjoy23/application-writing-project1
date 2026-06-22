"""Parse Stage 3 markdown (Joyverse export) into structured JSON."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_PHRASE_TABLE_RE = re.compile(r"表格\s*\d+\s*[：:]\s*(.+?)(?=表格\s*\d+\s*[：:]|二、话题词汇|$)", re.DOTALL)
_VOCAB_SECTION_RE = re.compile(r"二、话题词汇锦囊\s*(.*)", re.DOTALL)
_VOCAB_FIELD_RE = re.compile(r"语义场\s*\d+\s*[：:]\s*(.+?)(?=语义场\s*\d+\s*[：:]|$)", re.DOTALL)
_TIER_LEVELS = ("基础句", "进阶句", "高级句")
_VOCAB_TIERS = ("必备级", "进阶级", "亮点级")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\t", " ").strip())


def _strip_dash(s: str | None) -> str | None:
    if s is None:
        return None
    t = _clean(s)
    if t in ("—", "-", "–", ""):
        return None
    return t


def _parse_phrase_table(block: str) -> dict[str, Any]:
    name_m = re.match(r"^(.+?)\n", block.strip())
    raw_name = _clean(name_m.group(1)) if name_m else "功能句型"
    name = re.sub(r"^表格\s*\d+\s*[：:]\s*", "", raw_name).strip() or raw_name
    body = block[name_m.end() :] if name_m else block

    tiers: list[dict[str, Any]] = []
    for level in _TIER_LEVELS:
        m = re.search(
            rf"^{re.escape(level)}\s*\n(.+?)\n(.+?)\n(.+?)(?:\n|$)",
            body,
            flags=re.MULTILINE | re.DOTALL,
        )
        if not m:
            continue
        tiers.append(
            {
                "level": level,
                "english": _clean(m.group(1)),
                "chinese": _clean(m.group(2)),
                "high_score": _strip_dash(_clean(m.group(3))),
            }
        )

    topic_m = re.search(r"本题[：:]\s*(.+?)(?=\n改一句|\Z)", body, flags=re.DOTALL)
    topic_note = _clean(topic_m.group(1)) if topic_m else ""

    fix_m = re.search(r"改一句\s*\n(.+)", body, flags=re.DOTALL)
    fix_bad, fix_good = "", ""
    if fix_m:
        fix_body = fix_m.group(1)
        fix_body = re.split(r"\n表格\s*\d+", fix_body)[0]
        lines = [ln.strip() for ln in fix_body.splitlines() if ln.strip()]
        for ln in lines:
            if ln.startswith("→") or ln.startswith("->"):
                fix_good = ln
            elif "❌" in ln or (not fix_bad and "✅" not in ln):
                fix_bad = ln

    return {
        "name": name,
        "tiers": tiers,
        "topic_note": topic_note,
        "fix_bad": fix_bad,
        "fix_good": fix_good,
    }


def _parse_vocab_tier(block: str, level: str) -> dict[str, Any]:
    m = re.search(rf"{re.escape(level)}\s*\n(.+)", block, flags=re.DOTALL)
    if not m:
        return {"level": level, "rows": []}
    sub = m.group(1)
    # stop at next tier
    for other in _VOCAB_TIERS:
        if other != level:
            sub = re.split(rf"\n{re.escape(other)}\s*\n", sub, maxsplit=1)[0]

    lines = [ln.rstrip("\t") for ln in sub.splitlines()]
    # skip header block until first english row
    data_lines: list[str] = []
    passed_header = False
    for ln in lines:
        t = ln.strip()
        if not t:
            continue
        if not passed_header:
            if "英文词块" in t or "中文释义" in t or "具体使用例句" in t:
                continue
            passed_header = True
        data_lines.append(t)

    rows: list[dict[str, str]] = []
    i = 0
    while i + 2 < len(data_lines):
        eng, chi, ex = data_lines[i], data_lines[i + 1], data_lines[i + 2]
        if eng in _VOCAB_TIERS or "语义场" in eng:
            break
        rows.append({"english": _clean(eng), "chinese": _clean(chi), "example": _clean(ex)})
        i += 3

    return {"level": level, "rows": rows}


def _parse_vocab_field(block: str) -> dict[str, Any]:
    name_m = re.match(r"^(.+?)\n", block.strip())
    name = _clean(name_m.group(1)) if name_m else "词块"
    body = block[name_m.end() :] if name_m else block
    tiers = [_parse_vocab_tier(body, level) for level in _VOCAB_TIERS]
    return {"name": name, "tiers": tiers}


def parse_stage3_markdown(text: str) -> dict[str, Any]:
    """Parse Stage 3 body text into phrase_tables + vocab_fields."""
    text = text.strip()
    # strip leading stage title if present
    text = re.sub(r"^#+\s*Stage\s*3.*?\n", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^一、功能句型包\s*", "一、功能句型包\n", text)

    phrase_part = text.split("二、话题词汇锦囊")[0]
    phrase_tables = [
        _parse_phrase_table(m.group(0))
        for m in _PHRASE_TABLE_RE.finditer(phrase_part)
    ]

    vocab_part = ""
    vm = _VOCAB_SECTION_RE.search(text)
    if vm:
        vocab_part = vm.group(1)
    vocab_fields = [
        _parse_vocab_field(m.group(0)) for m in _VOCAB_FIELD_RE.finditer(vocab_part)
    ]

    return {"phrase_tables": phrase_tables, "vocab_fields": vocab_fields}


def parse_stage3_file(path: Path) -> dict[str, Any]:
    return parse_stage3_markdown(path.read_text(encoding="utf-8"))


def write_stage3_json(data: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
