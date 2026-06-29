"""Design token tests for Modern Education SaaS theme."""

from pptx.dml.color import RGBColor

from styles.design_tokens import ColorToken, Theme, hex_to_rgb


def test_color_token_hex_values():
    assert ColorToken.PRIMARY == "#A8DADC"
    assert ColorToken.PRIMARY_DARK == "#7BC7C4"
    assert ColorToken.BG == "#FFFFFF"
    assert ColorToken.ZONE_SURFACE == "#F7FAF9"
    assert ColorToken.TEXT_TITLE == "#1F2937"
    assert ColorToken.TEXT_BODY == "#374151"
    assert ColorToken.TEXT_SECONDARY == "#6B7280"
    assert ColorToken.WARNING == "#F59E0B"
    assert ColorToken.BORDER == "#E5E7EB"


def test_hex_to_rgb():
    c = hex_to_rgb("#A8DADC")
    assert c == RGBColor(0xA8, 0xDA, 0xDC)


def test_theme_section_colors_neutral():
    assert len(set(Theme.SECTION_COLORS.values())) == 1
    assert Theme.SECTION_COLORS["审题"] == Theme.TEXT_SECONDARY


def test_tier_style_returns_white_surface():
    fill, text = Theme.tier_style("进阶句")
    assert fill == Theme.SURFACE
    assert text == Theme.TEXT_BODY


def test_table_semantic_tokens():
    assert Theme.TABLE_HEADER == Theme.TEXT_TITLE
    assert Theme.TABLE_HEADER_BG == Theme.ZONE_SURFACE
    assert Theme.TABLE_CELL == Theme.TEXT_BODY


def test_warning_only_for_errors():
    assert Theme.bullet_accent("❌ 空泛理由") == Theme.WARNING
    assert Theme.bullet_accent("• 正常要点") == Theme.TEXT_BODY
    assert Theme.card_accent(warning=True) == Theme.WARNING
    assert Theme.card_accent(warning=False) == Theme.PRIMARY
