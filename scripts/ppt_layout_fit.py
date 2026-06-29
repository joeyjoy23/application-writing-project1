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

# Renderer dynamic layout (display-layer fixes; content unchanged)
DYNAMIC_HEIGHT_MODE = True
RENDER_LINE_HEIGHT_INCH = 0.18
TEXT_BOX_PADDING_RATIO = 0.05
BULLET_LINE_SPACING_MULT = 1.20
BULLET_PARAGRAPH_SPACING_MULT = 1.15
TABLE_MAX_ROWS_PER_PAGE = 6
_PHRASE_COL_FRACS = [0.14, 0.52, 0.34]
_VERIFY_PAD_V_PT = 8.0
_VERIFY_PAD_H_PT = 6.0


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


def split_callout_lines(
    text: str,
    width_inches: float,
    *,
    budget: LayoutBudget | None = None,
    max_segments: int = 4,
) -> tuple[list[str], FitResult, float]:
    """Wrap B1 一句大实话 callout; return display lines, typography, card height."""
    budget = budget or LAYOUT_REGISTRY["content_key"]
    clean = text.replace("💡", "").strip()
    if not clean:
        return [], FitResult(budget.min_pt, 1.12, 0.35, False), 0.92
    banner_fit = fit_paragraphs(
        [clean],
        width_inches,
        1.65,
        max_pt=budget.max_secondary_pt,
        min_pt=budget.min_pt,
    )
    pt, sp = banner_fit.font_pt, banner_fit.line_spacing
    one_line_h = text_block_height("测", width_inches, pt, sp)
    max_seg_h = max(0.48, one_line_h * 1.25)

    def _split_segment(seg: str) -> list[str]:
        if text_block_height(seg, width_inches, pt, sp) <= max_seg_h and len(seg) <= 42:
            return [seg]
        mid = len(seg) // 2
        best = mid
        for sep in ("；", "，", "。", "、", " ", ","):
            pos = seg.rfind(sep, max(0, mid - 28), min(len(seg), mid + 28))
            if pos > 10:
                best = pos + len(sep)
                break
        a, b = seg[:best].strip(), seg[best:].strip()
        return [a, b] if a and b else [seg]

    if "；" in clean:
        raw_parts = [p.strip() for p in clean.split("；") if p.strip()]
        segments = [
            (p + "；") if i < len(raw_parts) - 1 else p for i, p in enumerate(raw_parts)
        ]
    else:
        segments = [clean]

    expanded: list[str] = []
    for seg in segments:
        expanded.extend(_split_segment(seg))
    segments = expanded[:max_segments]
    while len(segments) < max_segments:
        long_idx = max(range(len(segments)), key=lambda i: len(segments[i]))
        if len(segments[long_idx]) <= 42 and text_block_height(
            segments[long_idx], width_inches, pt, sp
        ) <= max_seg_h:
            break
        parts = _split_segment(segments[long_idx])
        if len(parts) == 1:
            break
        segments = segments[:long_idx] + parts + segments[long_idx + 1 :]
        segments = segments[:max_segments]
    content_h = text_block_height_paragraphs(segments, width_inches, pt, sp, space_after_pt=5)
    card_h = max(0.92, content_h + 0.34)
    return segments, FitResult(pt, sp, content_h, False), card_h


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
    heading = _trim_peel(str(point.get("heading") or ""), max_len=100)
    return {
        "label": (point.get("label") or "").strip() or "Point",
        "heading": heading,
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
    """Keep PEEL on one slide; renderer expands cards instead of splitting pages."""
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
        new_spec = dict(spec)
        new_spec["points"] = points
        new_spec["layout"] = "single" if len(points) == 1 else "dual"
        expanded.append(new_spec)
    return expanded


# --- Slide packing layer (merge first, split last) ---

PAGE_CAPACITY = 1.0
PAGE_SAFE_THRESHOLD = 0.92
DENSITY_MERGE_THRESHOLD = 0.35
DENSITY_SPLIT_THRESHOLD = 0.80
_PACK_PART_SUFFIX = re.compile(r"（\d+/\d+）|\(\d+/\d+\)| · Part \d+")


def _normalize_pack_title(title: str) -> str:
    t = _PACK_PART_SUFFIX.sub("", title or "")
    return re.sub(r"\s+", " ", t).strip()


def pack_group(spec: dict) -> str | None:
    """Merge group key; None means never merge this slide."""
    kind = spec.get("type")
    title = _normalize_pack_title(spec.get("title") or "")

    if kind == "content":
        if "批注" in title:
            base = title.replace(" · 批注", "").strip()
            return f"essay_annotation:{base}"
        if title.startswith("思维 ·") or "审题与路径" in title:
            return "thinking_core"
        if title == "海报示意":
            return "visual_poster"
        if "任务拆解" in title:
            return "task_checklist"
        return None

    if kind == "phrase_table":
        part = spec.get("part") or "full"
        if part not in ("body", "full"):
            return None
        if part == "full" and (
            (spec.get("table") or {}).get("topic_note")
            or (spec.get("table") or {}).get("fix_bad")
        ):
            return None
        parts = [p.strip() for p in title.split("·")]
        skill = parts[1] if len(parts) > 1 else title
        return f"phrase_body:{skill}"

    if kind == "vocab_table":
        tier = (spec.get("tier") or "").strip()
        if not tier and "·" in title:
            tier = title.split("·")[-1].strip()
        cols = tuple(spec.get("columns") or ())
        return f"vocab:{tier}:{cols}"

    if kind == "essay":
        base = _normalize_pack_title(spec.get("title") or "范文")
        return f"essay:{base}"

    return None


def slide_density_ratio(spec: dict) -> float:
    """Normalized page fill ratio (1.0 ≈ full usable body area)."""
    return estimate_slide_height(spec)


def _is_low_density(spec: dict) -> bool:
    return slide_density_ratio(spec) < DENSITY_MERGE_THRESHOLD


def _is_high_density(spec: dict) -> bool:
    return slide_density_ratio(spec) > DENSITY_SPLIT_THRESHOLD


def estimate_slide_height(spec: dict) -> float:
    """Normalized page fill ratio (1.0 ≈ full usable body area)."""
    kind = spec.get("type")
    budget_content = LAYOUT_REGISTRY["content_cards"]
    body_avail = budget_content.content_height(with_pill=True)

    if kind == "content":
        bullets = [str(b) for b in (spec.get("bullets") or []) if str(b).strip()]
        if not bullets:
            return 0.22
        key_lines = [b for b in bullets if b.startswith("💡") or "高分关键" in b or "最危险" in b]
        body_bullets = [b for b in bullets if b not in key_lines]
        reserve = 0.62 if spec.get("badge") else 0.0
        reserve += 1.05 if key_lines else 0.0
        chrome = 0.35 + reserve
        layout = fit_bullet_card_layout(
            body_bullets,
            budget_content,
            content_height=max(2.0, body_avail - reserve),
        )
        stack = sum(layout.heights) + 0.14 * max(len(body_bullets) - 1, 0)
        return min(1.5, (chrome + stack) / max(body_avail, 1.0))

    if kind == "phrase_table":
        part = spec.get("part") or "full"
        budget = LAYOUT_REGISTRY["phrase_table_footer" if part.startswith("footer") else "phrase_table_body"]
        avail = budget.content_height(with_pill=True)
        if part.startswith("footer") or (
            part == "full"
            and (
                (spec.get("table") or {}).get("topic_note")
                or (spec.get("table") or {}).get("fix_bad")
            )
        ):
            table = spec.get("table") or {}
            h = 0.35
            if table.get("topic_note"):
                h += 0.18
            if table.get("fix_bad") or table.get("fix_good"):
                h += 0.28
            return min(1.5, h / max(avail, 1.0))
        tiers = (spec.get("table") or {}).get("tiers") or []
        if not tiers:
            return 0.3
        row_heights, _, _, _ = phrase_table_body_heights(tiers, _PHRASE_COL_FRACS, budget)
        return min(1.5, (0.35 + sum(row_heights)) / max(avail, 1.0))

    if kind == "vocab_table":
        rows = spec.get("rows") or []
        columns = spec.get("columns") or []
        budget = LAYOUT_REGISTRY["vocab_table"]
        avail = budget.content_height(with_pill=True)
        if not rows:
            return 0.3
        row_heights, _, _, _ = fit_vocab_chunk(rows, columns, budget)
        return min(1.5, (0.35 + sum(row_heights)) / max(avail, 1.0))

    if kind == "essay":
        from scripts.essay_format import classroom_essay_plain_text, prepare_classroom_essay_body

        paragraphs, _wc, ann = prepare_classroom_essay_body(spec.get("essay_text", ""))
        plain = classroom_essay_plain_text(paragraphs) if paragraphs else (spec.get("essay_text") or "").strip()
        if not ann.strip():
            ann = (spec.get("annotation") or "").strip()
        budget = LAYOUT_REGISTRY["essay_body"]
        avail = budget.content_height(with_pill=True)
        body_fit = fit_essay_block(plain, budget, panel_height=avail * 0.72)
        h = 0.35 + body_fit.block_height
        if ann.strip():
            h += 0.18
        return min(1.5, h / max(avail, 1.0))

    if kind in ("peel", "title", "title_poster"):
        return 0.88
    return 0.35


def _pack_merge_specs(left: dict, right: dict) -> dict:
    kind = left.get("type")
    merged = dict(left)

    if kind == "content":
        merged["bullets"] = list(left.get("bullets") or []) + list(right.get("bullets") or [])
        merged["title"] = _normalize_pack_title(left.get("title") or "")
        if left.get("badge"):
            merged["badge"] = left["badge"]
        return merged

    if kind == "phrase_table":
        table = dict(left.get("table") or {})
        table["tiers"] = list(table.get("tiers") or []) + list((right.get("table") or {}).get("tiers") or [])
        merged["table"] = table
        merged["part"] = left.get("part") or "body"
        merged["title"] = _normalize_pack_title(left.get("title") or "")
        return merged

    if kind == "vocab_table":
        merged["rows"] = list(left.get("rows") or []) + list(right.get("rows") or [])
        merged["title"] = _normalize_pack_title(left.get("title") or "")
        merged["columns"] = left.get("columns") or right.get("columns")
        merged["tier"] = left.get("tier") or right.get("tier")
        return merged

    if kind == "essay":
        merged["essay_text"] = (left.get("essay_text") or "").rstrip() + "\n\n" + (right.get("essay_text") or "").lstrip()
        merged["annotation"] = (right.get("annotation") or left.get("annotation") or "")
        merged["badge"] = left.get("badge") or right.get("badge")
        merged["title"] = _normalize_pack_title(left.get("title") or "")
        return merged

    return merged


def _content_slide_fits(spec: dict) -> bool:
    """True when content bullets fit one slide at min font (capacity-driven)."""
    bullets = [str(b) for b in (spec.get("bullets") or []) if str(b).strip()]
    if not bullets:
        return True
    budget = LAYOUT_REGISTRY["content_cards"]
    key_lines = [b for b in bullets if b.startswith("💡") or "高分关键" in b or "最危险" in b]
    body_bullets = [b for b in bullets if b not in key_lines]
    reserve = 0.62 if spec.get("badge") else 0.0
    reserve += 1.05 if key_lines else 0.0
    avail = budget.content_height(with_pill=bool(spec.get("badge"))) - reserve
    layout = fit_bullet_card_layout(body_bullets, budget, content_height=max(2.0, avail))
    return not layout.needs_split


def _table_slide_fits(spec: dict) -> bool:
    return estimate_slide_height(spec) <= PAGE_SAFE_THRESHOLD


def _pack_can_merge(left: dict, right: dict) -> bool:
    gl, gr = pack_group(left), pack_group(right)
    low_density_pair = (
        _is_low_density(left)
        and _is_low_density(right)
        and left.get("type") == right.get("type")
        and left.get("type") in ("content", "phrase_table", "vocab_table")
    )
    if gl and gl == gr:
        group_key = gl
    elif low_density_pair:
        if left.get("type") == "phrase_table":
            if (left.get("part") or "") == "full" or (right.get("part") or "") == "full":
                return False
            if _pack_phrase_skill(left.get("title") or "") != _pack_phrase_skill(
                right.get("title") or ""
            ):
                return False
        group_key = f"low_density:{left.get('type')}"
    else:
        return False

    if group_key.startswith("phrase_body:") or (
        low_density_pair and left.get("type") == "phrase_table"
    ):
        la = len((left.get("table") or {}).get("tiers") or [])
        lb = len((right.get("table") or {}).get("tiers") or [])
        if la + lb > TABLE_MAX_ROWS_PER_PAGE:
            return False

    if group_key.startswith("vocab:") or (low_density_pair and left.get("type") == "vocab_table"):
        la = len(left.get("rows") or [])
        lb = len(right.get("rows") or [])
        if la + lb > TABLE_MAX_ROWS_PER_PAGE:
            return False

    candidate = _pack_merge_specs(left, right)
    kind = candidate.get("type")
    if kind == "content":
        return _content_slide_fits(candidate)
    if kind in ("phrase_table", "vocab_table"):
        return _table_slide_fits(candidate)
    if kind == "essay":
        return estimate_slide_height(candidate) <= PAGE_SAFE_THRESHOLD
    return estimate_slide_height(candidate) <= PAGE_SAFE_THRESHOLD


def _pack_split_phrase_table(spec: dict) -> list[dict]:
    part = spec.get("part") or "full"
    if part not in ("body", "full"):
        return [spec]
    tiers = list((spec.get("table") or {}).get("tiers") or [])
    if len(tiers) <= TABLE_MAX_ROWS_PER_PAGE and estimate_slide_height(spec) <= PAGE_CAPACITY:
        return [spec]
    out: list[dict] = []
    base_title = _normalize_pack_title(spec.get("title", "功能句型"))
    chunks: list[list] = []
    current: list = []
    for tier in tiers:
        trial = current + [tier]
        trial_spec = dict(spec)
        trial_spec["table"] = {**(spec.get("table") or {}), "tiers": trial}
        if len(trial) > TABLE_MAX_ROWS_PER_PAGE or estimate_slide_height(trial_spec) > PAGE_CAPACITY:
            if current:
                chunks.append(current)
            current = [tier]
        else:
            current = trial
    if current:
        chunks.append(current)
    n_parts = max(len(chunks), 1)
    for ci, chunk in enumerate(chunks):
        part_spec = dict(spec)
        part_spec["table"] = {**(spec.get("table") or {}), "tiers": chunk}
        part_spec["part"] = "body"
        if n_parts > 1:
            part_spec["title"] = f"{base_title} ({ci + 1}/{n_parts})"
        out.append(part_spec)
    return out or [spec]


def _pack_split_vocab_table(spec: dict) -> list[dict]:
    rows = list(spec.get("rows") or [])
    if len(rows) <= TABLE_MAX_ROWS_PER_PAGE and estimate_slide_height(spec) <= PAGE_CAPACITY:
        return [spec]
    out: list[dict] = []
    base_title = _normalize_pack_title(spec.get("title", "话题词块"))
    chunks: list[list] = []
    current: list = []
    for row in rows:
        trial = current + [row]
        trial_spec = dict(spec)
        trial_spec["rows"] = trial
        if len(trial) > TABLE_MAX_ROWS_PER_PAGE or estimate_slide_height(trial_spec) > PAGE_CAPACITY:
            if current:
                chunks.append(current)
            current = [row]
        else:
            current = trial
    if current:
        chunks.append(current)
    n_parts = max(len(chunks), 1)
    for ci, chunk in enumerate(chunks):
        part_spec = dict(spec)
        part_spec["rows"] = chunk
        if n_parts > 1:
            part_spec["title"] = f"{base_title} ({ci + 1}/{n_parts})"
        out.append(part_spec)
    return out or [spec]


def _pack_split_content(spec: dict) -> list[dict]:
    """Do not split content slides for overflow; renderer uses WPS-safe card heights."""
    return [spec]


def _pack_split_essay(spec: dict) -> list[dict]:
    if estimate_slide_height(spec) <= PAGE_CAPACITY:
        return [spec]
    from scripts.essay_format import classroom_essay_plain_text, prepare_classroom_essay_body

    paragraphs, _wc, ann = prepare_classroom_essay_body(spec.get("essay_text", ""))
    if not ann.strip():
        ann = (spec.get("annotation") or "").strip()
    plain = classroom_essay_plain_text(paragraphs) if paragraphs else (spec.get("essay_text") or "").strip()
    if essay_text_fits(plain, has_badge=bool(spec.get("badge")), has_annotation=bool(ann)):
        return [spec]
    chunks = split_essay_text(
        plain,
        has_badge=bool(spec.get("badge")),
        has_annotation=bool(ann),
    )
    if len(chunks) <= 1:
        return [spec]
    out: list[dict] = []
    base_title = _normalize_pack_title(spec.get("title") or "范文")
    for idx, chunk in enumerate(chunks):
        part = dict(spec)
        part["essay_text"] = chunk
        part["badge"] = spec.get("badge") if idx == 0 else None
        part["annotation"] = ann if idx == len(chunks) - 1 else ""
        if len(chunks) > 1:
            part["title"] = f"{base_title}（{idx + 1}/{len(chunks)}）"
        out.append(part)
    return out


def _pack_split_if_needed(spec: dict) -> list[dict]:
    kind = spec.get("type")
    if kind == "phrase_table":
        return _pack_split_phrase_table(spec)
    if kind == "vocab_table":
        return _pack_split_vocab_table(spec)
    if kind == "content":
        return _pack_split_content(spec)
    if kind == "essay":
        return _pack_split_essay(spec)
    if _is_high_density(spec) and kind not in ("essay",):
        return [spec]
    if estimate_slide_height(spec) > PAGE_CAPACITY:
        return [spec]
    return [spec]


def _pack_phrase_skill(title: str) -> str:
    parts = [p.strip() for p in (title or "").split("·")]
    return parts[1] if len(parts) > 1 else _normalize_pack_title(title)


def _pack_merge_cover_stem(slides: list[dict]) -> list[dict]:
    """Merge bare title cover + adjacent 真题/导入 content into one title spec."""
    if not slides:
        return []
    out: list[dict] = []
    i = 0
    while i < len(slides):
        spec = slides[i]
        if (
            spec.get("type") == "title"
            and not (spec.get("body") or [])
            and not (spec.get("poster_lines") or [])
            and i + 1 < len(slides)
        ):
            nxt = slides[i + 1]
            nxt_title = nxt.get("title") or ""
            if nxt.get("type") == "content" and ("真题" in nxt_title or "导入" in nxt_title):
                merged = dict(spec)
                merged["body"] = list(nxt.get("bullets") or [])
                if nxt.get("poster_lines"):
                    merged["poster_lines"] = list(nxt.get("poster_lines") or [])
                merged["_merged_cover_stem"] = True
                out.append(merged)
                i += 2
                continue
        out.append(dict(spec))
        i += 1
    return out


def _pack_merge_poster_into_cover(slides: list[dict]) -> list[dict]:
    """Inline all consecutive visual_poster slides into the cover/title page."""
    if not slides:
        return []
    out: list[dict] = []
    i = 0
    while i < len(slides):
        spec = slides[i]
        if spec.get("type") != "title":
            out.append(dict(spec))
            i += 1
            continue
        merged = dict(spec)
        i += 1
        while i < len(slides):
            nxt = slides[i]
            if nxt.get("type") == "content" and pack_group(nxt) == "visual_poster":
                bullets = list(nxt.get("bullets") or [])
                existing = list(merged.get("poster_lines") or [])
                merged["poster_lines"] = existing + bullets
                merged["_merged_cover_stem"] = True
                i += 1
            else:
                break
        out.append(merged)
    return out


def _pack_prepass_merges(slides: list[dict]) -> list[dict]:
    """Structural merges before group-based packing (cover, poster only; phrase body/footer stay split)."""
    s = _pack_merge_cover_stem(slides)
    s = _pack_merge_poster_into_cover(s)
    return s


def pack_slides(slides: list[dict]) -> list[dict]:
    """Merge adjacent compatible slides, then split only when capacity requires it."""
    if not slides:
        return []

    slides = _pack_prepass_merges(slides)

    merged: list[dict] = []
    for spec in slides:
        if merged and _pack_can_merge(merged[-1], spec):
            merged[-1] = _pack_merge_specs(merged[-1], spec)
        else:
            merged.append(dict(spec))

    packed: list[dict] = []
    for spec in merged:
        packed.append(dict(spec))

    from scripts.teaching_flow_orchestrator import orchestrate_teaching_flow

    flow = orchestrate_teaching_flow(packed)
    final: list[dict] = []
    for spec in flow:
        final.extend(_pack_split_if_needed(spec))
    return final


def expand_content_slides(slides: list[dict]) -> list[dict]:
    """Pass-through: renderer expands card heights instead of splitting content pages."""
    return list(slides)


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


def apply_content_line_spacing(fit: FitResult) -> FitResult:
    """Bump line spacing for content bullets (display layer only)."""
    sp = min(1.35, fit.line_spacing * BULLET_LINE_SPACING_MULT)
    return FitResult(fit.font_pt, sp, fit.block_height, fit.needs_split)


def content_block_height(
    text: str,
    width_inches: float,
    font_pt: int,
    line_spacing: float,
) -> float:
    """Text block height with paragraph spacing bump."""
    base = text_block_height(text, width_inches, font_pt, line_spacing)
    return base * BULLET_PARAGRAPH_SPACING_MULT


def verify_safe_textbox_height(
    content_height_inches: float,
    *,
    pad_v_pt: float = _VERIFY_PAD_V_PT,
    extra_chrome: float = 0.10,
) -> float:
    """Textbox height that clears verify_text_fit (WPS safety + padding)."""
    padded = content_height_inches * (1.0 + 2.0 * TEXT_BOX_PADDING_RATIO)
    return padded / WPS_SAFETY_FACTOR + 2.0 * pad_v_pt / 72.0 + extra_chrome


def verify_safe_row_height(content_block_h: float, *, extra: float = 0.36) -> float:
    """Table row height that clears cell overflow verify."""
    padded = content_block_h * (1.0 + 2.0 * TEXT_BOX_PADDING_RATIO)
    return max(0.52, padded / (WPS_SAFETY_FACTOR * 0.92) + extra)


def auto_fit_slide_height(
    bullets: list[str],
    budget: LayoutBudget,
    *,
    content_width: float = 12.0,
    content_height: float | None = None,
    gap: float = 0.14,
    card_pad_v: float = 0.32,
    card_min_h: float = 0.56,
) -> BulletCardLayout:
    """Dynamic card heights: expand for long bullets, never shrink below min font."""
    return fit_bullet_card_layout(
        bullets,
        budget,
        content_width=content_width,
        content_height=content_height,
        gap=gap,
        card_pad_v=card_pad_v,
        card_min_h=card_min_h,
    )


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
    """Variable-height stacked cards; dynamic mode expands height instead of scaling font."""
    if not bullets:
        return BulletCardLayout([], [], needs_split=False)

    avail_h = content_height if content_height is not None else budget.content_height(with_pill=True)
    text_w = max(4.0, content_width - 0.34)

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
        fit = apply_content_line_spacing(fit)
        block_h = content_block_height(bullet, text_w, fit.font_pt, fit.line_spacing)
        from scripts.wps_layout_verify import compute_card_height

        box_h = compute_card_height(
            bullet, fit.font_pt, text_w, bullet=True, min_h=card_min_h
        )
        card_h = max(card_min_h, box_h)
        natural.append(card_h)
        fits.append(FitResult(fit.font_pt, fit.line_spacing, block_h, fit.needs_split))

    total = sum(natural) + gap * max(len(bullets) - 1, 0)
    if total <= avail_h * 1.01:
        return BulletCardLayout(natural, fits, needs_split=False)

    if DYNAMIC_HEIGHT_MODE:
        expanded: list[float] = []
        for card_h, bullet, fit in zip(natural, bullets, fits):
            if is_arrow_separator(bullet):
                expanded.append(card_h)
                continue
            lines = line_count(bullet, text_w, fit.font_pt)
            cap_lines = max(1.0, (card_h - card_pad_v) / RENDER_LINE_HEIGHT_INCH)
            if lines > cap_lines:
                card_h = card_h + (lines - cap_lines) * RENDER_LINE_HEIGHT_INCH
            expanded.append(card_h)
        total_exp = sum(expanded) + gap * max(len(bullets) - 1, 0)
        return BulletCardLayout(expanded, fits, needs_split=total_exp > avail_h * 1.02)

    inner = max(0.5, avail_h - gap * max(len(bullets) - 1, 0))
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
    for bullet, card_h in zip(bullets, scaled):
        if is_arrow_separator(bullet):
            refit.append(FitResult(budget.max_primary_pt, 1.0, ARROW_SEP_HEIGHT, needs_split=False))
            continue
        fit = fit_typography(
            bullet,
            text_w,
            max(0.35, card_h - card_pad_v + 0.06),
            max_pt=budget.max_primary_pt,
            min_pt=budget.min_pt,
        )
        refit.append(apply_content_line_spacing(fit))
        if fit.needs_split:
            needs_split = True
    return BulletCardLayout(scaled, refit, needs_split=needs_split)


def phrase_table_body_heights(
    tiers: list[dict],
    col_fracs: list[float],
    budget: LayoutBudget | None = None,
) -> tuple[list[float], list[list[int]], list[list[float]], bool]:
    """Header + tier row heights/fonts/spacings; never scale row height without typography."""
    budget = budget or LAYOUT_REGISTRY["phrase_table_body"]
    avail = budget.content_height(with_pill=True)
    header_h = 0.68
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

    for ri in range(1, len(row_heights)):
        row_heights[ri] = verify_safe_row_height(row_heights[ri] - 0.20, extra=0.24)

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

    header_h = 0.68
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

    for ri in range(1, len(row_heights)):
        row_heights[ri] = verify_safe_row_height(row_heights[ri] - 0.20, extra=0.24)

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
    stem_panel_h = max(0.9, stem_fit.block_height * WPS_PANEL_FUDGE + stem_pad)
    stem_panel_h = max(stem_panel_h, verify_safe_textbox_height(stem_fit.block_height, extra_chrome=stem_pad))
    if poster_clean and poster_panel_h:
        poster_panel_h = max(
            poster_panel_h,
            verify_safe_textbox_height(poster_fit.block_height if poster_fit else 0.45, extra_chrome=poster_pad),
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


def expand_title_slides(slides: list[dict]) -> list[dict]:
    """Keep poster_lines inline on cover — no standalone title_poster pages."""
    return list(slides)


@dataclass(frozen=True)
class EssayStackLayout:
    body_top: float
    body_height: float
    annotation_top: float
    annotation_height: float
    body_fit: FitResult
    ann_fit: FitResult | None


def plan_essay_stack(
    paragraphs: list[str],
    annotation: str,
    *,
    header_bottom: float = 1.70,
    bottom_y: float = SLIDE_CONTENT_BOTTOM,
    content_width: float = 11.6,
) -> EssayStackLayout:
    """Vertical stack: body from content_top, annotation strictly below body."""
    content_top = header_bottom + 0.08
    text_w = content_width - 0.2
    ann_gap = 0.08
    ann_text = (annotation or "").strip()
    ann_h = 0.0
    ann_fit: FitResult | None = None
    if ann_text:
        ann_fit = fit_typography(ann_text, text_w, 2.5, max_pt=26, min_pt=26)
        ann_h = ann_fit.block_height + 0.16

    body_max_h = bottom_y - content_top - ann_h - ann_gap - (0.06 if ann_text else 0.0)
    lines = [p for p in paragraphs if p.strip()]
    body_fit = fit_paragraphs(
        lines,
        text_w,
        max(1.0, body_max_h),
        space_after_pt=6,
        max_pt=28,
        min_pt=26,
        min_spacing=0.9,
        pad_h_pt=10,
        pad_v_pt=6,
    )
    body_height = min(body_max_h, max(1.2, verify_safe_textbox_height(body_fit.block_height, extra_chrome=0.18)))
    body_top = content_top
    annotation_top = body_top + body_height + ann_gap
    return EssayStackLayout(body_top, body_height, annotation_top, ann_h, body_fit, ann_fit)


def essay_text_fits(
    essay_text: str,
    *,
    has_badge: bool = True,
    has_annotation: bool = True,
    content_width: float = 11.6,
) -> bool:
    panel_h = estimate_essay_panel_height(has_badge=has_badge, has_annotation=has_annotation)
    return not fit_essay_block(
        essay_text,
        content_width=content_width,
        panel_height=panel_h,
    ).needs_split


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
