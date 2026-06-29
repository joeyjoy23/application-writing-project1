"""Classroom PPT design tokens — Modern Education SaaS (mint + white + gray)."""

from __future__ import annotations

from pptx.dml.color import RGBColor


class ColorToken:
    """Canonical hex values (single source of truth)."""

    PRIMARY = "#A8DADC"
    PRIMARY_DARK = "#7BC7C4"
    BG = "#FFFFFF"
    ZONE_SURFACE = "#F7FAF9"
    SURFACE = "#FFFFFF"
    BORDER = "#E5E7EB"
    TEXT_TITLE = "#1F2937"
    TEXT_BODY = "#374151"
    TEXT_SECONDARY = "#6B7280"
    WARNING = "#F59E0B"
    # Legacy aliases — mapped to SaaS palette
    TEXT_PRIMARY = TEXT_TITLE
    TEXT_MUTED = TEXT_SECONDARY
    ACCENT = PRIMARY
    SECONDARY = PRIMARY_DARK
    HIGHLIGHT_BG = ZONE_SURFACE
    TAG_BG = ZONE_SURFACE
    SUCCESS = PRIMARY_DARK
    DANGER = WARNING


def hex_to_rgb(value: str) -> RGBColor:
    clean = value.lstrip("#")
    return RGBColor(int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


class Theme:
    """PPTX-ready semantic colors — mint primary, amber warning only."""

    PRIMARY = hex_to_rgb(ColorToken.PRIMARY)
    PRIMARY_DARK = hex_to_rgb(ColorToken.PRIMARY_DARK)
    BG = hex_to_rgb(ColorToken.BG)
    ZONE_SURFACE = hex_to_rgb(ColorToken.ZONE_SURFACE)
    SURFACE = hex_to_rgb(ColorToken.SURFACE)
    BORDER = hex_to_rgb(ColorToken.BORDER)
    TEXT_TITLE = hex_to_rgb(ColorToken.TEXT_TITLE)
    TEXT_BODY = hex_to_rgb(ColorToken.TEXT_BODY)
    TEXT_SECONDARY = hex_to_rgb(ColorToken.TEXT_SECONDARY)
    WARNING = hex_to_rgb(ColorToken.WARNING)

    TEXT_PRIMARY = TEXT_TITLE
    TEXT_MUTED = TEXT_SECONDARY
    ACCENT = PRIMARY
    SECONDARY = PRIMARY_DARK
    SUCCESS = PRIMARY_DARK
    DANGER = WARNING
    HIGHLIGHT_BG = ZONE_SURFACE
    TAG_BG = ZONE_SURFACE

    INK = TEXT_BODY
    MUTED = TEXT_SECONDARY
    WHITE = SURFACE
    ERROR = WARNING

    PANEL_DEFAULT = SURFACE
    PANEL_HIGHLIGHT = ZONE_SURFACE
    PANEL_ALT = ZONE_SURFACE
    PANEL_WARN = SURFACE

    ACCENT_LINE = PRIMARY
    DIVIDER_ACCENT = PRIMARY_DARK

    COVER_TITLE = TEXT_TITLE
    COVER_SUBTITLE = TEXT_SECONDARY
    COVER_BG = BG

    CARD_BG = SURFACE
    CARD_BORDER = BORDER

    PEEL_EMPHASIS = PRIMARY_DARK
    PEEL_ALT = PRIMARY
    PEEL_WARNING = WARNING
    PEEL_ERROR = WARNING

    TABLE_HEADER = TEXT_TITLE
    TABLE_HEADER_BG = ZONE_SURFACE
    TABLE_CELL = TEXT_BODY
    TABLE_GRID = BORDER

    PILL_BG = ZONE_SURFACE
    PILL_TEXT = TEXT_SECONDARY
    PILL_BORDER = BORDER

    FIX_GOOD_BORDER = BORDER
    FIX_BAD_BORDER = WARNING
    FIX_BAD_TEXT = TEXT_BODY

    SECTION_COLORS: dict[str, RGBColor] = {
        "审题": TEXT_SECONDARY,
        "范文": TEXT_SECONDARY,
        "句型": TEXT_SECONDARY,
        "词汇": TEXT_SECONDARY,
        "活动": TEXT_SECONDARY,
        "迁移": TEXT_SECONDARY,
        "小结": TEXT_SECONDARY,
        "路线": TEXT_SECONDARY,
    }

    TIER_FILL: dict[str, RGBColor] = {
        "基础": SURFACE,
        "必备": SURFACE,
        "进阶": SURFACE,
        "高级": SURFACE,
        "亮点": SURFACE,
    }

    TIER_TEXT: dict[str, RGBColor] = {
        "基础": TEXT_SECONDARY,
        "必备": TEXT_SECONDARY,
        "进阶": TEXT_BODY,
        "高级": TEXT_BODY,
        "亮点": TEXT_BODY,
    }

    @classmethod
    def tier_style(cls, label: str) -> tuple[RGBColor, RGBColor]:
        for key in cls.TIER_FILL:
            if key in label:
                return cls.TIER_FILL[key], cls.TIER_TEXT[key]
        return cls.SURFACE, cls.TEXT_SECONDARY

    @classmethod
    def bullet_accent(cls, text: str) -> RGBColor:
        raw = text.lstrip("• ").strip()
        if raw.startswith("❌") or "别这样写" in raw:
            return cls.WARNING
        if raw.startswith("★") or raw.startswith("✅"):
            return cls.PRIMARY_DARK
        if raw.startswith("→") or raw.strip() == "↓":
            return cls.TEXT_SECONDARY
        return cls.TEXT_BODY

    @classmethod
    def peel_pair(cls) -> tuple[tuple[RGBColor, RGBColor], tuple[RGBColor, RGBColor]]:
        return (cls.PRIMARY_DARK, cls.SURFACE), (cls.PRIMARY, cls.SURFACE)

    @classmethod
    def card_accent(cls, *, warning: bool = False) -> RGBColor:
        return cls.WARNING if warning else cls.PRIMARY
