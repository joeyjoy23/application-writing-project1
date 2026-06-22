"""Layout budgets + elastic font (26–32pt) for classroom PPT renderers.

LLM deck plans reference layout IDs defined in LAYOUT_REGISTRY; each layout
reserves inches for chrome (tags, pills, banners) so text fit is predictable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

# Match generate_classroom_pptx slide canvas
SLIDE_CONTENT_BOTTOM = 7.32

MIN_BODY_PT = 26
MAX_PRIMARY_PT = 32
MAX_SECONDARY_PT = 28
MIN_LINE_SPACING = 0.9
FONT_STEPS = (32, 30, 28, 26)
LINE_SPACING_STEPS = (1.12, 1.05, 1.0, 0.95, 0.9)
# WPS wraps tighter than heuristic; leave margin for cell/text-frame padding.
FIT_WIDTH_FACTOR = 0.85
FIT_HEIGHT_FACTOR = 0.94
FIT_FILL_RATIO = 0.98
WPS_SAFETY_FACTOR = 0.85
# WPS text frames render taller than heuristic block_height — pad panel chrome.
WPS_PANEL_FUDGE = 1.12
TITLE_PANEL_TOP = 2.12
MAX_CONTENT_BULLETS = 3
ARROW_SEP_HEIGHT = 0.12
_ARROW_SEP_RE = re.compile(r"^[↓→↔⬇]$")


def is_arrow_separator(text: str) -> bool:
    """True for chain arrows (↓) that sit between substantive bullet cards."""
    t = (text or "").strip()
    if not t:
        return False
    if _ARROW_SEP_RE.match(t):
        return True
    return len(t) <= 2 and all(c in "↓→↔" for c in t)


def substantive_bullet_count(bullets: list[str]) -> int:
    return sum(1 for b in bullets if b.strip() and not is_arrow_separator(b))


def _chunk_bullets_preserving_arrows(bullets: list[str], max_substantive: int) -> list[list[str]]:
    """Split bullet lists on substantive count; keep ↓ attached to adjacent steps."""
    if max_substantive < 1:
        max_substantive = 1
    chunks: list[list[str]] = []
    current: list[str] = []
    substantive = 0
    for bullet in bullets:
        if is_arrow_separator(bullet):
            current.append(bullet)
            continue
        if substantive >= max_substantive and current:
            chunks.append(current)
            current = []
            substantive = 0
        current.append(bullet)
        substantive += 1
    if current:
        if chunks and current and is_arrow_separator(current[0]):
            chunks[-1].extend(current)
        else:
            chunks.append(current)
    return chunks or [[]]


ColKind = Literal["primary", "secondary", "label"]


@dataclass(frozen=True)
class LayoutBudget:
    """Reserved vertical space (inches) below title bar — not for body text."""

    layout_id: str
    header: float = 1.12
    section_tag: float = 0.0  # included in header offset in V2
    pill_row: float = 0.58
    key_banner: float = 0.0
    fix_row: float = 0.0
    bottom_margin: float = 0.15
    max_primary_pt: int = MAX_PRIMARY_PT
    max_secondary_pt: int = MAX_SECONDARY_PT
    min_pt: int = MIN_BODY_PT

    def chrome_height(self, *, with_pill: bool = True, with_banner: bool = False) -> float:
        h = self.header + self.bottom_margin
        if with_pill and self.pill_row:
            h += self.pill_row
        if with_banner and self.key_banner:
            h += self.key_banner
        if self.fix_row:
            h += self.fix_row
        return h

    def content_height(
        self,
        *,
        with_pill: bool = True,
        with_banner: bool = False,
        extra_reserve: float = 0.0,
    ) -> float:
        """Usable height for main text block on a 16:9 slide."""
        return max(
            1.0,
            SLIDE_CONTENT_BOTTOM - self.chrome_height(with_pill=with_pill, with_banner=with_banner)
            - extra_reserve,
        )


LAYOUT_REGISTRY: dict[str, LayoutBudget] = {
    "phrase_table_body": LayoutBudget(
        layout_id="phrase_table_body",
        pill_row=0.58,
        key_banner=0.0,
        fix_row=0.0,
        max_primary_pt=32,
        max_secondary_pt=28,
    ),
    "phrase_table_footer": LayoutBudget(
        layout_id="phrase_table_footer",
        pill_row=0.0,
        key_banner=1.05,
        fix_row=1.12,
        max_primary_pt=28,
        max_secondary_pt=26,
    ),
    "vocab_table": LayoutBudget(
        layout_id="vocab_table",
        pill_row=0.58,
        max_primary_pt=30,
        max_secondary_pt=26,
    ),
    "content_key": LayoutBudget(
        layout_id="content_key",
        pill_row=0.62,
        key_banner=1.05,
        max_primary_pt=28,
    ),
    "content_cards": LayoutBudget(
        layout_id="content_cards",
        pill_row=0.62,
        max_primary_pt=28,
    ),
    "peel_dual": LayoutBudget(
        layout_id="peel_dual",
        pill_row=0.0,
        max_primary_pt=28,
    ),
    "title_body": LayoutBudget(
        layout_id="title_body",
        header=2.55,
        pill_row=0.78,
        bottom_margin=0.08,
        max_primary_pt=28,
        max_secondary_pt=26,
    ),
    "essay_body": LayoutBudget(
        layout_id="essay_body",
        pill_row=0.62,
        bottom_margin=0.15,
        max_primary_pt=28,
        max_secondary_pt=26,
    ),
}


@dataclass(frozen=True)
class FitResult:
    font_pt: int
    line_spacing: float
    block_height: float
    needs_split: bool = False


@dataclass(frozen=True)
class FixCardsLayout:
    """Dual side-by-side, vertical stack, or must split to another slide."""

    mode: Literal["dual", "stack", "needs_split"]
    card_height: float
    left: FitResult
    right: FitResult | None = None


def effective_text_area(
    width_inches: float,
    height_inches: float,
    *,
    pad_h_pt: float = 6,
    pad_v_pt: float = 4,
) -> tuple[float, float]:
    """Usable text area after margins and WPS safety factor."""
    w = max(1.0, width_inches - 2 * pad_h_pt / 72.0) * FIT_WIDTH_FACTOR
    h = max(0.25, height_inches - 2 * pad_v_pt / 72.0) * FIT_HEIGHT_FACTOR
    return w, h


def _cjk_ratio(text: str) -> float:
    if not text:
        return 1.0
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff" or ch in "，。；：！？、「」")
    return cjk / len(text)


def chars_per_line(text: str, width_inches: float, font_pt: float) -> float:
    ratio = _cjk_ratio(text)
    base = 28 * ratio + 52 * (1 - ratio)
    scale = (width_inches * 72) / (font_pt * 1.05)
    return max(8.0, base * scale / 6.5)


def line_count(text: str, width_inches: float, font_pt: float) -> float:
    if not text.strip():
        return 0.35
    cpl = chars_per_line(text, width_inches, font_pt)
    total = 0.0
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            total += 0.35
            continue
        total += max(1.0, len(para) / cpl)
    return total


def line_height_inches(font_pt: float, line_spacing: float = 1.12) -> float:
    return (font_pt / 72.0) * line_spacing


def text_block_height(
    text: str,
    width_inches: float,
    font_pt: float,
    line_spacing: float = 1.12,
) -> float:
    return line_count(text, width_inches, font_pt) * line_height_inches(font_pt, line_spacing)


def text_block_height_paragraphs(
    paragraphs: list[str],
    width_inches: float,
    font_pt: float,
    line_spacing: float,
    *,
    space_after_pt: float = 0,
) -> float:
    """Height for multiple paragraphs including space_after gaps."""
    lines = [p for p in paragraphs if p.strip()]
    if not lines:
        return 0.35
    total = 0.0
    for i, para in enumerate(lines):
        total += text_block_height(para, width_inches, font_pt, line_spacing)
        if space_after_pt and i < len(lines) - 1:
            total += space_after_pt / 72.0
    return total


def fit_typography(
    text: str,
    width_inches: float,
    max_height_inches: float,
    *,
    min_pt: int = MIN_BODY_PT,
    max_pt: int = MAX_PRIMARY_PT,
    min_spacing: float = MIN_LINE_SPACING,
    pad_h_pt: float = 6,
    pad_v_pt: float = 4,
) -> FitResult:
    """Largest font + tightest spacing that fits; else min settings + needs_split."""
    eff_w, eff_h = effective_text_area(
        width_inches, max_height_inches, pad_h_pt=pad_h_pt, pad_v_pt=pad_v_pt
    )
    cap = eff_h * FIT_FILL_RATIO
    for pt in FONT_STEPS:
        if pt > max_pt:
            continue
        if pt < min_pt:
            break
        for spacing in LINE_SPACING_STEPS:
            if spacing < min_spacing - 1e-6:
                break
            h = text_block_height(text, eff_w, pt, spacing)
            if h <= cap:
                return FitResult(pt, spacing, h, needs_split=False)
    h = text_block_height(text, eff_w, min_pt, min_spacing)
    return FitResult(min_pt, min_spacing, h, needs_split=True)


def fit_paragraphs(
    paragraphs: list[str],
    width_inches: float,
    max_height_inches: float,
    *,
    space_after_pt: float = 0,
    min_pt: int = MIN_BODY_PT,
    max_pt: int = MAX_PRIMARY_PT,
    min_spacing: float = MIN_LINE_SPACING,
    pad_h_pt: float = 6,
    pad_v_pt: float = 4,
) -> FitResult:
    """Fit multi-paragraph blocks (title body, PEEL lines) with inter-paragraph gaps."""
    eff_w, eff_h = effective_text_area(
        width_inches, max_height_inches, pad_h_pt=pad_h_pt, pad_v_pt=pad_v_pt
    )
    cap = eff_h * FIT_FILL_RATIO
    lines = [p for p in paragraphs if p.strip()]
    if not lines:
        return FitResult(min_pt, 1.12, 0.35, needs_split=False)
    for pt in FONT_STEPS:
        if pt > max_pt:
            continue
        if pt < min_pt:
            break
        for spacing in LINE_SPACING_STEPS:
            if spacing < min_spacing - 1e-6:
                break
            h = text_block_height_paragraphs(lines, eff_w, pt, spacing, space_after_pt=space_after_pt)
            if h <= cap:
                return FitResult(pt, spacing, h, needs_split=False)
    h = text_block_height_paragraphs(
        lines, eff_w, min_pt, min_spacing, space_after_pt=space_after_pt
    )
    return FitResult(min_pt, min_spacing, h, needs_split=True)


def pick_font_pt(
    text: str,
    width_inches: float,
    max_height_inches: float,
    *,
    min_pt: int = MIN_BODY_PT,
    max_pt: int = MAX_PRIMARY_PT,
    line_spacing: float = 1.12,
) -> int:
    """Largest font in FONT_STEPS that fits max_height, else min_pt."""
    for pt in FONT_STEPS:
        if pt > max_pt:
            continue
        if pt < min_pt:
            break
        if text_block_height(text, width_inches, pt, line_spacing) <= max_height_inches * 1.02:
            return pt
    return min_pt


def pick_font_for_kind(
    text: str,
    width_inches: float,
    max_row_height: float,
    kind: ColKind,
    budget: LayoutBudget,
    *,
    line_spacing: float = 1.12,
) -> int:
    max_pt = budget.max_primary_pt if kind == "primary" else budget.max_secondary_pt
    if kind == "label":
        max_pt = 26
    return pick_font_pt(
        text,
        width_inches,
        max_row_height,
        min_pt=budget.min_pt,
        max_pt=max_pt,
        line_spacing=line_spacing,
    )


def fit_banner(
    text: str,
    budget: LayoutBudget,
    *,
    content_width: float = 12.0,
    label_width: float = 1.7,
) -> FitResult:
    """Fit key-insight / 本题 banner text."""
    max_h = budget.key_banner if budget.key_banner else 1.05
    text_w = max(4.0, content_width - label_width)
    return fit_typography(
        text.replace("💡", "").strip(),
        text_w,
        max_h,
        max_pt=budget.max_secondary_pt,
        min_pt=budget.min_pt,
    )


def split_banner_text(text: str, budget: LayoutBudget | None = None) -> list[str]:
    """Split long banner text into two lines when single-line fit would overflow."""
    budget = budget or LAYOUT_REGISTRY["phrase_table_footer"]
    clean = text.replace("💡", "").strip()
    if not clean or not fit_banner(clean, budget).needs_split:
        return [clean] if clean else []
    mid = len(clean) // 2
    best = mid
    for sep in ("；", "，", ",", "。", "、", " "):
        pos = clean.rfind(sep, max(0, mid - 24), min(len(clean), mid + 24))
        if pos > 12:
            best = pos + len(sep)
            break
    line1, line2 = clean[:best].strip(), clean[best:].strip()
    if line1 and line2:
        return [line1, line2]
    return [clean]


def fit_table_rows(
    values: list[str],
    col_fracs: list[float],
    col_kinds: list[ColKind],
    budget: LayoutBudget,
    *,
    content_width: float = 12.0,
    max_row_cap: float = 1.55,
    per_row_budget: float | None = None,
) -> tuple[float, list[int], list[float], bool]:
    """Return (row height, font pt per column, line_spacing per column, needs_split)."""
    col_widths = [content_width * f for f in col_fracs]
    row_budget = per_row_budget
    if row_budget is None:
        row_budget = min(budget.content_height(with_pill=False) / 4.0, max_row_cap)

    font_pts: list[int] = []
    spacings: list[float] = []
    needs_split = False
    for val, w, kind in zip(values, col_widths, col_kinds, strict=True):
        max_pt = budget.max_primary_pt if kind == "primary" else budget.max_secondary_pt
        if kind == "label":
            max_pt = 26
        fit = fit_typography(
            val,
            w,
            row_budget - 0.12,
            min_pt=budget.min_pt,
            max_pt=max_pt,
        )
        font_pts.append(fit.font_pt)
        spacings.append(fit.line_spacing)
        if fit.needs_split:
            needs_split = True

    heights = [
        text_block_height(val, w, pt, sp) + 0.20
        for val, w, pt, sp in zip(values, col_widths, font_pts, spacings, strict=True)
    ]
    row_h = max(max(heights), 0.48)
    if row_h > max_row_cap:
        needs_split = True
    return row_h, font_pts, spacings, needs_split


PEEL_CARD_WIDTH = 5.85
PEEL_CARD_BODY_INSET = 0.62  # header + gap below card top before body textbox
PEEL_CARD_CHROME = 0.82  # card height above measured body block
PEEL_DUAL_CARD_TOP = 1.70  # V2 header (1.62) + 0.08 gap
MAX_PEEL_E_ITEMS = 2
PEEL_LINE_MAX_LEN = 96
PEEL_E_LINE_MAX_LEN = 72
PEEL_POINT_CHAR_BUDGET = 130
_PEEL_E_META_PREFIX = (
    "具体化",
    "感受",
    "元素含义",
    "说明元素",
    "影响",
    "将",
    "说明",
)


def _trim_peel(text: str, max_len: int = PEEL_LINE_MAX_LEN) -> str:
    s = re.sub(r"\s+", " ", (text or "").strip())
    return s[: max_len - 1] + "…" if len(s) > max_len else s


def _quoted_peel_fragment(raw: str) -> str:
    for pat in (
        r"如[「\"']([^」\"']{6,})[」\"']",
        r"如\s*[「\"']([^」\"']{6,})",
        r"「([^」]{6,})」",
    ):
        m = re.search(pat, raw)
        if m:
            return m.group(1).strip()
    best = ""
    for m in re.finditer(r'"([^"]+)"', raw):
        cand = m.group(1).strip()
        if len(cand) < 6:
            continue
        latin = sum(ch.isascii() and ch.isalpha() for ch in cand)
        if latin >= 4 and len(cand) > len(best):
            best = cand
    if best:
        return best
    m = re.search(r"'([^']{6,})'", raw)
    return m.group(1).strip() if m else ""


def _project_peel_e_item(raw: str) -> str:
    """Strip Chinese meta-labels; prefer short English quote for projection."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    if not s:
        return ""
    quoted = _quoted_peel_fragment(s)
    if quoted:
        return _trim_peel(quoted, PEEL_E_LINE_MAX_LEN)
    if "：" in s:
        head, tail = s.split("：", 1)
        if any(head.startswith(p) or p in head for p in _PEEL_E_META_PREFIX):
            s = tail.strip()
    elif ":" in s and re.match(r"^[\w/]+:", s):
        s = s.split(":", 1)[1].strip()
    s = re.sub(r"（[^）]*）", "", s)
    s = re.sub(r"\([^)]*\)", "", s)
    quoted = _quoted_peel_fragment(s)
    if quoted:
        return _trim_peel(quoted, PEEL_E_LINE_MAX_LEN)
    return _trim_peel(s, PEEL_E_LINE_MAX_LEN)


