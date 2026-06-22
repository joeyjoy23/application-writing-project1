#!/usr/bin/env python
"""V2 classroom PPT — stronger hierarchy, youth appeal, logic-first layout."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from scripts.generate_classroom_pptx import (
    BOTTOM_Y,
    CONTENT_W,
    FONT_ANNOTATION,
    FONT_BADGE,
    FONT_BODY,
    FONT_ESSAY,
    FONT_ESSAY_SIZE,
    FONT_SECTION,
    FONT_TABLE,
    FONT_TITLE,
    FONT_UI,
    MARGIN_L,
    MIN_FONT_PT,
    SLIDE_H,
    SLIDE_W,
    WHITE,
    _clean_pptx_dir,
    _collect_font_sizes,
    _configure_text_frame,
    _enforce_word_wrap,
    _find_page_numbers,
    _scan_pptx_xml_pagination,
    build_deck_with_stage3,
    build_mental_health_deck,
    expand_slide_specs,
    verify_text_fit,
)
from scripts.ppt_layout_fit import (
    LAYOUT_REGISTRY,
    PEEL_CARD_WIDTH,
    effective_text_area,
    fit_banner,
    fit_bullet_card_layout,
    fit_dual_cards,
    fit_essay_block,
    fit_fix_cards,
    fit_paragraphs,
    fit_peel_point,
    fit_table_rows,
    fit_typography,
    fit_vocab_chunk,
    line_count,
    normalize_peel_point,
    phrase_table_body_heights,
    text_block_height_paragraphs,
)

# V2 palette — brighter, student-friendly
VIOLET = RGBColor(0x7C, 0x3A, 0xED)
INDIGO = RGBColor(0x63, 0x66, 0xF1)
CORAL = RGBColor(0xF4, 0x72, 0xB6)
MINT = RGBColor(0x2D, 0xD4, 0xBF)
SKY = RGBColor(0x38, 0xBD, 0xF8)
AMBER = RGBColor(0xFB, 0xBF, 0x24)
INK = RGBColor(0x0F, 0x17, 0x2A)
MUTED = RGBColor(0x47, 0x55, 0x69)
WARN = RGBColor(0xDC, 0x26, 0x26)
PANEL_LILAC = RGBColor(0xF5, 0xF3, 0xFF)
PANEL_MINT = RGBColor(0xEC, 0xFD, 0xF5)
PANEL_SKY = RGBColor(0xF0, 0xF9, 0xFF)
PANEL_WARN = RGBColor(0xFE, 0xF2, 0xF2)
BORDER = RGBColor(0xE2, 0xE8, 0xF0)

SECTION_COLORS = {
    "审题": INDIGO,
    "范文": CORAL,
    "句型": MINT,
    "活动": SKY,
    "迁移": VIOLET,
    "小结": INDIGO,
}

CONTENT_TEXT_W = CONTENT_W

DEFAULT_V2_OUT = Path(r"d:\Downloads\ppt-work\mental_health_classroom.pptx")

_TIER_ACCENT = {
    "基础": MUTED,
    "必备": MUTED,
    "进阶": MINT,
    "高级": VIOLET,
    "亮点": CORAL,
}


def _tier_color(label: str) -> RGBColor:
    for key, color in _TIER_ACCENT.items():
        if key in label:
            return color
    return INDIGO


def _phrase_tier_note(tier: dict) -> str:
    level = tier.get("level", "")
    if level == "基础句":
        return ""
    note = tier.get("chinese", "") or ""
    hs = tier.get("high_score")
    if hs:
        note = f"{note}\n{hs}" if note else hs
    return note


def _inject_v2_structure(slides: list[dict]) -> list[dict]:
    """Insert section dividers for clearer lesson arc (no roadmap / illustrations)."""
    out: list[dict] = []
    section_markers = {
        "审题 ·": ("01", "读懂题目", "写什么 · 写给谁 · 怎么写", INDIGO),
        "PEEL": ("02", "范文骨架", "先搭 PEEL，再读三版范文", CORAL),
        "基础版范文": ("02", "范文骨架", "先搭 PEEL，再读三版范文", CORAL),
        "讲评活动": ("03", "讲评升级", "元素 → 主题 → 逻辑链", SKY),
        "功能句型": ("04", "语言工具箱", "观点 · 论据 · 衔接 · 词块", MINT),
        "当堂迁移": ("05", "当堂练", "用同样方法写新题", VIOLET),
        "课堂小结": ("06", "带走什么", "审题 → 范文 → 句型 → 迁移", INDIGO),
    }
    seen_sections: set[str] = set()

    for spec in slides:
        title = spec.get("title", "")
        for key, (num, name, sub, color) in section_markers.items():
            if key in title and num not in seen_sections:
                out.append(
                    {
                        "type": "divider",
                        "num": num,
                        "name": name,
                        "subtitle": sub,
                        "color": color,
                    }
                )
                seen_sections.add(num)
                break
        out.append(spec)
    return out


class SlideBuilderV2:
    def __init__(self, prs: Presentation) -> None:
        self.prs = prs
        self._anim_seq = 0

    def _reset_anim(self) -> None:
        self._anim_seq = 0

    def _tag_anim(self, shape) -> None:
        self._anim_seq += 1
        shape.name = f"anim_{self._anim_seq:03d}"

    def _pill(
        self,
        slide,
        text: str,
        *,
        left,
        top,
        width,
        height,
        fill: RGBColor,
        text_color: RGBColor = WHITE,
    ) -> None:
        pill = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            left,
            top,
            width,
            height,
        )
        pill.fill.solid()
        pill.fill.fore_color.rgb = fill
        pill.line.fill.background()
        _configure_text_frame(pill.text_frame, anchor=MSO_ANCHOR.MIDDLE, pad_h=10, pad_v=6)
        p = pill.text_frame.paragraphs[0]
        p.text = text
        p.font.name = FONT_UI
        p.font.size = Pt(26)
        p.font.bold = True
        p.font.color.rgb = text_color
        p.alignment = PP_ALIGN.CENTER

    def _blank(self):
        self._reset_anim()
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        bg = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), SLIDE_W, SLIDE_H
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = WHITE
        bg.line.fill.background()
        return slide

    def _section_tag(self, slide, label: str) -> RGBColor:
        color = SECTION_COLORS.get(label, INDIGO)
        tag = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(0.45),
            Inches(0.12),
            Inches(1.35),
            Inches(0.48),
        )
        tag.fill.solid()
        tag.fill.fore_color.rgb = color
        tag.line.fill.background()
        tf = tag.text_frame
        _configure_text_frame(tf, anchor=MSO_ANCHOR.MIDDLE, pad_h=4, pad_v=2)
        p = tf.paragraphs[0]
        p.text = label
        p.font.name = FONT_UI
        p.font.size = Pt(26)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.alignment = PP_ALIGN.CENTER
        return color

    def _header(self, slide, title: str, section: str | None = None) -> float:
        if section:
            color = self._section_tag(slide, section)
        else:
            color = INDIGO
        bar = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE,
            Inches(0),
            Inches(0.72),
            SLIDE_W,
            Inches(0.78),
        )
        bar.fill.solid()
        bar.fill.fore_color.rgb = color
        bar.line.fill.background()
        box = slide.shapes.add_textbox(Inches(0.55), Inches(0.82), Inches(12.2), Inches(0.62))
        tf = box.text_frame
        _configure_text_frame(tf, anchor=MSO_ANCHOR.MIDDLE)
        p = tf.paragraphs[0]
        p.text = title
        p.font.name = FONT_UI
        p.font.size = FONT_TITLE
        p.font.bold = True
        p.font.color.rgb = WHITE
        return 1.62

    def title_slide(self, title: str, subtitle: str, body_lines: list[str]) -> None:
        slide = self._blank()
        hero = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), SLIDE_W, Inches(2.35)
        )
        hero.fill.solid()
        hero.fill.fore_color.rgb = VIOLET
        hero.line.fill.background()
        stripe = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(2.35), SLIDE_W, Inches(0.06)
        )
        stripe.fill.solid()
        stripe.fill.fore_color.rgb = CORAL
        stripe.line.fill.background()

        tbox = slide.shapes.add_textbox(MARGIN_L, Inches(0.38), Inches(8.5), Inches(0.72))
        _configure_text_frame(tbox.text_frame, anchor=MSO_ANCHOR.MIDDLE)
        p = tbox.text_frame.paragraphs[0]
        p.text = title
        p.font.name = FONT_UI
        p.font.size = FONT_TITLE
        p.font.bold = True
        p.font.color.rgb = WHITE

        sbox = slide.shapes.add_textbox(MARGIN_L, Inches(1.05), Inches(8.5), Inches(0.55))
        _configure_text_frame(sbox.text_frame)
        p = sbox.text_frame.paragraphs[0]
        p.text = subtitle
        p.font.name = FONT_UI
        p.font.size = FONT_SECTION
        p.font.color.rgb = RGBColor(0xE9, 0xD5, 0xFF)

        self._pill(
            slide,
            "本课任务：选海报\n写理由",
            left=MARGIN_L,
            top=Inches(1.72),
            width=Inches(4.6),
            height=Inches(0.78),
            fill=CORAL,
        )

        panel_top = 2.55
        max_panel_h = BOTTOM_Y - panel_top - 0.08
        budget = LAYOUT_REGISTRY["title_body"]
        body_lines_clean = [line for line in body_lines if line.strip()]
        text_w = float(CONTENT_TEXT_W.inches) - 0.4
        fit = fit_paragraphs(
            body_lines_clean,
            text_w,
            max_panel_h - 0.32,
            space_after_pt=10,
            max_pt=budget.max_primary_pt,
            min_pt=budget.min_pt,
            pad_h_pt=10,
            pad_v_pt=8,
        )
        panel_h = min(max_panel_h, max(2.1, fit.block_height + 0.4))
        panel_top_adj = panel_top + max(0.0, (max_panel_h - panel_h) * 0.25)
        panel = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            MARGIN_L,
            Inches(panel_top_adj),
            CONTENT_TEXT_W,
            Inches(panel_h),
        )
        panel.fill.solid()
        panel.fill.fore_color.rgb = PANEL_SKY
        panel.line.color.rgb = BORDER

        space_after = Pt(10 if fit.line_spacing >= 1.0 else 6)
        body_h = max(0.8, panel_h - 0.32)

        body = slide.shapes.add_textbox(
            MARGIN_L + Inches(0.2),
            Inches(panel_top_adj + 0.16),
            CONTENT_TEXT_W - Inches(0.4),
            Inches(body_h),
        )
        _configure_text_frame(body.text_frame, pad_h=10, pad_v=8)
        tf = body.text_frame
        first = True
        for line in body_lines_clean:
            para = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            para.text = line
            para.font.name = FONT_UI
            para.font.size = Pt(fit.font_pt)
            para.font.color.rgb = INK
            para.space_after = space_after
            para.line_spacing = fit.line_spacing

    def roadmap_slide(self, steps: list[tuple[str, str, str]]) -> None:
        slide = self._blank()
        top = self._header(slide, "本课怎么走？（逻辑路线图）", section="路线")
        colors = [INDIGO, CORAL, MINT, SKY, VIOLET]
        col_w = 2.25
        gap = 0.15
        start_x = 0.55
        for i, (num, name, hint) in enumerate(steps):
            x = start_x + i * (col_w + gap)
            c = colors[i % len(colors)]
            card = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                Inches(x),
                Inches(top + 0.15),
                Inches(col_w),
                Inches(4.85),
            )
            card.fill.solid()
            card.fill.fore_color.rgb = PANEL_LILAC if i % 2 == 0 else PANEL_MINT
            card.line.color.rgb = c
            card.line.width = Pt(2)

            circle = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.OVAL,
                Inches(x + 0.75),
                Inches(top + 0.35),
                Inches(0.75),
                Inches(0.75),
            )
            circle.fill.solid()
            circle.fill.fore_color.rgb = c
            circle.line.fill.background()
            np = circle.text_frame.paragraphs[0]
            np.text = num
            np.font.name = FONT_UI
            np.font.size = Pt(28)
            np.font.bold = True
            np.font.color.rgb = WHITE
            np.alignment = PP_ALIGN.CENTER

            tbox = slide.shapes.add_textbox(
                Inches(x + 0.12),
                Inches(top + 1.35),
                Inches(col_w - 0.24),
                Inches(1.9),
            )
            _configure_text_frame(tbox.text_frame, anchor=MSO_ANCHOR.TOP)
            p1 = tbox.text_frame.paragraphs[0]
            p1.text = name
            p1.font.name = FONT_UI
            p1.font.size = Pt(28)
            p1.font.bold = True
            p1.font.color.rgb = INK
            p1.alignment = PP_ALIGN.CENTER
            p2 = tbox.text_frame.add_paragraph()
            p2.text = hint
            p2.font.name = FONT_UI
            p2.font.size = Pt(26)
            p2.font.color.rgb = MUTED
            p2.alignment = PP_ALIGN.CENTER

            if i < len(steps) - 1:
                arrow = slide.shapes.add_textbox(
                    Inches(x + col_w - 0.05),
                    Inches(top + 2.05),
                    Inches(0.42),
                    Inches(0.55),
                )
                ap = arrow.text_frame.paragraphs[0]
                ap.text = "→"
                ap.font.name = FONT_UI
                ap.font.size = Pt(26)
                ap.font.color.rgb = MUTED
                ap.alignment = PP_ALIGN.CENTER
                _configure_text_frame(arrow.text_frame, anchor=MSO_ANCHOR.MIDDLE)

        note = slide.shapes.add_textbox(MARGIN_L, Inches(6.55), CONTENT_W, Inches(0.55))
        p = note.text_frame.paragraphs[0]
        p.text = "【抓逻辑】每步都回答：我选哪个？为什么？用什么英语说？"
        p.font.name = FONT_UI
        p.font.size = Pt(26)
        p.font.bold = True
        p.font.color.rgb = VIOLET

    def divider_slide(self, num: str, name: str, subtitle: str, color: RGBColor) -> None:
        slide = self._blank()
        block = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(0), Inches(0), SLIDE_W, SLIDE_H
        )
        block.fill.solid()
        block.fill.fore_color.rgb = color
        block.line.fill.background()

        num_box = slide.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(3.5), Inches(1.2))
        p = num_box.text_frame.paragraphs[0]
        p.text = num
        p.font.name = FONT_UI
        p.font.size = Pt(72)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

        name_box = slide.shapes.add_textbox(Inches(0.8), Inches(3.0), Inches(11.5), Inches(1.0))
        p = name_box.text_frame.paragraphs[0]
        p.text = name
        p.font.name = FONT_UI
        p.font.size = Pt(44)
        p.font.bold = True
        p.font.color.rgb = WHITE

        sub_box = slide.shapes.add_textbox(Inches(0.8), Inches(4.05), Inches(11.0), Inches(0.8))
        p = sub_box.text_frame.paragraphs[0]
        p.text = subtitle
        p.font.name = FONT_UI
        p.font.size = Pt(28)
        p.font.color.rgb = RGBColor(0xE0, 0xE7, 0xFF)

    def _guess_section(self, title: str) -> str | None:
        if "审题" in title or "动笔" in title or "易错" in title and "深化" not in title:
            return "审题"
        if "PEEL" in title or "范文" in title or "对比" in title or "讲评" in title:
            return "范文"
        if "句型" in title or "词块" in title:
            return "句型"
        if "迁移" in title:
            return "迁移"
        if "小结" in title:
            return "小结"
        if "活动" in title:
            return "活动"
        return None

    def content_slide(
        self,
        title: str,
        bullets: list[str],
        *,
        badge: str | None = None,
        panel: bool = False,
        warn_panel: bool = False,
    ) -> None:
        slide = self._blank()
        section = self._guess_section(title)
        top = self._header(slide, title, section=section)

        if badge:
            pill_w = Inches(min(11.5, 0.18 * len(badge) + 2.4))
            self._pill(
                slide,
                badge,
                left=MARGIN_L,
                top=Inches(top + 0.05),
                width=pill_w,
                height=Inches(0.55),
                fill=AMBER if "Stage 4" in badge else SKY,
                text_color=INK,
            )
            top += 0.62

        # Key insight banner
        key_lines = [b for b in bullets if b.startswith("💡") or "高分关键" in b or "最危险" in b]
        body_bullets = [b for b in bullets if b not in key_lines]
        if key_lines:
            budget = LAYOUT_REGISTRY["content_key"]
            banner_fit = fit_banner(key_lines[0], budget)
            h = max(0.88, banner_fit.block_height + 0.18)
            banner = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                MARGIN_L,
                Inches(top),
                CONTENT_W,
                Inches(h),
            )
            banner.fill.solid()
            banner.fill.fore_color.rgb = AMBER
            banner.line.fill.background()
            lbl = slide.shapes.add_textbox(MARGIN_L + Inches(0.15), Inches(top + 0.06), Inches(1.6), Inches(0.52))
            lp = lbl.text_frame.paragraphs[0]
            lp.text = "抓重点"
            lp.font.name = FONT_UI
            lp.font.size = Pt(26)
            lp.font.bold = True
            lp.font.color.rgb = INK
            txt = slide.shapes.add_textbox(MARGIN_L + Inches(1.5), Inches(top + 0.1), Inches(10.2), Inches(h - 0.16))
            _configure_text_frame(txt.text_frame)
            tp = txt.text_frame.paragraphs[0]
            tp.text = key_lines[0].replace("💡", "").strip()
            tp.font.name = FONT_UI
            tp.font.size = Pt(banner_fit.font_pt)
            tp.font.bold = True
            tp.font.color.rgb = INK
            tp.line_spacing = banner_fit.line_spacing
            top += h + 0.07

        content_top = top + 0.08
        content_h = BOTTOM_Y - content_top
        fill = PANEL_WARN if warn_panel else (PANEL_LILAC if panel else PANEL_SKY)
        if "PEEL" in title:
            self._peel_cards(slide, body_bullets, content_top, content_h)
            return

        self._bullet_cards(
            slide,
            body_bullets[:5],
            content_top,
            float(MARGIN_L.inches) + 0.05,
            float(CONTENT_W.inches) - 0.1,
            content_h,
            fill,
        )

    def _bullet_cards(
        self,
        slide,
        bullets: list[str],
        top: float,
        left: float,
        width: float,
        height: float,
        fill: RGBColor,
    ) -> None:
        if not bullets:
            return
        tier_colors = {"基础": MUTED, "进阶": MINT, "高级": VIOLET, "亮点": CORAL, "必备": MUTED}
        gap = 0.14
        budget = LAYOUT_REGISTRY["content_cards"]
        layout = fit_bullet_card_layout(
            bullets,
            budget,
            content_width=width,
            content_height=height,
            gap=gap,
        )
        stack_h = sum(layout.heights) + gap * max(len(bullets) - 1, 0)
        y = top
        if stack_h < height * 0.72:
            y = top + (height - stack_h) * 0.35
        for i, bullet in enumerate(bullets):
            card_h = layout.heights[i]
            accent = INDIGO
            if bullet.startswith("★"):
                accent = CORAL
            elif bullet.startswith("→"):
                accent = MINT
            else:
                for tier, tc in tier_colors.items():
                    if bullet.startswith(tier):
                        accent = tc
                        break

            card = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                Inches(left),
                Inches(y),
                Inches(width),
                Inches(card_h),
            )
            card.fill.solid()
            card.fill.fore_color.rgb = fill
            card.line.color.rgb = accent
            card.line.width = Pt(2)

            bar = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.RECTANGLE,
                Inches(left),
                Inches(y + 0.06),
                Inches(0.08),
                Inches(card_h - 0.12),
            )
            bar.fill.solid()
            bar.fill.fore_color.rgb = accent
            bar.line.fill.background()

            text = bullet
            bold = bullet.startswith("★") or any(bullet.startswith(t) for t in tier_colors)
            color = INK
            if bullet.startswith("★"):
                color = CORAL
            elif bullet.startswith("→"):
                color = MINT
            else:
                for tier, tc in tier_colors.items():
                    if bullet.startswith(tier):
                        color = tc
                        break
                if not text.startswith(("•", "→", "★")) and not bold:
                    text = f"• {bullet}"

            box = slide.shapes.add_textbox(
                Inches(left + 0.22),
                Inches(y + 0.1),
                Inches(width - 0.34),
                Inches(card_h - 0.18),
            )
            _configure_text_frame(box.text_frame, pad_h=6, pad_v=4)
            para = box.text_frame.paragraphs[0]
            para.text = text
            para.font.name = FONT_UI
            fit = layout.fits[i] if i < len(layout.fits) else None
            para.font.size = Pt(fit.font_pt if fit else 28)
            para.font.bold = bold
            para.font.color.rgb = color
            para.line_spacing = fit.line_spacing if fit else 1.15
            y += card_h + gap

    def _peel_cards(self, slide, bullets: list[str], top: float, height: float) -> None:
        p1, p2 = [], []
        current = p1
        for b in bullets:
            if "Point 2" in b or "★ Point 2" in b:
                current = p2
            current.append(b)
        left_text = "\n".join(
            line.replace("核心句 P：", "P · ").replace("拓展 E：", "E · ")
            for line in p1
            if not line.startswith("★")
        )
        right_items = p2 or p1
        right_text = "\n".join(
            line.replace("核心句 P：", "P · ").replace("拓展 E：", "E · ")
            for line in right_items
            if not line.startswith("★")
        )
        budget = LAYOUT_REGISTRY["peel_dual"]
        w = 5.85
        lf, rf = fit_dual_cards(left_text, right_text, w, height, budget)
        card_h = min(height, max(lf.block_height, rf.block_height) + 0.82)
        card_top = top
        if card_h < height * 0.72:
            card_top = top + (height - card_h) * 0.35
        groups = [("① 选择", p1, INDIGO, lf), ("② 理由", right_items, CORAL, rf)]
        for idx, (label, items, color, fit) in enumerate(groups):
            x = 0.55 + idx * (w + 0.25)
            card = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                Inches(x),
                Inches(card_top),
                Inches(w),
                Inches(card_h),
            )
            card.fill.solid()
            card.fill.fore_color.rgb = PANEL_LILAC if idx == 0 else RGBColor(0xFF, 0xF0, 0xF6)
            card.line.color.rgb = color
            card.line.width = Pt(2)
            hdr = slide.shapes.add_textbox(Inches(x + 0.15), Inches(card_top + 0.12), Inches(w - 0.3), Inches(0.55))
            hp = hdr.text_frame.paragraphs[0]
            hp.text = label
            hp.font.name = FONT_UI
            hp.font.size = Pt(26)
            hp.font.bold = True
            hp.font.color.rgb = color
            body_h = min(card_h - 0.65, max(0.45, fit.block_height + 0.12))
            body = slide.shapes.add_textbox(
                Inches(x + 0.15),
                Inches(card_top + 0.55),
                Inches(w - 0.3),
                Inches(body_h),
            )
            _configure_text_frame(body.text_frame)
            tf = body.text_frame
            for j, line in enumerate(items[:4]):
                if line.startswith("★"):
                    continue
                para = tf.paragraphs[0] if j == 0 else tf.add_paragraph()
                para.text = line.replace("核心句 P：", "P · ").replace("拓展 E：", "E · ")
                para.font.name = FONT_ESSAY if "I'd" in line or "The cracked" in line else FONT_UI
                essay = "I'd" in line or "The cracked" in line
                para.font.size = Pt(fit.font_pt if essay else fit.font_pt)
                para.font.color.rgb = INK
                para.space_after = Pt(5)
                para.line_spacing = fit.line_spacing

    def essay_slide(self, title: str, essay_text: str, annotation: str, *, badge: str | None = None) -> None:
        from scripts.essay_format import (
            essay_layout_for_length,
            prepare_classroom_essay_display,
        )

        slide = self._blank()
        top = self._header(slide, title, section="范文")

        if "Dear " in essay_text or "中文批注" in essay_text:
            paragraphs, ann_text = prepare_classroom_essay_display(
                essay_text,
                annotation_fallback=annotation or "",
            )
        else:
            paragraphs = [p.strip() for p in essay_text.split("\n\n") if p.strip()]
            ann_text = (annotation or "").strip()
        body_for_layout = [
            re.sub(r"\s*Word count:\s*\d+\s*$", "", p, flags=re.IGNORECASE).strip()
            for p in paragraphs
        ]
        line_spacing, para_space_pt, indent_spaces = essay_layout_for_length(body_for_layout)

        ann_h = 0.0
        ann_fit = None
        if ann_text:
            ann_fit = fit_typography(
                ann_text,
                float(CONTENT_W.inches) - 0.2,
                2.5,
                max_pt=26,
                min_pt=26,
            )
            ann_h = max(0.72, ann_fit.block_height + 0.16)

        content_top = top + 0.08
        content_h = BOTTOM_Y - content_top - ann_h - 0.06
        text_w = float(CONTENT_W.inches) - 0.2
        body_fit = fit_paragraphs(
            body_for_layout,
            text_w,
            content_h,
            space_after_pt=6 if line_spacing >= 1.0 else 4,
            max_pt=28,
            min_pt=26,
            min_spacing=0.9,
            pad_h_pt=10,
            pad_v_pt=6,
        )
        font_pt = body_fit.font_pt
        line_spacing = body_fit.line_spacing
        text_box_h = min(content_h, max(1.2, body_fit.block_height + 0.18))
        essay_top = content_top + max(0.0, (content_h - text_box_h) * 0.18)

        panel = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            MARGIN_L,
            Inches(essay_top - 0.06),
            CONTENT_W,
            Inches(text_box_h + 0.12),
        )
        panel.fill.solid()
        panel.fill.fore_color.rgb = PANEL_SKY
        panel.line.color.rgb = BORDER
        panel.line.width = Pt(1)

        box = slide.shapes.add_textbox(
            MARGIN_L,
            Inches(essay_top),
            CONTENT_W,
            Inches(text_box_h),
        )
        _configure_text_frame(box.text_frame, anchor=MSO_ANCHOR.TOP, pad_h=10, pad_v=6)
        tf = box.text_frame
        first = True
        for pi, block in enumerate(paragraphs):
            para = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            para.text = (" " * indent_spaces) + block.strip()
            para.font.name = FONT_ESSAY
            para.font.size = Pt(font_pt)
            para.font.color.rgb = INK
            para.line_spacing = line_spacing
            para.space_after = Pt(4)
            if pi > 0:
                para.space_before = Pt(para_space_pt if line_spacing >= 1.0 else 4)

        if ann_text:
            note = slide.shapes.add_textbox(
                MARGIN_L,
                Inches(essay_top + text_box_h + 0.08),
                CONTENT_W,
                Inches(ann_h - 0.04),
            )
            _configure_text_frame(note.text_frame, anchor=MSO_ANCHOR.TOP, pad_h=6, pad_v=4)
            np = note.text_frame.paragraphs[0]
            np.text = ann_text
            np.font.name = FONT_UI
            np.font.size = Pt(ann_fit.font_pt if ann_fit else 26)
            np.font.color.rgb = MUTED
            np.line_spacing = ann_fit.line_spacing if ann_fit else 0.9

    def table_slide(self, title: str, headers: list[str], rows: list[list[str]]) -> None:
        slide = self._blank()
        top = self._header(slide, title, section="范文")
        n_cols = len(headers)
        col_fracs = [1.0 / n_cols] * n_cols
        kinds: list[str] = ["secondary"] * n_cols
        if n_cols:
            kinds[0] = "label"
        budget = LAYOUT_REGISTRY["content_cards"]
        max_table_h = BOTTOM_Y - top - 0.15
        per_row = min(0.72, max_table_h / max(len(rows) + 1, 1))
        row_heights = [0.56]
        row_fonts: list[list[int]] = [[26] * n_cols]
        row_spacings: list[list[float]] = [[1.12] * n_cols]
        for row in rows:
            rh, fpts, sps, _ = fit_table_rows(
                row, col_fracs, kinds, budget, per_row_budget=per_row, max_row_cap=per_row + 0.08
            )
            row_heights.append(rh)
            row_fonts.append(fpts)
            row_spacings.append(sps)
        total_h = sum(row_heights)
        if total_h > max_table_h:
            per_row = (max_table_h - 0.56) / max(len(rows), 1)
            row_heights = [0.56]
            for row in rows:
                rh, fpts, sps, _ = fit_table_rows(
                    row,
                    col_fracs,
                    kinds,
                    budget,
                    per_row_budget=max(0.38, per_row - 0.12),
                    max_row_cap=per_row,
                )
                row_heights.append(max(rh, 0.44))
            total_h = sum(row_heights)
        table_shape = slide.shapes.add_table(
            len(row_heights), n_cols, MARGIN_L, Inches(top + 0.12), CONTENT_W, Inches(total_h)
        )
        table = table_shape.table
        for ri, h in enumerate(row_heights):
            table.rows[ri].height = Inches(h)
        col_colors = [INDIGO, MUTED, CORAL, VIOLET]
        for c, h in enumerate(headers):
            cell = table.cell(0, c)
            cell.text = h
            cell.fill.solid()
            cell.fill.fore_color.rgb = col_colors[c % len(col_colors)]
            _configure_text_frame(cell.text_frame, anchor=MSO_ANCHOR.MIDDLE)
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT_UI
                p.font.size = FONT_TABLE
                p.font.bold = True
                p.font.color.rgb = WHITE
        for r, row in enumerate(rows, start=1):
            rh = row_heights[r]
            max_bh = 0.42
            for c, val in enumerate(row):
                col_w = float(CONTENT_W.inches) * col_fracs[c]
                kind = kinds[c]
                max_pt = budget.max_primary_pt if kind == "primary" else budget.max_secondary_pt
                if kind == "label":
                    max_pt = 26
                cell_fit = fit_typography(
                    val,
                    max(1.0, col_w - 0.12),
                    max(0.28, rh - 0.18),
                    min_pt=budget.min_pt,
                    max_pt=max_pt,
                )
                max_bh = max(max_bh, cell_fit.block_height)
                cell = table.cell(r, c)
                cell.text = val
                _configure_text_frame(cell.text_frame, anchor=MSO_ANCHOR.MIDDLE)
                for p in cell.text_frame.paragraphs:
                    p.font.name = FONT_UI
                    p.font.size = Pt(cell_fit.font_pt)
                    p.font.color.rgb = INK if c == 0 else MUTED
                    p.line_spacing = cell_fit.line_spacing
                    if c > 0:
                        p.font.bold = False
                if r % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = PANEL_SKY
            row_heights[r] = max(rh, max_bh + 0.24)
            table.rows[r].height = Inches(row_heights[r])
        table_shape.height = Inches(sum(row_heights))

    def _key_banner(self, slide, top: float, text: str, *, label: str = "抓重点") -> float:
        budget = LAYOUT_REGISTRY["phrase_table_footer"]
        banner_fit = fit_banner(text, budget)
        h = max(0.88, banner_fit.block_height + 0.18)
        banner = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            MARGIN_L,
            Inches(top),
            CONTENT_W,
            Inches(h),
        )
        banner.fill.solid()
        banner.fill.fore_color.rgb = AMBER
        banner.line.fill.background()
        lbl = slide.shapes.add_textbox(MARGIN_L + Inches(0.15), Inches(top + 0.08), Inches(1.5), Inches(0.48))
        lp = lbl.text_frame.paragraphs[0]
        lp.text = label
        lp.font.name = FONT_UI
        lp.font.size = Pt(26)
        lp.font.bold = True
        lp.font.color.rgb = INK
        body = slide.shapes.add_textbox(
            MARGIN_L + Inches(1.55), Inches(top + 0.1), Inches(10.1), Inches(h - 0.16)
        )
        _configure_text_frame(body.text_frame)
        bp = body.text_frame.paragraphs[0]
        bp.text = text.replace("💡", "").strip()
        bp.font.name = FONT_UI
        bp.font.size = Pt(banner_fit.font_pt)
        bp.font.color.rgb = INK
        bp.line_spacing = banner_fit.line_spacing
        return top + h + 0.1

    def _style_table_header(self, table, headers: list[str]) -> None:
        for c, h in enumerate(headers):
            cell = table.cell(0, c)
            cell.text = h
            cell.fill.solid()
            cell.fill.fore_color.rgb = INDIGO
            _configure_text_frame(cell.text_frame, anchor=MSO_ANCHOR.MIDDLE)
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT_UI
                p.font.size = FONT_TABLE
                p.font.bold = True
                p.font.color.rgb = WHITE

    def _style_phrase_row(
        self,
        table,
        row_idx: int,
        level: str,
        english: str,
        note: str,
        font_pts: list[int] | None = None,
        line_spacings: list[float] | None = None,
    ) -> None:
        accent = _tier_color(level)
        vals = [level, english, note]
        sizes = font_pts or [26, 28, 26]
        spacings = line_spacings or [1.12, 1.12, 1.12]
        for c, val in enumerate(vals):
            cell = table.cell(row_idx, c)
            cell.text = val
            anchor = MSO_ANCHOR.MIDDLE if c == 0 else MSO_ANCHOR.TOP
            _configure_text_frame(cell.text_frame, anchor=anchor)
            pt = sizes[c] if c < len(sizes) else 26
            sp = spacings[c] if c < len(spacings) else 1.12
            for p in cell.text_frame.paragraphs:
                if c == 0:
                    p.font.name = FONT_UI
                    p.font.bold = True
                    p.font.color.rgb = WHITE
                elif c == 1:
                    p.font.name = FONT_ESSAY
                    p.font.bold = True
                    p.font.color.rgb = INK
                else:
                    p.font.name = FONT_UI
                    p.font.color.rgb = MUTED
                p.font.size = Pt(pt)
                p.line_spacing = sp
            if c == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = accent
            elif row_idx % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = PANEL_SKY

    def _render_peel_point_body(
        self,
        slide,
        *,
        x: float,
        card_top: float,
        card_w: float,
        body_h: float,
        point: dict,
        color: RGBColor,
        body_fit,
    ) -> None:
        body = slide.shapes.add_textbox(
            Inches(x + 0.15),
            Inches(card_top + 0.55),
            Inches(card_w - 0.3),
            Inches(body_h),
        )
        _configure_text_frame(body.text_frame, pad_h=4, pad_v=4)
        tf = body.text_frame
        first = True
        norm = normalize_peel_point(point)

        def add_line(tag: str, text: str, *, essay: bool = False, accent: RGBColor = INK) -> None:
            nonlocal first
            if not text:
                return
            para = tf.paragraphs[0] if first else tf.add_paragraph()
            first = False
            run_tag = para.add_run()
            run_tag.text = f"{tag}  "
            run_tag.font.name = FONT_UI
            run_tag.font.size = Pt(26)
            run_tag.font.bold = True
            run_tag.font.color.rgb = color
            run_body = para.add_run()
            run_body.text = text
            run_body.font.name = FONT_ESSAY if essay else FONT_UI
            run_body.font.size = Pt(body_fit.font_pt)
            run_body.font.color.rgb = accent
            para.space_after = Pt(4 if body_fit.line_spacing < 1.0 else 6)
            para.line_spacing = body_fit.line_spacing

        add_line("P", norm["p"], essay=True, accent=INK)
        for ei, e_text in enumerate(norm["e_items"]):
            add_line(
                "E" if ei == 0 else "  ",
                e_text,
                essay="'" in e_text or "I'd" in e_text,
            )
        add_line("L", norm["l"], essay=True, accent=MINT)

    def _peel_card(
        self,
        slide,
        *,
        x: float,
        card_top: float,
        card_w: float,
        card_h: float,
        label: str,
        point: dict,
        color: RGBColor,
        fill: RGBColor,
        body_fit,
    ) -> None:
        card = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
            Inches(x),
            Inches(card_top),
            Inches(card_w),
            Inches(card_h),
        )
        card.fill.solid()
        card.fill.fore_color.rgb = fill
        card.line.color.rgb = color
        card.line.width = Pt(2)

        hdr = slide.shapes.add_textbox(
            Inches(x + 0.15), Inches(card_top + 0.1), Inches(card_w - 0.3), Inches(0.45)
        )
        hp = hdr.text_frame.paragraphs[0]
        hp.text = label
        hp.font.name = FONT_UI
        hp.font.size = Pt(26)
        hp.font.bold = True
        hp.font.color.rgb = color

        body_h = min(card_h - 0.62, max(0.55, body_fit.block_height + 0.14))
        self._render_peel_point_body(
            slide,
            x=x,
            card_top=card_top,
            card_w=card_w,
            body_h=body_h,
            point=point,
            color=color,
            body_fit=body_fit,
        )

    def peel_slide(self, title: str, points: list[dict], *, layout: str = "dual") -> None:
        points = [normalize_peel_point(p) for p in points[:2]]
        if not points:
            return
        if layout == "single" or len(points) == 1:
            slide = self._blank()
            top = self._header(slide, title, section="范文")
            card_top = top + 0.08
            avail_h = BOTTOM_Y - card_top - 0.1
            card_w = CONTENT_W.inches if hasattr(CONTENT_W, "inches") else 12.0
            body_max = avail_h - 0.62
            body_fit = fit_peel_point(points[0], card_w, body_max)
            card_h = min(avail_h, max(body_fit.block_height + 0.82, 1.35))
            body_h = min(card_h - 0.62, max(0.55, body_fit.block_height + 0.14))
            if card_h < avail_h * 0.72:
                card_top = card_top + (avail_h - card_h) * 0.35
            self._peel_card(
                slide,
                x=0.55,
                card_top=card_top,
                card_w=card_w,
                card_h=card_h,
                label="① 先选" if "1" in points[0].get("label", "1") else "② 再讲理由",
                point=points[0],
                color=INDIGO if "1" in points[0].get("label", "1") else CORAL,
                fill=PANEL_LILAC if "1" in points[0].get("label", "1") else RGBColor(0xFF, 0xF0, 0xF6),
                body_fit=body_fit,
            )
            return

        slide = self._blank()
        top = self._header(slide, title, section="范文")
        card_top = top + 0.08
        avail_h = BOTTOM_Y - card_top - 0.1
        card_w = PEEL_CARD_WIDTH
        body_max = avail_h - 0.62
        fits = [fit_peel_point(p, card_w, body_max) for p in points]
        card_h = min(avail_h, max(f.block_height for f in fits) + 0.82)
        if card_h < avail_h * 0.72:
            card_top = card_top + (avail_h - card_h) * 0.35
        labels = ("① 先选", "② 再讲理由")
        colors = (INDIGO, CORAL)
        fills = (PANEL_LILAC, RGBColor(0xFF, 0xF0, 0xF6))
        for idx, point in enumerate(points):
            x = 0.55 + idx * (card_w + 0.25)
            self._peel_card(
                slide,
                x=x,
                card_top=card_top,
                card_w=card_w,
                card_h=card_h,
                label=labels[idx],
                point=point,
                color=colors[idx],
                fill=fills[idx],
                body_fit=fits[idx],
            )

    def phrase_table_slide(
        self,
        title: str,
        table: dict,
        *,
        badge: str | None = None,
        part: str = "full",
    ) -> None:
        """part: body | footer | footer_note | footer_fix | full."""
        if part in ("full", "body"):
            self._phrase_table_body_slide(title, table, badge=badge)
        if part in ("full", "footer", "footer_note", "footer_fix", "footer_fix_bad", "footer_fix_good"):
            if part == "full" and not (
                table.get("topic_note") or table.get("fix_bad") or table.get("fix_good")
            ):
                return
            footer_title = (
                title
                if part.startswith("footer")
                else f"{title.split('·')[0].strip()} · 用法与改错"
            )
            self._phrase_table_footer_slide(
                footer_title,
                table,
                part=part if part.startswith("footer") else "footer",
            )

    def _phrase_table_body_slide(
        self, title: str, table: dict, *, badge: str | None = None
    ) -> None:
        slide = self._blank()
        top = self._header(slide, title, section="句型")
        if "·" in title and "用法" not in title:
            skill = title.split("·", 1)[-1].strip()
            self._pill(
                slide,
                skill,
                left=MARGIN_L,
                top=Inches(top + 0.04),
                width=Inches(min(8.0, 0.22 * len(skill) + 1.6)),
                height=Inches(0.52),
                fill=MINT,
                text_color=INK,
            )
            top += 0.58
        if badge:
            self._pill(
                slide,
                badge,
                left=MARGIN_L + Inches(4.5),
                top=Inches(top - 0.54),
                width=Inches(min(7.0, 0.18 * len(badge) + 2.0)),
                height=Inches(0.52),
                fill=SKY,
                text_color=INK,
            )

        col_fracs = [0.14, 0.52, 0.34]
        tiers = table.get("tiers", [])
        content_top = top + 0.06
        budget = LAYOUT_REGISTRY["phrase_table_body"]
        row_heights, row_fonts, row_spacings, _ = phrase_table_body_heights(tiers, col_fracs, budget)
        row_data: list[tuple[str, str, str]] = []
        for tier in tiers:
            row_data.append(
                (tier.get("level", ""), tier.get("english", ""), _phrase_tier_note(tier))
            )

        tbl_shape = slide.shapes.add_table(
            len(row_heights), 3, MARGIN_L, Inches(content_top), CONTENT_W, Inches(sum(row_heights))
        )
        tbl = tbl_shape.table
        for i, frac in enumerate(col_fracs):
            tbl.columns[i].width = Inches(CONTENT_W.inches * frac)
        for ri, h in enumerate(row_heights):
            tbl.rows[ri].height = Inches(h)
        self._style_table_header(tbl, ["层级", "背这句", "怎么用"])
        for ri, (level, english, note) in enumerate(row_data, start=1):
            rh = row_heights[ri]
            fpts = row_fonts[ri] if ri < len(row_fonts) else [26, 28, 26]
            fsps = row_spacings[ri] if ri < len(row_spacings) else [1.12, 1.12, 1.12]
            kinds_fit: list[str] = ["label", "primary", "secondary"]
            vals = [level, english, note]
            final_pts: list[int] = []
            final_sps: list[float] = []
            max_bh = 0.42
            for c, (val, frac, kind) in enumerate(zip(vals, col_fracs, kinds_fit, strict=True)):
                col_w = float(CONTENT_W.inches) * frac
                max_pt = budget.max_primary_pt if kind == "primary" else budget.max_secondary_pt
                if kind == "label":
                    max_pt = 26
                cell_fit = fit_typography(
                    val,
                    max(1.0, col_w - 0.12),
                    max(0.3, rh - 0.16),
                    min_pt=budget.min_pt,
                    max_pt=max_pt,
                )
                final_pts.append(cell_fit.font_pt)
                final_sps.append(cell_fit.line_spacing)
                max_bh = max(max_bh, cell_fit.block_height)
            row_heights[ri] = max(rh, max_bh + 0.24)
            tbl.rows[ri].height = Inches(row_heights[ri])
            self._style_phrase_row(
                tbl, ri, level, english, note, font_pts=final_pts, line_spacings=final_sps
            )
        tbl_shape.height = Inches(sum(row_heights))
        self._tag_anim(tbl_shape)

    def _phrase_table_footer_slide(self, title: str, table: dict, *, part: str = "footer") -> None:
        slide = self._blank()
        top = self._header(slide, title, section="句型")
        cursor = top + 0.12
        budget = LAYOUT_REGISTRY["phrase_table_footer"]
        show_note = part in ("footer", "footer_note") and table.get("topic_note")
        show_fix = part in ("footer", "footer_fix", "footer_fix_bad", "footer_fix_good") and (
            table.get("fix_bad") or table.get("fix_good")
        )
        if show_note:
            cursor = self._key_banner(slide, cursor, table["topic_note"], label="本题")
            for sh in slide.shapes:
                if sh.has_text_frame and table["topic_note"][:12] in (sh.text_frame.text or ""):
                    self._tag_anim(sh)
                    break

        if not show_fix:
            return

        col_w = 5.85
        y = cursor + 0.08
        avail_h = BOTTOM_Y - y - 0.12
        left_text = ("别这样写\n" + table.get("fix_bad", "")).strip() if table.get("fix_bad") else ""
        right_text = (
            ("改成\n" + table.get("fix_good", "").lstrip("→").strip()).strip()
            if table.get("fix_good")
            else ""
        )
        if part == "footer_fix_bad":
            left_text = left_text or ""
            right_text = ""
        elif part == "footer_fix_good":
            left_text = ""
            right_text = right_text or ""

        layout = fit_fix_cards(
            left_text,
            right_text,
            avail_height=avail_h,
            card_width=col_w,
            full_width=float(CONTENT_W.inches),
            budget=budget,
        )

        def _draw_fix_card(
            x: float,
            card_y: float,
            card_w: float,
            card_h: float,
            text: str,
            fit,
            *,
            fill: RGBColor,
            border: RGBColor,
            text_color: RGBColor,
            bold: bool = False,
        ) -> None:
            card = slide.shapes.add_shape(
                MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE,
                Inches(x),
                Inches(card_y),
                Inches(card_w),
                Inches(card_h),
            )
            card.fill.solid()
            card.fill.fore_color.rgb = fill
            card.line.color.rgb = border
            card.line.width = Pt(2)
            box = slide.shapes.add_textbox(
                Inches(x + 0.15),
                Inches(card_y + 0.12),
                Inches(card_w - 0.3),
                Inches(max(0.3, card_h - 0.2)),
            )
            _configure_text_frame(box.text_frame)
            bp = box.text_frame.paragraphs[0]
            bp.text = text
            bp.font.name = FONT_ESSAY
            bp.font.size = Pt(fit.font_pt)
            bp.font.bold = bold
            bp.font.color.rgb = text_color
            bp.line_spacing = fit.line_spacing
            self._tag_anim(box)

        if layout.mode == "stack":
            cy = y
            if left_text and layout.left and right_text and layout.right:
                stack_h = (avail_h - 0.08) / 2
                _draw_fix_card(
                    float(MARGIN_L.inches),
                    cy,
                    float(CONTENT_W.inches),
                    stack_h,
                    left_text,
                    layout.left,
                    fill=PANEL_WARN,
                    border=WARN,
                    text_color=WARN,
                )
                cy += stack_h + 0.08
                _draw_fix_card(
                    float(MARGIN_L.inches),
                    cy,
                    float(CONTENT_W.inches),
                    stack_h,
                    right_text,
                    layout.right,
                    fill=PANEL_MINT,
                    border=MINT,
                    text_color=INK,
                    bold=True,
                )
            elif left_text and layout.left:
                card_h = layout.card_height
                cy = y + max(0.0, (avail_h - card_h) * 0.2)
                _draw_fix_card(
                    float(MARGIN_L.inches),
                    cy,
                    float(CONTENT_W.inches),
                    card_h,
                    left_text,
                    layout.left,
                    fill=PANEL_WARN,
                    border=WARN,
                    text_color=WARN,
                )
            elif right_text and layout.right:
                card_h = layout.card_height
                cy = y + max(0.0, (avail_h - card_h) * 0.2)
                _draw_fix_card(
                    float(MARGIN_L.inches),
                    cy,
                    float(CONTENT_W.inches),
                    card_h,
                    right_text,
                    layout.right,
                    fill=PANEL_MINT,
                    border=MINT,
                    text_color=INK,
                    bold=True,
                )
        else:
            fix_h = layout.card_height
            if left_text and layout.left:
                _draw_fix_card(
                    float(MARGIN_L.inches),
                    y,
                    col_w,
                    fix_h,
                    left_text,
                    layout.left,
                    fill=PANEL_WARN,
                    border=WARN,
                    text_color=WARN,
                )
            if right_text and layout.right:
                x2 = MARGIN_L.inches + col_w + 0.25
                _draw_fix_card(
                    x2,
                    y,
                    col_w,
                    fix_h,
                    right_text,
                    layout.right,
                    fill=PANEL_MINT,
                    border=MINT,
                    text_color=INK,
                    bold=True,
                )

    def vocab_table_slide(
        self,
        title: str,
        tier: str,
        rows: list[dict],
        columns: list[str],
        *,
        badge: str | None = None,
    ) -> None:
        slide = self._blank()
        top = self._header(slide, title, section="句型")
        accent = _tier_color(tier)
        tier_short = tier.replace("级", "")
        self._pill(
            slide,
            tier_short,
            left=MARGIN_L,
            top=Inches(top + 0.04),
            width=Inches(1.35),
            height=Inches(0.52),
            fill=accent,
        )
        hint = "只背英文 + 例句" if len(columns) == 2 else "词块 + 释义 + 例句"
        self._pill(
            slide,
            hint,
            left=MARGIN_L + Inches(1.5),
            top=Inches(top + 0.04),
            width=Inches(min(10.0, 0.22 * len(hint) + 1.8)),
            height=Inches(0.52),
            fill=PANEL_SKY,
            text_color=INK,
        )
        top += 0.58

        header_map = {"english": "词块", "chinese": "释义", "example": "例句"}
        headers = [header_map[c] for c in columns]
        n_cols = len(columns)
        col_fracs = [0.38, 0.62] if n_cols == 2 else [0.26, 0.20, 0.54]

        content_top = top + 0.06
        budget = LAYOUT_REGISTRY["vocab_table"]
        row_heights, row_fonts, row_spacings, _ = fit_vocab_chunk(rows, columns, budget)
        row_values: list[list[str]] = [[row.get(c, "") for c in columns] for row in rows]

        tbl_shape = slide.shapes.add_table(
            len(row_heights), n_cols, MARGIN_L, Inches(content_top), CONTENT_W, Inches(sum(row_heights))
        )
        tbl = tbl_shape.table
        for i, frac in enumerate(col_fracs):
            tbl.columns[i].width = Inches(CONTENT_W.inches * frac)
        for ri, h in enumerate(row_heights):
            tbl.rows[ri].height = Inches(h)
        self._style_table_header(tbl, headers)
        for ri, vals in enumerate(row_values, start=1):
            rh = row_heights[ri]
            max_bh = 0.42
            for c, val in enumerate(vals):
                col_w = float(CONTENT_W.inches) * col_fracs[c]
                kind: str = "primary" if columns[c] in ("english", "example") else "secondary"
                max_pt = budget.max_primary_pt if kind == "primary" else budget.max_secondary_pt
                cell_fit = fit_typography(
                    val,
                    max(1.5, col_w - 0.12),
                    max(0.3, rh - 0.16),
                    min_pt=budget.min_pt,
                    max_pt=max_pt,
                )
                max_bh = max(max_bh, cell_fit.block_height)
                cell = tbl.cell(ri, c)
                cell.text = val
                _configure_text_frame(cell.text_frame, anchor=MSO_ANCHOR.TOP)
                pt = cell_fit.font_pt
                sp = cell_fit.line_spacing
                for p in cell.text_frame.paragraphs:
                    p.font.size = Pt(pt)
                    p.line_spacing = sp
                    if columns[c] == "english":
                        p.font.name = FONT_ESSAY
                        p.font.bold = True
                        p.font.color.rgb = INK
                    elif columns[c] == "example":
                        p.font.name = FONT_ESSAY
                        p.font.color.rgb = INK
                    else:
                        p.font.name = FONT_UI
                        p.font.color.rgb = MUTED
                if ri % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = PANEL_SKY
            row_heights[ri] = max(rh, max_bh + 0.24)
            tbl.rows[ri].height = Inches(row_heights[ri])
        tbl_shape.height = Inches(sum(row_heights))
        self._tag_anim(tbl_shape)


def render_v2_deck(slides: list[dict], output: Path) -> Path:
    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H
    builder = SlideBuilderV2(prs)
    for spec in slides:
        kind = spec["type"]
        if kind == "title":
            builder.title_slide(spec["title"], spec["subtitle"], spec["body"])
        elif kind == "roadmap":
            pass  # roadmap slides disabled
        elif kind == "divider":
            builder.divider_slide(spec["num"], spec["name"], spec["subtitle"], spec["color"])
        elif kind == "essay":
            builder.essay_slide(
                spec["title"],
                spec["essay_text"],
                spec.get("annotation", ""),
                badge=spec.get("badge"),
            )
        elif kind == "table":
            builder.table_slide(spec["title"], spec["headers"], spec["rows"])
        elif kind == "peel":
            builder.peel_slide(
                spec["title"],
                spec["points"],
                layout=spec.get("layout", "dual"),
            )
        elif kind == "phrase_table":
            builder.phrase_table_slide(
                spec["title"],
                spec["table"],
                badge=spec.get("badge"),
                part=spec.get("part", "full"),
            )
        elif kind == "vocab_table":
            builder.vocab_table_slide(
                spec["title"],
                spec.get("tier", ""),
                spec["rows"],
                spec["columns"],
                badge=spec.get("badge"),
            )
        else:
            builder.content_slide(
                spec["title"],
                spec["bullets"],
                badge=spec.get("badge"),
                panel=spec.get("panel", False),
                warn_panel=spec.get("warn_panel", False),
            )
    output.parent.mkdir(parents=True, exist_ok=True)
    _enforce_word_wrap(prs)
    _clean_pptx_dir(output)
    prs.save(output)
    return output


def build_v2_deck_with_stage3(
    stage3_path: Path,
    deck_plan_path: Path | None = None,
    *,
    vocab_max_rows: int = 6,
) -> list[dict]:
    base = build_deck_with_stage3(
        stage3_path, deck_plan_path, vocab_max_rows=vocab_max_rows
    )
    return _inject_v2_structure(base)


def render_v2_classroom(
    slides: list[dict],
    output: Path,
) -> Path:
    return render_v2_deck(slides, output)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Generate 应用文 classroom PPTX V2")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_V2_OUT)
    parser.add_argument("--stage3", type=Path, default=None)
    parser.add_argument("--deck-plan", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.stage3 and args.stage3.is_file():
        slides = build_v2_deck_with_stage3(
            args.stage3.expanduser().resolve(),
            args.deck_plan.expanduser().resolve() if args.deck_plan else None,
        )
    else:
        slides = _inject_v2_structure(expand_slide_specs(build_mental_health_deck()))
    path = render_v2_deck(slides, args.output)
    prs = Presentation(path)
    seen, violations = _collect_font_sizes(prs)
    overflow = verify_text_fit(prs)
    page_nums = _find_page_numbers(prs)

    print(f"V2 Saved: {path}")
    print(f"Slides: {len(prs.slides)}")
    print(f"Fonts: {sorted(seen)} min={min(seen) if seen else '?'}")
    print(f"Overflow: {'pass' if not overflow else overflow[:3]}")
    print(f"Page nums: {'none' if not page_nums else page_nums}")
    ok = not violations and not overflow and not page_nums
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
