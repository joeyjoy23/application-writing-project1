"""UI 装饰资源。"""

from pathlib import Path

from utils.ui_assets import (
    LILY_CORNER_FILE,
    LILY_TRANSPARENT_FILE,
    lily_corner_data_uri,
    lily_decor_css,
    lily_hero_data_uri,
    render_hero_block,
)


def test_lily_asset_files_exist():
    assert LILY_TRANSPARENT_FILE.is_file()
    assert LILY_CORNER_FILE.is_file()


def test_lily_data_uris():
    hero = lily_hero_data_uri()
    corner = lily_corner_data_uri()
    assert hero.startswith("data:image/png;base64,")
    assert corner.startswith("data:image/png;base64,")
    assert len(hero) > 1000


def test_lily_decor_css_includes_urls():
    css = lily_decor_css()
    assert "--lily-hero-url" in css
    assert "--lily-corner-url" in css
    assert "--lily-bg-match" in css


def test_render_hero_block():
    html = render_hero_block()
    assert "hero-lily" in html
    assert "高考英语应用文 AI 分析系统" in html