def peel_point_char_total(point: dict) -> int:
    norm = normalize_peel_point(point)
    return len(norm["p"]) + sum(len(e) for e in norm["e_items"]) + len(norm["l"])


def normalize_peel_point(point: dict, *, max_e: int = MAX_PEEL_E_ITEMS) -> dict:
    """Cap E items and trim verbose PEEL fields for slide layout."""
    p = _trim_peel(str(point.get("p") or ""))
    e_raw = point.get("e_items") or ([point["e"]] if point.get("e") else [])
    e_items = [_project_peel_e_item(str(e)) for e in e_raw if str(e).strip()][:max_e]
    l = _trim_peel(str(point.get("l") or ""))
    return {
        "label": (point.get("label") or "").strip() or "Point",
        "p": p,
        "e_items": e_items,
        "l": l,
    }


def peel_point_body_lines(point: dict) -> list[str]:
    """Measurement lines matching V2 renderer tag+body runs (``P  `` prefix)."""
    norm = normalize_peel_point(point)
    lines: list[str] = []
    if norm["p"]:
        lines.append(f"P  {norm['p']}")
    for ei, e_text in enumerate(norm["e_items"]):
        tag = "E" if ei == 0 else "  "
        lines.append(f"{tag}  {e_text}")
    if norm["l"]:
        lines.append(f"L  {norm['l']}")
    return lines


