# DEPRECATED (2026-06-20): Do not use in default classroom PPT workflow.
# Rewrite failing slide SVGs per PPT_LAYOUT_LAW §5 instead of patching coordinates.
# See: .cursor/skills/yingyongwen-export-to-ppt/PPT_LAYOUT_LAW.md
#      .cursor/skills/yingyongwen-export-to-ppt/SKILL.md
"""V3 SVG: restore ppt-master baseline layout, add reveal groups without moving coords."""

from __future__ import annotations

import re
import shutil
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

BASELINE_BACKUP = "20260620_083711"
FONT_SCALE = {"26": "35", "28": "38", "32": "43", "38": "51", "44": "59", "35": "47"}

# Minimum SVG px → ~26pt in PowerPoint after ppt-master 0.75 conversion
MIN_BODY_PX = 35


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _tag(elem: ET.Element) -> str:
    return elem.tag.replace(f"{{{SVG_NS}}}", "")


def scale_fonts(text: str) -> str:
    def repl(m: re.Match) -> str:
        size = m.group(1)
        return f'font-size="{FONT_SCALE.get(size, size)}"'

    return re.sub(r'font-size="(\d+)"', repl, text)


def _wrap_chars(text: str, width: int) -> list[str]:
    return textwrap.wrap(text, width=width, break_long_words=False)


def wrap_top_level_reveals(svg_text: str, *, header_ids: frozenset[str] = frozenset()) -> str:
    """Wrap each top-level shape in reveal-NN; merge header chrome into one static group."""
    root = ET.fromstring(svg_text)
    bg: ET.Element | None = None
    header_parts: list[ET.Element] = []
    body: list[ET.Element] = []
    idx = 1

    for child in list(root):
        if _tag(child) == "rect" and child.get("width") == "1280" and child.get("height") == "720":
            bg = child
            continue
        y_hint = 0.0
        if _tag(child) == "text":
            y_hint = float(re.findall(r"[\d.]+", child.get("y", "999") or "999")[0])
        elif _tag(child) == "rect":
            y_hint = float(child.get("y", "999") or "999")
        if y_hint <= 80 or child.get("id") in header_ids:
            header_parts.append(child)
        else:
            body.append(child)

    new_root = ET.Element(f"{{{SVG_NS}}}svg", viewBox="0 0 1280 720", width="1280", height="720")
    if bg is not None:
        new_root.append(bg)
    if header_parts:
        new_root.append(_group("header", *header_parts))

    for elem in body:
        new_root.append(_group(f"reveal-{idx:02d}", elem))
        idx += 1

    out = ET.tostring(new_root, encoding="unicode")
    if not out.startswith("<?xml"):
        out = '<?xml version="1.0" encoding="UTF-8"?>\n' + out
    return out


def _group(gid: str, *children: ET.Element) -> ET.Element:
    g = ET.Element(f"{{{SVG_NS}}}g", id=gid)
    for c in children:
        g.append(c)
    return g


def build_cover_svg() -> str:
    lines = [
        "假如你是李华，James 参加心理健康活动周海报设计大赛，请你回复邮件：",
        "（1）你的选择；（2）说明理由。",
        'Poster 1：裂痕微笑之心 — "It\'s okay not to be okay."',
        'Poster 2：浇水壶与心形叶子 — "Water your heart"',
    ]
    tspans = []
    y0 = 400
    for i, line in enumerate(lines):
        dy = "0" if i == 0 else "40"
        tspans.append(f'    <tspan x="72" dy="{dy}">{_esc(line)}</tspan>')
    tspan_block = "\n".join(tspans)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#FFFFFF"/>
  <g id="header">
    <rect x="0" y="0" width="1280" height="260" fill="#6366F1"/>
    <rect x="0" y="260" width="1280" height="6" fill="#14B8A6"/>
    <rect x="48" y="44" width="168" height="44" rx="8" fill="#8B5CF6"/>
    <text x="64" y="74" font-family="Microsoft YaHei, Arial, sans-serif" font-size="35" font-weight="bold" fill="#FFFFFF">观点理由类</text>
    <text x="48" y="148" font-family="Microsoft YaHei, Arial, sans-serif" font-size="51" font-weight="bold" fill="#FFFFFF">高考英语应用文</text>
    <text x="48" y="204" font-family="Microsoft YaHei, Arial, sans-serif" font-size="43" fill="#DDD6FE">心理健康周海报选题</text>
  </g>
  <g id="reveal-01">
    <text x="48" y="310" font-family="Microsoft YaHei, Arial, sans-serif" font-size="38" font-weight="bold" fill="#1E293B">题目原文</text>
  </g>
  <g id="reveal-02">
    <rect x="48" y="330" width="1184" height="330" rx="16" fill="#F5F3FF" stroke="#E2E8F0" stroke-width="2"/>
  </g>
  <g id="reveal-03">
    <text x="72" y="{y0}" font-family="Microsoft YaHei, Arial, sans-serif" font-size="35" fill="#1E293B">
{tspan_block}
    </text>
  </g>
