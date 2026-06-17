"""UI 静态装饰资源（百合花等）。"""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from utils.config import get_project_root

LILY_UI_DIR = get_project_root() / "assets" / "ui"
LILY_TRANSPARENT_FILE = LILY_UI_DIR / "lily-transparent.png"
LILY_CORNER_FILE = LILY_UI_DIR / "lily-corner.png"


@lru_cache(maxsize=4)
def _png_data_uri(path_str: str) -> str:
    path = Path(path_str)
    if not path.is_file():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def lily_hero_data_uri() -> str:
    return _png_data_uri(str(LILY_TRANSPARENT_FILE.resolve()))


def lily_corner_data_uri() -> str:
    return _png_data_uri(str(LILY_CORNER_FILE.resolve()))


def lily_decor_css() -> str:
    """注入百合装饰用的 CSS 变量（供 custom.css 引用）。"""
    hero = lily_hero_data_uri()
    corner = lily_corner_data_uri()
    if not hero and not corner:
        return ""
    lines = [
        ":root {",
        "  --lily-bg-match: #f7f0e8;",
    ]
    if hero:
        lines.append(f"  --lily-hero-url: url('{hero}');")
    if corner:
        lines.append(f"  --lily-corner-url: url('{corner}');")
    lines.append("}")
    return "\n".join(lines)


def render_hero_block() -> str:
    """Hero 区 HTML（标题 + 百合装饰位）。"""
    lily_class = "hero-lily" if lily_hero_data_uri() else "hero-lily hero-lily--missing"
    return (
        '<div class="hero-block">'
        '<div class="hero-inner">'
        '<div class="hero-copy">'
        '<div class="hero-title">高考英语应用文 AI 分析系统</div>'
        '<div class="hero-subtitle">四阶段备课工作流 · 审题 · 范文 · 语言 · 教学</div>'
        '<div class="hero-underline"></div>'
        "</div>"
        f'<div class="{lily_class}" role="presentation" aria-hidden="true"></div>'
        "</div>"
        "</div>"
    )