def _peel_paragraph_block_height(
    lines: list[str],
    width_inches: float,
    font_pt: int,
    line_spacing: float,
    *,
    space_after_pt: float = 0,
) -> float:
    """PEEL lines use 26pt tag runs; measure height at max(tag, body) per line."""
    if not lines:
        return 0.35
    total = 0.0
    tag_pt = 26
    for i, line in enumerate(lines):
        pt = max(tag_pt, font_pt)
        total += text_block_height(line, width_inches, pt, line_spacing)
        if space_after_pt and i < len(lines) - 1:
            total += space_after_pt / 72.0
    return total


def fit_peel_point(
    point: dict,
    card_width: float,
    body_max_height: float,
    budget: LayoutBudget | None = None,
) -> FitResult:
    """Fit one PEEL card body using tag+body paragraph lines."""
    budget = budget or LAYOUT_REGISTRY["peel_dual"]
    inner_w = max(3.0, card_width - 0.3)
    lines = peel_point_body_lines(point)
    eff_w, eff_h = effective_text_area(
        inner_w, body_max_height, pad_h_pt=4, pad_v_pt=4
    )
    cap = eff_h * FIT_FILL_RATIO
    if not lines:
        return FitResult(budget.min_pt, 1.12, 0.35, needs_split=False)
    for pt in FONT_STEPS:
        if pt > budget.max_primary_pt:
            continue
        if pt < budget.min_pt:
            break
        for spacing in LINE_SPACING_STEPS:
            if spacing < MIN_LINE_SPACING - 1e-6:
                break
            h = _peel_paragraph_block_height(
                lines, eff_w, pt, spacing, space_after_pt=6
            )
            if h <= cap:
                return FitResult(pt, spacing, h, needs_split=False)
    h = _peel_paragraph_block_height(
        lines, eff_w, budget.min_pt, MIN_LINE_SPACING, space_after_pt=6
    )
    return FitResult(budget.min_pt, MIN_LINE_SPACING, h, needs_split=True)