</svg>
'''


def build_key_insight_svg() -> str:
    trap = "只说「我觉得哪个好」，不分析设计元素与心理健康主题关联"
    key = "用具体细节支撑选择：裂痕象征真实情绪，浇水象征自我关怀"
    trap_lines = _wrap_chars(trap, 36)
    key_lines = _wrap_chars(key, 38)
    trap_tspans = "\n".join(
        f'      <tspan x="72" dy="{"0" if i == 0 else "38"}">{_esc(ln)}</tspan>'
        for i, ln in enumerate(trap_lines)
    )
    key_tspans = "\n".join(
        f'      <tspan x="72" dy="{"0" if i == 0 else "38"}">{_esc(ln)}</tspan>'
        for i, ln in enumerate(key_lines)
    )
    banner_h = 100 + len(trap_lines) * 38
    panel_top = 120 + banner_h + 24
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">
  <rect width="1280" height="720" fill="#FFFFFF"/>
  <g id="header">
    <rect x="0" y="0" width="1280" height="76" fill="#6366F1"/>
    <rect x="0" y="76" width="1280" height="4" fill="#14B8A6"/>
    <text x="48" y="52" font-family="Microsoft YaHei, Arial, sans-serif" font-size="51" font-weight="bold" fill="#FFFFFF">一句大实话</text>
  </g>
  <g id="reveal-01">
    <rect x="48" y="108" width="1184" height="{banner_h}" rx="12" fill="#F59E0B"/>
    <text x="72" y="148" font-family="Microsoft YaHei, Arial, sans-serif" font-size="38" font-weight="bold" fill="#FFFFFF">最危险陷阱</text>
    <text x="72" y="188" font-family="Microsoft YaHei, Arial, sans-serif" font-size="35" fill="#FFFFFF">
{trap_tspans}
    </text>
  </g>
  <g id="reveal-02">
    <rect x="48" y="{panel_top}" width="1184" height="{680 - panel_top}" rx="12" fill="#F5F3FF" stroke="#6366F1" stroke-width="3"/>
    <text x="72" y="{panel_top + 44}" font-family="Microsoft YaHei, Arial, sans-serif" font-size="38" font-weight="bold" fill="#6366F1">高分关键</text>
    <text x="72" y="{panel_top + 88}" font-family="Microsoft YaHei, Arial, sans-serif" font-size="35" fill="#1E293B">
{key_tspans}
    </text>
  </g>
</svg>
'''


def build_panel_bullets_svg(
    *,
    tag: str | None = None,
    title: str,
    bullets: list[str],
    tag_color: str = "#6366F1",
) -> str:
    """One content panel, bullets stacked with breathing room — not one card per line."""
    header_lines = [
        '  <rect width="1280" height="720" fill="#FFFFFF"/>',
        '  <g id="header">',
        '    <rect x="0" y="0" width="1280" height="76" fill="#6366F1"/>',
        '    <rect x="0" y="76" width="1280" height="4" fill="#14B8A6"/>',
    ]
    if tag:
        tw = len(tag) * 24 + 56
        header_lines += [
            f'    <rect x="48" y="18" width="{tw}" height="40" rx="8" fill="{tag_color}"/>',
            f'    <text x="60" y="46" font-family="Microsoft YaHei, Arial, sans-serif" font-size="35" font-weight="bold" fill="#FFFFFF">{_esc(tag)}</text>',
            f'    <text x="{tw + 64}" y="46" font-family="Microsoft YaHei, Arial, sans-serif" font-size="51" font-weight="bold" fill="#FFFFFF">{_esc(title)}</text>',
        ]
    else:
        header_lines.append(
            f'    <text x="48" y="52" font-family="Microsoft YaHei, Arial, sans-serif" font-size="51" font-weight="bold" fill="#FFFFFF">{_esc(title)}</text>'
        )
    header_lines.append("  </g>")

    panel_top, panel_h = 96, 600
    parts = header_lines + [
        '  <g id="reveal-01">',
        f'    <rect x="48" y="{panel_top}" width="1184" height="{panel_h}" rx="16" fill="#F5F3FF" stroke="#E2E8F0" stroke-width="2"/>',
        "  </g>",
    ]
    y = panel_top + 52
    step = 72 if len(bullets) <= 5 else 58
    for i, bullet in enumerate(bullets, start=2):
        wrapped = _wrap_chars(bullet, 42 if len(bullet) > 30 else 50)
        if len(wrapped) == 1:
            parts.append(
                f'  <g id="reveal-{i:02d}"><text x="72" y="{y}" font-family="Microsoft YaHei, Arial, sans-serif" font-size="38" fill="#1E293B">{_esc(wrapped[0])}</text></g>'
            )
            y += step
        else:
            tspans = "\n".join(
                f'      <tspan x="72" dy="{"0" if j == 0 else "36"}">{_esc(ln)}</tspan>'
                for j, ln in enumerate(wrapped)
            )
            parts.append(
                f'  <g id="reveal-{i:02d}"><text x="72" y="{y}" font-family="Microsoft YaHei, Arial, sans-serif" font-size="38" fill="#1E293B">\n{tspans}\n    </text></g>'
            )
            y += step + (len(wrapped) - 1) * 36

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        + '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">\n'
        + "\n".join(parts)
        + "\n</svg>\n"
    )


