"""Layout Solver Lite — conservative WPS-safe layout decisions for V2 renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from scripts.ppt_layout_fit import (
    LAYOUT_REGISTRY,
    MIN_BODY_PT,
    SLIDE_CONTENT_BOTTOM,
    _cjk_ratio,
    chars_per_line,
    is_arrow_separator,
    line_count,
)
from scripts.wps_layout_verify import compute_safe_height, estimate_wps_text_height

# WPS renders taller than python-pptx heuristics
WPS_LINE_FACTOR = 1.35
CJK_MULT = 1.05
BOLD_MULT = 1.10
BULLET_MULT = 1.08
WPS_HEIGHT_FUDGE = 1.12
CONTAINER_PAD_RATIO = 0.12
CARD_INNER_PAD_V = 0.16
CARD_INNER_PAD_H = 0.22


@dataclass
class TextBlockPlan:
    text: str
    font_pt: int
    line_spacing: float
    inner_height: float
    container_height: float
    width: float
    bold: bool = False


@dataclass
class FixCardPlan:
    text: str
    font_pt: int
    line_spacing: float
    container_height: float
    mode: str  # dual | stack | single


@dataclass
class EssayPlan:
    paragraphs: list[str]
    font_pt: int
    line_spacing: float
    para_space_pt: int
    indent_spaces: int
    panel_top: float
    panel_height: float
    text_height: float
    annotation: str = ""
    ann_font_pt: int = 26
    ann_line_spacing: float = 1.0
    ann_height: float = 0.0
    ann_top: float = 0.0


@dataclass
class TitlePlan:
    show_stem_panel: bool
    task_pill_text: str
    stem_lines: list[str] = field(default_factory=list)
    poster_lines: list[str] = field(default_factory=list)
    stem_panel_height: float = 0.0
    poster_panel_height: float = 0.0
    stem_font_pt: int = 28
    poster_font_pt: int = 26


@dataclass
class SolvedLayout:
    kind: str
    title: TitlePlan | None = None
    content_cards: list[TextBlockPlan] = field(default_factory=list)
    essay: EssayPlan | None = None
    essay_split_parts: list[EssayPlan] = field(default_factory=list)
    fix_cards: list[FixCardPlan] = field(default_factory=list)
    fix_mode: str = "dual"
    table_row_heights: list[float] = field(default_factory=list)


def estimate_real_text_height(
    text: str,
    font_size: float,
    width_inches: float,
    *,
    bold: bool = False,
    bullet: bool = False,
    line_spacing: float = 1.15,
) -> float:
    """Conservative text block height (inches) — biased high for WPS."""
    clean = (text or "").strip()
    if not clean:
        return 0.35

    fs = max(float(font_size), float(MIN_BODY_PT))
    w = max(2.5, width_inches - CARD_INNER_PAD_H)
    mult = WPS_LINE_FACTOR * line_spacing
    if _cjk_ratio(clean) > 0.25:
        mult *= CJK_MULT
    if bold:
        mult *= BOLD_MULT
    if bullet or clean.startswith(("•", "①", "②", "③", "④")):
        mult *= BULLET_MULT

    line_h = (fs / 72.0) * mult
    lines = max(1.0, line_count(clean, w, fs))
    block = lines * line_h * WPS_HEIGHT_FUDGE
    return block + 0.10


def final_container_height(
    inner_text_height: float,
    *,
    min_h: float = 0.56,
    extra_pad: float = CARD_INNER_PAD_V * 2,
) -> float:
    """Shape height = text need + padding (shape ≡ textbox envelope)."""
    padded = inner_text_height * (1.0 + CONTAINER_PAD_RATIO)
    return max(min_h, padded + extra_pad)


def _pick_font_pt(text: str, width: float, max_h: float, *, max_pt: int = 28) -> tuple[int, float]:
    from scripts.ppt_layout_fit import fit_typography

    fit = fit_typography(text, width, max_h, min_pt=MIN_BODY_PT, max_pt=max_pt)
    return fit.font_pt, fit.line_spacing


def plan_text_block(
    text: str,
    width: float,
    *,
    bold: bool = False,
    bullet: bool = False,
    max_pt: int = 28,
    min_container: float = 0.56,
) -> TextBlockPlan:
    inner_w = max(2.5, width - CARD_INNER_PAD_H)
    font_pt, line_spacing = _pick_font_pt(text, inner_w, 999.0, max_pt=max_pt)
    inner_h = estimate_wps_text_height(
        text,
        font_pt,
        {
            "chinese": _cjk_ratio(text) > 0.25,
            "bold": bold,
            "bullet": bullet or text.strip().startswith(("•", "①", "★", "→")),
            "table_cell": False,
        },
        width_inches=width,
    )
    container_h = compute_safe_height(
        text,
        font_pt,
        width,
        bold=bold,
        bullet=bullet,
        min_h=min_container,
    )
    return TextBlockPlan(
        text=text,
        font_pt=font_pt,
        line_spacing=line_spacing,
        inner_height=max(inner_h, container_h - CARD_INNER_PAD_V * 2),
        container_height=container_h,
        width=width,
        bold=bold,
    )


def solve_title_layout(spec: dict) -> TitlePlan:
    body = [ln for ln in (spec.get("body") or []) if str(ln).strip()]
    posters = [ln for ln in (spec.get("poster_lines") or []) if str(ln).strip()]
    task_tag = (spec.get("task_tag") or spec.get("subtitle") or "").strip()
    pill = f"本课任务：{task_tag.replace(' · ', chr(10))}" if task_tag else ""

    plan = TitlePlan(
        show_stem_panel=bool(body),
        task_pill_text=pill,
        stem_lines=body,
        poster_lines=posters,
    )
    text_w = 11.2
    if body:
        block = plan_text_block("\n".join(body), text_w, max_pt=28)
        plan.stem_font_pt = block.font_pt
        plan.stem_panel_height = block.container_height + 0.36
    if posters:
        block = plan_text_block("\n".join(posters), text_w - 0.4, max_pt=26)
        plan.poster_font_pt = block.font_pt
        plan.poster_panel_height = block.container_height + 0.36
    return plan


def solve_content_layout(
    bullets: list[str],
    width: float,
) -> list[TextBlockPlan]:
    plans: list[TextBlockPlan] = []
    for bullet in bullets:
        if is_arrow_separator(bullet):
            plans.append(
                TextBlockPlan(
                    text=bullet.strip(),
                    font_pt=28,
                    line_spacing=1.0,
                    inner_height=0.12,
                    container_height=0.12,
                    width=width,
                )
            )
            continue
        display = bullet
        bold = bullet.startswith("★") or any(bullet.startswith(t) for t in ("基础", "进阶", "高级", "亮点", "必备"))
        if not display.startswith(("•", "→", "★")) and not bold:
            display = f"• {bullet}"
        plans.append(
            plan_text_block(display, width, bold=bold, bullet=True, max_pt=28)
        )
    return plans


def solve_essay_layout(
    paragraphs: list[str],
    *,
    header_bottom: float = 1.70,
    bottom_y: float = SLIDE_CONTENT_BOTTOM,
    content_width: float = 12.0,
    annotation: str = "",
    font_pt: int = 28,
    line_spacing: float = 1.12,
    para_space_pt: int = 6,
    indent_spaces: int = 0,
) -> EssayPlan | list[EssayPlan]:
    """Single essay plan or split list at paragraph boundaries when over capacity."""
    avail = bottom_y - header_bottom - 0.14
    text_w = content_width - 0.4
    ann = (annotation or "").strip()
    ann_h = 0.0
    if ann:
        ann_h = estimate_real_text_height(ann, 26, text_w) + 0.20

    def _body_height(paras: list[str]) -> float:
        total = 0.0
        for i, p in enumerate(paras):
            total += estimate_real_text_height(p, font_pt, text_w, line_spacing=line_spacing)
            if i < len(paras) - 1:
                total += para_space_pt / 72.0
        return total

    def _essay_panel_height(paras: list[str]) -> tuple[float, float]:
        text_h = _body_height(paras) + 0.18
        panel_h = text_h + CARD_INNER_PAD_V * 2 + 0.12
        return panel_h, text_h

    body_h = _body_height(paragraphs)
    need = body_h + 0.24
    if ann:
        need += ann_h + 0.08

    if need <= avail and paragraphs:
        panel_top = header_bottom + 0.08
        panel_h, text_h = _essay_panel_height(paragraphs)
        ann_top = panel_top + panel_h + 0.08
        return EssayPlan(
            paragraphs=paragraphs,
            font_pt=font_pt,
            line_spacing=line_spacing,
            para_space_pt=para_space_pt,
            indent_spaces=indent_spaces,
            panel_top=panel_top,
            panel_height=panel_h,
            text_height=text_h,
            annotation=ann,
            ann_font_pt=26,
            ann_line_spacing=1.0,
            ann_height=ann_h if ann else 0.0,
            ann_top=ann_top if ann else 0.0,
        )

    if len(paragraphs) <= 1:
        panel_top = header_bottom + 0.08
        panel_h, text_h = _essay_panel_height(paragraphs)
        ann_top = panel_top + panel_h + 0.08
        return EssayPlan(
            paragraphs=paragraphs,
            font_pt=font_pt,
            line_spacing=line_spacing,
            para_space_pt=para_space_pt,
            indent_spaces=indent_spaces,
            panel_top=panel_top,
            panel_height=panel_h,
            text_height=text_h,
            annotation=ann,
            ann_font_pt=26,
            ann_line_spacing=1.0,
            ann_height=ann_h if ann else 0.0,
            ann_top=ann_top if ann else 0.0,
        )

    parts: list[list[str]] = []
    current: list[str] = []
    for para in paragraphs:
        trial = current + [para]
        if current and _body_height(trial) + 0.24 > avail:
            parts.append(current)
            current = [para]
        else:
            current = trial
    if current:
        parts.append(current)

    out: list[EssayPlan] = []
    for idx, chunk in enumerate(parts):
        chunk_ann = ann if idx == len(parts) - 1 else ""
        plan = solve_essay_layout(
            chunk,
            header_bottom=header_bottom,
            bottom_y=bottom_y,
            content_width=content_width,
            annotation=chunk_ann,
            font_pt=font_pt,
            line_spacing=line_spacing,
            para_space_pt=para_space_pt,
            indent_spaces=indent_spaces,
        )
        if isinstance(plan, list):
            out.extend(plan)
        else:
            out.append(plan)
    return out if len(out) > 1 else (out[0] if out else EssayPlan([], font_pt, line_spacing, para_space_pt, indent_spaces, header_bottom + 0.08, 1.2, 1.0))


def solve_fix_cards_layout(
    left_text: str,
    right_text: str,
    *,
    avail_height: float,
    card_width: float = 5.85,
    full_width: float = 12.0,
) -> tuple[str, list[FixCardPlan]]:
    """Conservative fix-card layout; dual when both fit, else stack."""
    plans: list[FixCardPlan] = []
    inner_w = max(3.0, card_width - 0.30)
    left = (left_text or "").strip()
    right = (right_text or "").strip()

    if left:
        lp = plan_text_block(left, inner_w, bold=False, max_pt=28, min_container=0.72)
        plans.append(
            FixCardPlan(left, lp.font_pt, lp.line_spacing, lp.container_height, "single")
        )
    if right:
        rp = plan_text_block(right, inner_w, bold=True, max_pt=28, min_container=0.72)
        plans.append(
            FixCardPlan(right, rp.font_pt, rp.line_spacing, rp.container_height, "single")
        )

    if not plans:
        return "dual", []

    inner_w_dual = max(3.0, card_width - 0.30)
    for p in plans:
        safe_h = compute_safe_height(
            p.text,
            p.font_pt,
            inner_w_dual,
            bold=("改成" in p.text),
            min_h=0.72,
        )
        p.container_height = max(p.container_height, safe_h)

    if len(plans) == 1:
        inner_w = max(3.0, card_width - 0.30)
        p = plans[0]
        safe_h = compute_safe_height(
            p.text,
            p.font_pt,
            inner_w,
            bold=("改成" in p.text),
            min_h=0.72,
        )
        p.container_height = max(p.container_height, safe_h)
        return "single", plans

    max_h = max(p.container_height for p in plans)
    dual_need = max_h + 0.12
    if dual_need <= avail_height:
        for p in plans:
            p.container_height = max_h
            p.mode = "dual"
        return "dual", plans

    stack_h = (avail_height - 0.08) / 2
    for p in plans:
        inner_w_full = max(4.0, full_width - 0.30)
        repl = plan_text_block(
            p.text,
            inner_w_full,
            bold=("改成" in p.text),
            max_pt=28,
            min_container=min(stack_h, 0.72),
        )
        safe_h = compute_safe_height(
            p.text,
            repl.font_pt,
            inner_w_full,
            bold=("改成" in p.text),
            min_h=0.72,
        )
        p.font_pt = repl.font_pt
        p.line_spacing = repl.line_spacing
        p.container_height = max(safe_h, min(repl.container_height, stack_h))
        p.mode = "stack"
    return "stack", plans


def solve_table_row_heights(
    row_values: list[list[str]],
    col_fracs: list[float],
    *,
    content_width: float = 12.0,
    header: bool = False,
) -> list[float]:
    """Per-row heights from real text measurement."""
    heights: list[float] = []
    if header:
        heights.append(0.68)
    for vals in row_values:
        max_inner = 0.42
        for val, frac in zip(vals, col_fracs, strict=False):
            col_w = content_width * frac
            inner_w = max(1.0, col_w - 0.14)
            h = compute_safe_height(
                str(val or ""),
                28,
                inner_w,
                table_cell=True,
                min_h=0.42,
            )
            max_inner = max(max_inner, h - 0.20)
        heights.append(max(0.52, max_inner + 0.20))
    return heights


def solve_layout(spec: dict) -> SolvedLayout:
    """Single layout decision entry for one slide spec."""
    kind = spec.get("type", "")
    solved = SolvedLayout(kind=kind)

    if kind == "title":
        solved.title = solve_title_layout(spec)
        return solved

    if kind == "content":
        bullets = [str(b) for b in (spec.get("bullets") or []) if str(b).strip()]
        width = 11.7
        solved.content_cards = solve_content_layout(bullets, width)
        return solved

    if kind == "essay":
        from scripts.essay_format import essay_layout_for_length, prepare_classroom_essay_display

        essay_text = spec.get("essay_text") or ""
        ann = (spec.get("annotation") or "").strip()
        if "Dear " in essay_text or "中文批注" in essay_text:
            paragraphs, ann_text = prepare_classroom_essay_display(
                essay_text, annotation_fallback=ann
            )
        else:
            paragraphs = [p.strip() for p in essay_text.split("\n\n") if p.strip()]
            ann_text = ann
        line_spacing, para_space_pt, indent_spaces = essay_layout_for_length(
            [
                re.sub(r"\s*Word count:\s*\d+\s*$", "", p, flags=re.IGNORECASE).strip()
                for p in paragraphs
            ]
        )
        result = solve_essay_layout(
            paragraphs,
            annotation=ann_text,
            line_spacing=line_spacing,
            para_space_pt=para_space_pt,
            indent_spaces=indent_spaces,
        )
        if isinstance(result, list):
            solved.essay_split_parts = result
        else:
            solved.essay = result
        return solved

    if kind == "phrase_table":
        part = spec.get("part") or "full"
        table = spec.get("table") or {}
        if part.startswith("footer") or (
            part == "full" and (table.get("topic_note") or table.get("fix_bad"))
        ):
            left = ("别这样写\n" + table.get("fix_bad", "")).strip() if table.get("fix_bad") else ""
            right = (
                ("改成\n" + table.get("fix_good", "").lstrip("→").strip()).strip()
                if table.get("fix_good")
                else ""
            )
            budget = LAYOUT_REGISTRY["phrase_table_footer"]
            note_h = 0.0
            if table.get("topic_note") and part in ("footer", "footer_note", "full"):
                note_h = estimate_real_text_height(table["topic_note"], 26, 10.0) + 1.05
            avail = SLIDE_CONTENT_BOTTOM - 1.74 - note_h - 0.20
            mode, cards = solve_fix_cards_layout(left, right, avail_height=max(1.0, avail))
            solved.fix_mode = mode
            solved.fix_cards = cards
        else:
            tiers = table.get("tiers") or []
            col_fracs = [0.14, 0.52, 0.34]
            rows = [["层级", "背这句", "怎么用"]]
            for tier in tiers:
                note = tier.get("chinese") or ""
                hs = tier.get("high_score")
                if hs:
                    note = f"{note}\n{hs}" if note else hs
                rows.append([tier.get("level", ""), tier.get("english", ""), note])
            solved.table_row_heights = solve_table_row_heights(
                rows[1:], col_fracs, header=True
            )
            solved.table_row_heights = [0.68] + solved.table_row_heights
        return solved

    if kind == "vocab_table":
        rows = spec.get("rows") or []
        columns = spec.get("columns") or []
        n = len(columns)
        col_fracs = [0.38, 0.62] if n == 2 else [0.26, 0.20, 0.54]
        row_vals = [[row.get(c, "") for c in columns] for row in rows]
        solved.table_row_heights = solve_table_row_heights(
            row_vals, col_fracs, header=True
        )
        solved.table_row_heights = [0.68] + solved.table_row_heights
        return solved

    return solved