def estimate_peel_dual_body_height() -> float:
    """Body textbox max height for side-by-side PEEL cards on V2 slides."""
    card_h = SLIDE_CONTENT_BOTTOM - PEEL_DUAL_CARD_TOP - 0.1
    return max(0.45, card_h - PEEL_CARD_BODY_INSET)


def estimate_peel_single_body_height() -> float:
    """Body textbox max height for a full-width single PEEL card."""
    return estimate_peel_dual_body_height()


def peel_dual_needs_split(points: list[dict]) -> bool:
    """True when dual-card PEEL must split (WPS-safe: prefer one point per slide)."""
    normed = [normalize_peel_point(p) for p in points[:2]]
    if len(normed) >= 2:
        return True
    if not normed:
        return False
    point = normed[0]
    if len(point["e_items"]) > 1:
        return True
    if peel_point_char_total(point) > PEEL_POINT_CHAR_BUDGET:
        return True
    body_h = estimate_peel_dual_body_height()
    return fit_peel_point(point, PEEL_CARD_WIDTH, body_h).needs_split


def expand_peel_slides(slides: list[dict]) -> list[dict]:
    """Split PEEL specs into one Point per slide when dual would overflow."""
    expanded: list[dict] = []
    for spec in slides:
        if spec.get("type") != "peel":
            expanded.append(spec)
            continue
        raw = spec.get("points") or []
        points = [normalize_peel_point(p) for p in raw[:2]]
        if not points:
            expanded.append(spec)
            continue
        if len(points) == 1:
            new_spec = dict(spec)
            new_spec["points"] = points
            new_spec["layout"] = "single"
            expanded.append(new_spec)
            continue
        if peel_dual_needs_split(points):
            for idx, point in enumerate(points):
                new_spec = dict(spec)
                new_spec["points"] = [point]
                new_spec["layout"] = "single"
                suffix = f" · Point {idx + 1}" if len(points) > 1 else ""
                new_spec["title"] = f"{spec['title']}{suffix}"
                expanded.append(new_spec)
        else:
            new_spec = dict(spec)
            new_spec["points"] = points
            new_spec["layout"] = "dual"
            expanded.append(new_spec)
    return expanded


def expand_content_slides(slides: list[dict]) -> list[dict]:
    """Split content slides when bullet cards overflow (WPS-safe: max 3 bullets/page)."""
    expanded: list[dict] = []
    budget = LAYOUT_REGISTRY["content_cards"]
    for spec in slides:
        if spec.get("type") != "content":
            expanded.append(spec)
            continue
        bullets = [b for b in (spec.get("bullets") or []) if b.strip()]
        if not bullets:
            expanded.append(spec)
            continue
        key_lines = [
            b for b in bullets if b.startswith("💡") or "高分关键" in b or "最危险" in b
        ]
        body_bullets = [b for b in bullets if b not in key_lines]
        has_banner = bool(key_lines)
        has_badge = bool(spec.get("badge"))
        reserve = 0.62 if has_badge else 0.0
        reserve += 1.05 if has_banner else 0.0
        content_h = budget.content_height(with_pill=has_badge) - reserve
        layout = fit_bullet_card_layout(
            body_bullets,
            budget,
            content_height=max(2.0, content_h),
        )
        needs_split = (
            layout.needs_split or substantive_bullet_count(body_bullets) > MAX_CONTENT_BULLETS
        )
        if not needs_split:
            expanded.append(spec)
            continue
        chunks = _chunk_bullets_preserving_arrows(body_bullets, MAX_CONTENT_BULLETS)
        if key_lines:
            chunks[0] = key_lines + chunks[0]
        for idx, chunk in enumerate(chunks):
            new_spec = dict(spec)
            new_spec["bullets"] = chunk
            if len(chunks) > 1:
                new_spec["title"] = f"{spec['title']}（{idx + 1}/{len(chunks)}）"
            if idx > 0:
                new_spec.pop("badge", None)
            expanded.append(new_spec)
    return expanded


def fit_dual_cards(
    left_text: str,
    right_text: str,
    card_width: float,
    card_height: float,
    budget: LayoutBudget | None = None,
) -> tuple[FitResult, FitResult]:
    """Fit two side-by-side PEEL / fix cards."""
    budget = budget or LAYOUT_REGISTRY["peel_dual"]
    inner_w = max(3.0, card_width - 0.3)
    inner_h = max(0.35, card_height - 0.24)
    left = fit_typography(
        left_text,
        inner_w,
        inner_h,
        max_pt=budget.max_primary_pt,
        min_pt=budget.min_pt,
        pad_h_pt=6,
        pad_v_pt=4,
    )
    right = fit_typography(
        right_text or " ",
        inner_w,
        inner_h,
        max_pt=budget.max_primary_pt,
        min_pt=budget.min_pt,
        pad_h_pt=6,
        pad_v_pt=4,
    )
    return left, right