def build_peel_svg() -> str:
    left = [
        ("Point 1 选择", True, "#6366F1", "Microsoft YaHei, Arial, sans-serif"),
        ("P: I'd go with Poster 1.", False, "#1E293B", "Times New Roman, Times, serif"),
        ("E: cracked heart + smile", False, "#1E293B", "Microsoft YaHei, Arial, sans-serif"),
        ('   + "It\'s okay not to be okay"', False, "#1E293B", "Microsoft YaHei, Arial, sans-serif"),
        ("L: Here's why I think so.", False, "#1E293B", "Times New Roman, Times, serif"),
    ]
    right = [
        ("Point 2 理由", True, "#14B8A6", "Microsoft YaHei, Arial, sans-serif"),
        ("P: The cracked heart captures", False, "#1E293B", "Times New Roman, Times, serif"),
        ("   mental health essence.", False, "#1E293B", "Times New Roman, Times, serif"),
        ("E: crack = struggles;", False, "#1E293B", "Times New Roman, Times, serif"),
        ("   smile = acceptance", False, "#1E293B", "Microsoft YaHei, Arial, sans-serif"),
        ("L: Poster 1 feels authentic", False, "#1E293B", "Times New Roman, Times, serif"),
        ("   and resonant.", False, "#1E293B", "Times New Roman, Times, serif"),
    ]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">',
        '  <rect width="1280" height="720" fill="#FFFFFF"/>',
        '  <g id="header">',
        '    <rect x="0" y="0" width="1280" height="76" fill="#6366F1"/>',
        '    <rect x="0" y="76" width="1280" height="4" fill="#14B8A6"/>',
        '    <rect x="48" y="18" width="72" height="40" rx="8" fill="#14B8A6"/>',
        '    <text x="60" y="46" font-family="Microsoft YaHei, Arial, sans-serif" font-size="35" font-weight="bold" fill="#FFFFFF">范文</text>',
        '    <text x="136" y="46" font-family="Microsoft YaHei, Arial, sans-serif" font-size="51" font-weight="bold" fill="#FFFFFF">PEEL 写作骨架</text>',
        "  </g>",
        '  <g id="reveal-01"><rect x="48" y="96" width="580" height="580" rx="12" fill="#F5F3FF" stroke="#6366F1" stroke-width="2"/></g>',
        '  <g id="reveal-02"><rect x="652" y="96" width="580" height="580" rx="12" fill="#ECFEFF" stroke="#14B8A6" stroke-width="2"/></g>',
    ]
    idx = 3
    y = 140
    for line, bold, color, ff in left:
        fw = "bold" if bold else "normal"
        fs = 43 if bold else 38
        parts.append(
            f'  <g id="reveal-{idx:02d}"><text x="72" y="{y}" font-family="{ff}" font-size="{fs}" font-weight="{fw}" fill="{color}">{_esc(line)}</text></g>'
        )
        idx += 1
        y += 50 if bold else 44
    y = 140
    for line, bold, color, ff in right:
        fw = "bold" if bold else "normal"
        fs = 43 if bold else 38
        parts.append(
            f'  <g id="reveal-{idx:02d}"><text x="676" y="{y}" font-family="{ff}" font-size="{fs}" font-weight="{fw}" fill="{color}">{_esc(line)}</text></g>'
        )
        idx += 1
        y += 50 if bold else 44
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def patch_all(project_dir: Path, essay_builder) -> None:
    final = project_dir / "svg_final"
    output = project_dir / "svg_output"
    output.mkdir(exist_ok=True)

    baseline = project_dir / "backup" / BASELINE_BACKUP / "svg_output"
    if not baseline.is_dir():
        raise FileNotFoundError(f"Missing baseline backup: {baseline}")

    for src in baseline.glob("*.svg"):
        text = scale_fonts(src.read_text(encoding="utf-8"))
        (final / src.name).write_text(text, encoding="utf-8")

    custom = {
        "01_cover.svg": build_cover_svg(),
        "02_task_type.svg": build_panel_bullets_svg(
            tag="审题",
            title="题型与动笔自检",
            bullets=[
                "观点理由类 — 题干要求「你的选择」+「说明理由」",
                "1. 语气 — 朋友间建议 vs 正式报告？",
                "2. 结构 — 主体段有具体理由还是只有「我觉得好」？",
                "3. 逻辑 — 是否说明为什么选，也解释为什么不选另一个？",
                "4. 立意 — 是否写出心理健康深层意义？",
                "5. 语言 — 是否用「裂痕」「浇水」等关键表达？",
            ],
        ),
        "04_genre_ability.svg": build_panel_bullets_svg(
            title="体裁规范与能力维度",
            bullets=[
                "体裁：邮件 · 时态：一般现在时 · 人称：第一人称 · 语气：友好建议",
                "能力维度：观点表达与说理论证（立场→理由→辩证分析）",
                "思维路径：确定选择 → 分析设计元素与主题关联 → 细节支撑",
                "高分要点：观点具体性 + 论据支撑（裂痕/双手/浇水壶/植物）",
            ],
        ),
        "06_key_insight.svg": build_key_insight_svg(),
        "08_peel_skeleton.svg": build_peel_svg(),
        "14_phrases_opinion.svg": build_panel_bullets_svg(
            title="功能句型 · 观点表达",
            bullets=[
                "基础：I prefer Poster 1.",
                "进阶：I'm leaning towards Poster 1, as its design stands out.",
                "高级：Poster 1 strikes me as more compelling due to emotional resonance.",
            ],
        ),
        "15_phrases_evidence.svg": build_panel_bullets_svg(
            title="功能句型 · 论据支撑",
            bullets=[
                "基础：Poster 1 is good because it has a cracked heart.",
                "进阶：The cracked yet smiling heart conveys acceptance.",
                "高级：The visual metaphor speaks volumes about support.",
            ],
        ),
        "16_phrases_logic.svg": build_panel_bullets_svg(
            title="功能句型 · 逻辑衔接",
            bullets=[
                "基础：First... Second...",
                "进阶：Firstly... secondly...",
                "高级：On one hand... on the other hand...",
            ],
        ),
    }
    for name, svg in custom.items():
        (final / name).write_text(svg, encoding="utf-8")
        print(f"  custom layout: {name}")

    essay_builder(final)
    for name in ("09_essay_basic.svg", "10_essay_advanced_a.svg", "11_essay_advanced_b.svg"):
        if (final / name).exists():
            shutil.copy2(final / name, output / name)

    skip_rewrap = set(custom) | {
        "09_essay_basic.svg",
        "10_essay_advanced_a.svg",
        "11_essay_advanced_b.svg",
    }
    for path in sorted(final.glob("*.svg")):
        if path.name in skip_rewrap:
            text = path.read_text(encoding="utf-8")
        else:
            raw = path.read_text(encoding="utf-8")
            text = wrap_top_level_reveals(raw)
            print(f"  reveal groups: {path.name}")
        (output / path.name).write_text(text, encoding="utf-8")
        if path.name not in skip_rewrap:
            (final / path.name).write_text(text, encoding="utf-8")


def write_teaching_animations(project_dir: Path) -> None:
    import json

    cfg = {
        "version": 1,
        "defaults": {
            "transition": {"effect": "fade", "duration": 0.5},
            "animation": {"effect": "fade", "duration": 0.45, "trigger": "on-click"},
        },
        "slides": {},
    }
    (project_dir / "animations.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"  wrote {project_dir / 'animations.json'}")