def fit_fix_cards(
    left_text: str,
    right_text: str,
    *,
    avail_height: float,
    card_width: float = 5.85,
    full_width: float = 12.0,
    budget: LayoutBudget | None = None,
) -> FixCardsLayout:
    """Pick dual / stack / needs_split for 改错 cards using remaining slide height."""
    budget = budget or LAYOUT_REGISTRY["phrase_table_footer"]
    avail_height = max(0.5, avail_height)
    has_left = bool(left_text.strip())
    has_right = bool(right_text.strip())
    if has_left and not has_right:
        lf = fit_typography(
            left_text,
            full_width - 0.3,
            avail_height - 0.12,
            max_pt=budget.max_primary_pt,
            min_pt=budget.min_pt,
        )
        h = min(avail_height, lf.block_height + 0.24)
        mode = "needs_split" if lf.needs_split else "stack"
        return FixCardsLayout(mode, h, lf, None)
    if has_right and not has_left:
        rf = fit_typography(
            right_text,
            full_width - 0.3,
            avail_height - 0.12,
            max_pt=budget.max_primary_pt,
            min_pt=budget.min_pt,
        )
        h = min(avail_height, rf.block_height + 0.24)
        mode = "needs_split" if rf.needs_split else "stack"
        return FixCardsLayout(mode, h, rf, None)

    lf, rf = fit_dual_cards(left_text, right_text, card_width, avail_height, budget)
    if not lf.needs_split and not rf.needs_split:
        h = min(avail_height, max(lf.block_height, rf.block_height) + 0.24)
        return FixCardsLayout("dual", h, lf, rf)

    stack_w = max(4.0, full_width - 0.3)
    half_h = max(0.35, (avail_height - 0.12) / 2)
    lf_s = fit_typography(
        left_text, stack_w, half_h - 0.08, max_pt=budget.max_primary_pt, min_pt=budget.min_pt
    )
    rf_s = fit_typography(
        right_text, stack_w, half_h - 0.08, max_pt=budget.max_primary_pt, min_pt=budget.min_pt
    )
    if not lf_s.needs_split and not rf_s.needs_split:
        return FixCardsLayout("stack", avail_height, lf_s, rf_s)
    return FixCardsLayout("needs_split", avail_height, lf, rf)


def fit_bullet_cards(
    bullets: list[str],
    budget: LayoutBudget,
    *,
    content_width: float = 12.0,
    content_height: float | None = None,
) -> list[FitResult]:
    """Per-card typography for stacked bullet cards (legacy equal-height helper)."""
    layout = fit_bullet_card_layout(
        bullets,
        budget,
        content_width=content_width,
        content_height=content_height,
    )
    return layout.fits


@dataclass(frozen=True)
class BulletCardLayout:
    heights: list[float]
    fits: list[FitResult]
    needs_split: bool = False


def fit_bullet_card_layout(
    bullets: list[str],
    budget: LayoutBudget,
    *,
    content_width: float = 12.0,
    content_height: float | None = None,
    gap: float = 0.14,
    card_pad_v: float = 0.32,
    card_min_h: float = 0.56,
) -> BulletCardLayout:
    """Variable-height stacked cards: shrink-wrap short bullets, scale if over budget."""
    if not bullets:
        return BulletCardLayout([], [], needs_split=False)

    avail_h = content_height if content_height is not None else budget.content_height(with_pill=True)
    text_w = max(4.0, content_width - 0.34)
    n = len(bullets)

    natural: list[float] = []
    fits: list[FitResult] = []
    for bullet in bullets:
        if is_arrow_separator(bullet):
            natural.append(ARROW_SEP_HEIGHT)
            fits.append(FitResult(budget.max_primary_pt, 1.0, ARROW_SEP_HEIGHT, needs_split=False))
            continue
        fit = fit_typography(
            bullet,
            text_w,
            999.0,
            max_pt=budget.max_primary_pt,
            min_pt=budget.min_pt,
        )
        natural.append(max(card_min_h, fit.block_height + card_pad_v))
        fits.append(fit)

    total = sum(natural) + gap * max(n - 1, 0)
    if total <= avail_h * 1.01:
        return BulletCardLayout(natural, fits, needs_split=False)

    inner = max(0.5, avail_h - gap * max(n - 1, 0))
    scale = inner / sum(h for h, b in zip(natural, bullets) if not is_arrow_separator(b)) if any(
        not is_arrow_separator(b) for b in bullets
    ) else 1.0
    scaled = [
        ARROW_SEP_HEIGHT
        if is_arrow_separator(bullet)
        else max(card_min_h, h * scale)
        for h, bullet in zip(natural, bullets)
    ]
    refit: list[FitResult] = []
    needs_split = False
    final_heights: list[float] = []
    for bullet, card_h in zip(bullets, scaled):
        if is_arrow_separator(bullet):
            refit.append(FitResult(budget.max_primary_pt, 1.0, ARROW_SEP_HEIGHT, needs_split=False))
            final_heights.append(ARROW_SEP_HEIGHT)
            continue
        fit = fit_typography(
            bullet,
            text_w,
            max(0.35, card_h - card_pad_v + 0.06),
            max_pt=budget.max_primary_pt,
            min_pt=budget.min_pt,
        )
        refit.append(fit)
        needed = max(card_min_h, fit.block_height + card_pad_v)
        final_heights.append(max(card_h, needed))
        if fit.needs_split:
            needs_split = True
    return BulletCardLayout(final_heights, refit, needs_split=needs_split)


def phrase_table_body_heights(
    tiers: list[dict],
    col_fracs: list[float],
    budget: LayoutBudget | None = None,
) -> tuple[list[float], list[list[int]], list[list[float]], bool]:
    """Header + tier row heights/fonts/spacings; never scale row height without typography."""
    budget = budget or LAYOUT_REGISTRY["phrase_table_body"]
    avail = budget.content_height(with_pill=True)
    header_h = 0.56
    row_heights: list[float] = [header_h]
    all_fonts: list[list[int]] = [[26, 26, 26]]
    all_spacings: list[list[float]] = [[1.12, 1.12, 1.12]]
    needs_split = False

    kinds: list[ColKind] = ["label", "primary", "secondary"]
    per_row_budget = min(avail / max(len(tiers) + 1, 1), 1.55)
    for tier in tiers:
        level = tier.get("level", "")
        english = tier.get("english", "")
        if level == "基础句":
            note = ""
        else:
            note = tier.get("chinese", "") or ""
            hs = tier.get("high_score")
            if hs:
                note = f"{note}\n{hs}" if note else hs
        vals = [level, english, note]
        rh, fpts, sps, split = fit_table_rows(
            vals,
            col_fracs,
            kinds,
            budget,
            per_row_budget=per_row_budget,
        )
        row_heights.append(rh)
        all_fonts.append(fpts)
        all_spacings.append(sps)
        if split:
            needs_split = True

    total = sum(row_heights)
    if total > avail * 1.02:
        needs_split = True
    return row_heights, all_fonts, all_spacings, needs_split


def fit_vocab_chunk(
    rows: list[dict],
    columns: list[str],
    budget: LayoutBudget | None = None,
    *,
    content_width: float = 12.0,
) -> tuple[list[float], list[list[int]], list[list[float]], bool]:
    """Header + data row heights for a vocab chunk; signals needs_split if over budget."""
    budget = budget or LAYOUT_REGISTRY["vocab_table"]
    avail = budget.content_height(with_pill=True)
    n_cols = len(columns)
    col_fracs = [0.38, 0.62] if n_cols == 2 else [0.26, 0.20, 0.54]
    kinds: list[ColKind] = []
    for col in columns:
        if col == "english":
            kinds.append("primary")
        elif col == "example":
            kinds.append("primary")
        else:
            kinds.append("secondary")

    header_h = 0.56
    row_heights: list[float] = [header_h]
    all_fonts: list[list[int]] = [[26] * n_cols]
    all_spacings: list[list[float]] = [[1.12] * n_cols]
    needs_split = False
    per_row_budget = min(avail / max(len(rows) + 1, 1), 1.45)

    for row in rows:
        vals = [row.get(c, "") for c in columns]
        rh, fpts, sps, split = fit_table_rows(
            vals,
            col_fracs,
            kinds,
            budget,
            content_width=content_width,
            per_row_budget=per_row_budget,
        )
        row_heights.append(rh)
        all_fonts.append(fpts)
        all_spacings.append(sps)
        if split:
            needs_split = True

    total = sum(row_heights)
    if total > avail * 1.02:
        needs_split = True
    return row_heights, all_fonts, all_spacings, needs_split


def fit_essay_block(
    essay_text: str,
    budget: LayoutBudget | None = None,
    *,
    content_width: float = 11.6,
    panel_height: float | None = None,
) -> FitResult:
    budget = budget or LAYOUT_REGISTRY["essay_body"]
    avail = panel_height if panel_height is not None else budget.content_height(with_pill=True)
    return fit_typography(
        essay_text.strip(),
        content_width,
        avail - 0.28,
        max_pt=budget.max_primary_pt,
        min_pt=budget.min_pt,
    )


def estimate_essay_panel_height(
    *,
    has_badge: bool = False,
    has_annotation: bool = True,
) -> float:
    """Match ``generate_classroom_pptx_v2.SlideBuilderV2.essay_slide`` chrome."""
    top = 1.62 + 0.08
    ann_h = 0.72 if has_annotation else 0.0
    return max(SLIDE_CONTENT_BOTTOM - top - ann_h - 0.06, 2.0)


@dataclass(frozen=True)
class TitleCoverLayout:
    stem_panel_h: float
    poster_panel_h: float
    stem_fit: FitResult
    poster_fit: FitResult | None


def plan_title_cover_layout(
    body_lines: list[str],
    poster_lines: list[str] | None,
    *,
    panel_top: float = TITLE_PANEL_TOP,
    bottom_y: float = SLIDE_CONTENT_BOTTOM,
    text_w: float = 11.2,
    poster_text_w: float | None = None,
) -> TitleCoverLayout:
    """Top-down stem + poster stack; panels shrink-wrap fitted paragraphs."""
    budget = LAYOUT_REGISTRY["title_body"]
    poster_clean = [ln for ln in (poster_lines or []) if ln.strip()]
    body_clean = [ln for ln in body_lines if ln.strip()]
    max_panel_h = bottom_y - panel_top - 0.08
    poster_gap = 0.12
    stem_pad = 0.36
    poster_pad = 0.36
    poster_text_w = poster_text_w if poster_text_w is not None else text_w - 0.4

    poster_panel_h = 0.0
    poster_fit: FitResult | None = None
    if poster_clean:
        min_stem_h = 0.9
        poster_inner_budget = max(0.45, max_panel_h - min_stem_h - poster_gap - poster_pad)
        poster_fit = fit_paragraphs(
            poster_clean,
            poster_text_w,
            poster_inner_budget,
            space_after_pt=8,
            max_pt=budget.max_secondary_pt,
            min_pt=budget.min_pt,
            pad_h_pt=10,
            pad_v_pt=8,
        )
        poster_panel_h = poster_fit.block_height * WPS_PANEL_FUDGE + poster_pad

    stem_budget = max_panel_h - poster_panel_h - (poster_gap if poster_clean else 0.0)
    if not poster_clean:
        stem_budget = max_panel_h
    stem_fit = fit_paragraphs(
        body_clean,
        text_w,
        max(0.55, stem_budget - stem_pad),
        space_after_pt=10,
        max_pt=budget.max_primary_pt,
        min_pt=budget.min_pt,
        pad_h_pt=10,
        pad_v_pt=8,
    )
    stem_panel_h = min(
        stem_budget,
        max(0.9, stem_fit.block_height * WPS_PANEL_FUDGE + stem_pad),
    )
    return TitleCoverLayout(stem_panel_h, poster_panel_h, stem_fit, poster_fit)


def title_cover_needs_poster_slide(
    body_lines: list[str],
    poster_lines: list[str] | None,
    *,
    panel_top: float = TITLE_PANEL_TOP,
    bottom_y: float = SLIDE_CONTENT_BOTTOM,
) -> bool:
    """True when stem + poster cannot fit one slide — poster goes to a follow-up page."""
    cover = plan_title_cover_layout(body_lines, poster_lines, panel_top=panel_top, bottom_y=bottom_y)
    if not poster_lines:
        return False
    if cover.poster_fit and cover.poster_fit.needs_split:
        return True
    if cover.stem_fit.needs_split:
        return True
    total = cover.stem_panel_h + cover.poster_panel_h + 0.12
    return total > bottom_y - panel_top - 0.06


def _poster_slide_chunks(poster_lines: list[str], *, max_lines: int = 2) -> list[list[str]]:
    """Pack poster descriptions: all on one slide when possible, else ≤max_lines per slide."""
    posters = [ln for ln in poster_lines if ln.strip()]
    if not posters:
        return []
    budget = LAYOUT_REGISTRY["title_body"]
    text_w = 11.2 - 0.4
    avail_h = SLIDE_CONTENT_BOTTOM - 1.70 - 0.20
    all_fit = fit_paragraphs(
        posters,
        text_w,
        avail_h - 0.36,
        space_after_pt=10,
        max_pt=budget.max_secondary_pt,
        min_pt=budget.min_pt,
        pad_h_pt=10,
        pad_v_pt=8,
    )
    if not all_fit.needs_split:
        return [posters]

    chunks: list[list[str]] = []
    current: list[str] = []
    for line in posters:
        trial = current + [line]
        trial_fit = fit_paragraphs(
            trial,
            text_w,
            avail_h - 0.36,
            space_after_pt=10,
            max_pt=budget.max_secondary_pt,
            min_pt=budget.min_pt,
            pad_h_pt=10,
            pad_v_pt=8,
        )
        if current and (len(current) >= max_lines or trial_fit.needs_split):
            chunks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        chunks.append(current)
    return chunks or [posters]


def expand_title_slides(slides: list[dict]) -> list[dict]:
    """Stem on cover; poster descriptions on one follow-up slide (split only when needed)."""
    expanded: list[dict] = []
    for spec in slides:
        if spec.get("type") != "title":
            expanded.append(spec)
            continue
        posters = spec.get("poster_lines") or []
        if posters:
            stem = dict(spec)
            stem.pop("poster_lines", None)
            expanded.append(stem)
            for chunk in _poster_slide_chunks(posters):
                expanded.append(
                    {
                        "type": "title_poster",
                        "title": "海报示意",
                        "poster_lines": chunk,
                        "_module": spec.get("_module"),
                    }
                )
        else:
            expanded.append(spec)
    return expanded


@dataclass(frozen=True)
class EssayStackLayout:
    body_top: float
    body_height: float
    annotation_top: float
    annotation_height: float
    body_fit: FitResult
    ann_fit: FitResult | None
    para_space_pt: int = 10
    indent_spaces: int = 4


def _essay_display_paragraphs(
    paragraphs: list[str],
) -> tuple[list[str], float, int, int]:
    """Display lines + typography matching ``essay_slide`` rendering."""
    import re

    from scripts.essay_format import essay_layout_for_length

    clean = [
        re.sub(r"\s*Word count:\s*\d+\s*$", "", p, flags=re.IGNORECASE).strip()
        for p in paragraphs
        if p.strip()
    ]
    line_spacing, para_space_pt, indent_spaces = essay_layout_for_length(clean)
    display = [(" " * indent_spaces) + p for p in clean]
    return display, line_spacing, para_space_pt, indent_spaces


def _essay_body_block_height(
    display_paragraphs: list[str],
    width_inches: float,
    font_pt: int,
    line_spacing: float,
    *,
    space_after_pt: float = 4,
    space_before_pt: int = 10,
) -> float:
    """Measure essay body height including indent, space_after, and space_before."""
    if not display_paragraphs:
        return 0.35
    eff_w, _ = effective_text_area(width_inches, 10.0, pad_h_pt=10, pad_v_pt=6)
    total = 0.0
    for i, para in enumerate(display_paragraphs):
        if i > 0:
            sb = space_before_pt if line_spacing >= 1.0 else 4
            total += sb / 72.0
        total += text_block_height(para, eff_w, font_pt, line_spacing)
        if i < len(display_paragraphs) - 1:
            total += space_after_pt / 72.0
    return total


def _fit_essay_body(
    display_paragraphs: list[str],
    width_inches: float,
    max_height_inches: float,
    *,
    line_spacing_hint: float,
    space_after_pt: float = 4,
    space_before_pt: int = 10,
) -> FitResult:
    """Fit essay body using the same spacing rules as the V2 renderer."""
    eff_w, eff_h = effective_text_area(width_inches, max_height_inches, pad_h_pt=10, pad_v_pt=6)
    cap = eff_h * FIT_FILL_RATIO
    if not display_paragraphs:
        return FitResult(26, 1.12, 0.35, needs_split=False)
    spacing_steps = [s for s in LINE_SPACING_STEPS if s <= line_spacing_hint + 0.02]
    if not spacing_steps:
        spacing_steps = list(LINE_SPACING_STEPS)
    for pt in FONT_STEPS:
        if pt > 28:
            continue
        if pt < 26:
            break
        for spacing in spacing_steps:
            if spacing < MIN_LINE_SPACING - 1e-6:
                break
            h = _essay_body_block_height(
                display_paragraphs,
                width_inches,
                pt,
                spacing,
                space_after_pt=space_after_pt,
                space_before_pt=space_before_pt,
            )
            if h <= cap:
                return FitResult(pt, spacing, h, needs_split=False)
    h = _essay_body_block_height(
        display_paragraphs,
        width_inches,
        26,
        MIN_LINE_SPACING,
        space_after_pt=space_after_pt,
        space_before_pt=space_before_pt,
    )
    return FitResult(26, MIN_LINE_SPACING, h, needs_split=True)


def plan_essay_stack(
    paragraphs: list[str],
    annotation: str,
    *,
    header_bottom: float = 1.70,
    bottom_y: float = SLIDE_CONTENT_BOTTOM,
    content_width: float = 11.6,
) -> EssayStackLayout:
    """Vertical stack: body from content_top, annotation strictly below rendered body."""
    content_top = header_bottom + 0.08
    text_w = content_width - 0.2
    ann_gap = 0.08
    ann_text = (annotation or "").strip()
    ann_h = 0.0
    ann_fit: FitResult | None = None
    if ann_text:
        ann_fit = fit_typography(ann_text, text_w, 2.5, max_pt=26, min_pt=26)
        ann_h = ann_fit.block_height * WPS_PANEL_FUDGE + 0.16

    body_max_h = bottom_y - content_top - ann_h - ann_gap - (0.06 if ann_text else 0.0)
    display, layout_ls, para_space_pt, indent_spaces = _essay_display_paragraphs(paragraphs)
    body_fit = _fit_essay_body(
        display,
        text_w,
        max(1.0, body_max_h),
        line_spacing_hint=layout_ls,
        space_after_pt=4,
        space_before_pt=para_space_pt,
    )
    rendered_h = body_fit.block_height
    body_height = min(body_max_h, max(1.2, rendered_h * WPS_PANEL_FUDGE + 0.12))
    body_top = content_top
    annotation_top = body_top + body_height + ann_gap
    return EssayStackLayout(
        body_top,
        body_height,
        annotation_top,
        ann_h,
        body_fit,
        ann_fit,
        para_space_pt=para_space_pt,
        indent_spaces=indent_spaces,
    )


def essay_stack_fits(
    paragraphs: list[str],
    annotation: str,
    *,
    header_bottom: float = 1.70,
    bottom_y: float = SLIDE_CONTENT_BOTTOM,
    content_width: float = 11.6,
) -> bool:
    """True when essay body + annotation fit one slide without overlap."""
    stack = plan_essay_stack(
        paragraphs,
        annotation,
        header_bottom=header_bottom,
        bottom_y=bottom_y,
        content_width=content_width,
    )
    if stack.body_fit.needs_split:
        return False
    if stack.ann_fit and stack.ann_fit.needs_split:
        return False
    return stack.annotation_top + stack.annotation_height <= bottom_y + 0.05


def essay_text_fits(
    essay_text: str,
    *,
    has_badge: bool = True,
    has_annotation: bool = True,
    content_width: float = 11.6,
) -> bool:
    from scripts.essay_format import prepare_classroom_essay_body

    paragraphs, wc, embedded_ann = prepare_classroom_essay_body(essay_text)
    if not paragraphs and essay_text.strip():
        paragraphs = [p.strip() for p in essay_text.split("\n\n") if p.strip()]
    if wc and paragraphs:
        import re

        last = re.sub(r"\s*Word count:\s*\d+\s*$", "", paragraphs[-1], flags=re.IGNORECASE).rstrip()
        paragraphs = paragraphs[:-1] + [f"{last}  Word count: {wc}"]
    ann = embedded_ann if has_annotation else ""
    return essay_stack_fits(paragraphs, ann, content_width=content_width)


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _split_essay_by_sentences(
    text: str,
    *,
    has_badge: bool,
    has_annotation: bool,
    content_width: float = 11.6,
) -> list[str]:
    sents = _split_sentences(text)
    if len(sents) <= 1:
        mid = max(1, len(text) // 2)
        return [text[:mid].strip(), text[mid:].strip()]
    parts: list[str] = []
    current: list[str] = []
    for sent in sents:
        trial = " ".join(current + [sent])
        if current and not essay_text_fits(
            trial,
            has_badge=has_badge,
            has_annotation=has_annotation,
            content_width=content_width,
        ):
            parts.append(" ".join(current))
            current = [sent]
            has_badge = False
            has_annotation = False
        else:
            current.append(sent)
    if current:
        parts.append(" ".join(current))
    return parts


def split_essay_text(
    essay_text: str,
    *,
    has_badge: bool = False,
    has_annotation: bool = True,
    content_width: float = 11.6,
) -> list[str]:
    text = essay_text.strip()
    if not text:
        return [""]
    if essay_text_fits(
        text,
        has_badge=has_badge,
        has_annotation=has_annotation,
        content_width=content_width,
    ):
        return [text]

    blocks = [b.strip() for b in re.split(r"\n\s*\n+", text) if b.strip()]
    if len(blocks) <= 1:
        return _split_essay_by_sentences(
            text,
            has_badge=has_badge,
            has_annotation=has_annotation,
            content_width=content_width,
        )

    parts: list[str] = []
    current: list[str] = []
    ann = has_annotation
    badge = has_badge
    for block in blocks:
        trial = "\n\n".join(current + [block])
        if current and not essay_text_fits(
            trial,
            has_badge=badge,
            has_annotation=ann,
            content_width=content_width,
        ):
            parts.append("\n\n".join(current))
            current = [block]
            badge = False
            ann = False
        else:
            current.append(block)
    if current:
        parts.append("\n\n".join(current))

    final: list[str] = []
    for i, part in enumerate(parts):
        part_badge = has_badge if i == 0 else False
        part_ann = has_annotation if i == len(parts) - 1 else False
        if essay_text_fits(
            part,
            has_badge=part_badge,
            has_annotation=part_ann,
            content_width=content_width,
        ):
            final.append(part)
        else:
            final.extend(
                _split_essay_by_sentences(
                    part,
                    has_badge=part_badge,
                    has_annotation=part_ann,
                    content_width=content_width,
                )
            )
    return final or [text]


def expand_essay_slides(slides: list[dict]) -> list[dict]:
    """Split long essay specs into multiple slides when layout_fit requires it."""
    from scripts.essay_format import classroom_essay_plain_text, prepare_classroom_essay_body

    expanded: list[dict] = []
    for spec in slides:
        if spec.get("type") != "essay":
            expanded.append(spec)
            continue
        paragraphs, wc, ann = prepare_classroom_essay_body(spec.get("essay_text", ""))
        if not ann.strip():
            ann = (spec.get("annotation") or "").strip()
        plain = classroom_essay_plain_text(paragraphs)
        chunks = split_essay_text(
            plain,
            has_badge=False,
            has_annotation=bool(ann),
        )
        for idx, chunk in enumerate(chunks):
            new_spec = dict(spec)
            if idx == len(chunks) - 1 and wc:
                parts = [p.strip() for p in chunk.split("\n\n") if p.strip()]
                if parts:
                    last = re.sub(r"\s*Word count:\s*\d+\s*$", "", parts[-1], flags=re.IGNORECASE).rstrip()
                    parts[-1] = f"{last}  Word count: {wc}"
                chunk = "\n\n".join(parts)
            new_spec["essay_text"] = chunk
            new_spec["badge"] = None
            new_spec["annotation"] = ann if idx == len(chunks) - 1 else ""
            if len(chunks) > 1:
                new_spec["title"] = f"{spec['title']}（{idx + 1}/{len(chunks)}）"
            expanded.append(new_spec)
    return expanded
