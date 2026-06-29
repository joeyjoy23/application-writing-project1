#!/usr/bin/env python
"""DEPRECATED: Use scripts/build_ppt_stage3_svg.py instead.

Generate ppt-master vocab-table slide SVGs (17/18/19) from V1 deck data.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

FONT_BODY = 38
FONT_TITLE = 51
X0 = 48
Y_START = 140
LINE_DY = 52

DEFAULT_PROJECT = Path(
    r"C:\Users\Joey\tools\ppt-master\projects\yingyongwen-mental-health-v3_ppt169_20260620"
)

VOCAB_OUTPUTS = (
    "17_vocab_opinion.svg",
    "18_vocab_design.svg",
    "19_vocab_theme.svg",
)


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def build_vocab_svg(title: str, bullets: list[str]) -> str:
    if len(bullets) < 4:
        raise ValueError(f"vocab slide needs 4 bullets (必备/进阶/亮点/例句), got {len(bullets)}")
    reveal_parts: list[str] = []
    for i, bullet in enumerate(bullets[:4]):
        y = Y_START + i * LINE_DY
        reveal_parts.append(
            f'  <g id="reveal-{i + 1:02d}">\n'
            f'    <text x="{X0}" y="{y}" font-family="Microsoft YaHei, Arial, sans-serif" '
            f'font-size="{FONT_BODY}" fill="#1E293B">{_esc(bullet)}</text>\n'
            f"  </g>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" '
        'width="1280" height="720">\n'
        '  <rect width="1280" height="720" fill="#FFFFFF" />\n'
        '  <g id="header">\n'
        '    <rect x="0" y="0" width="1280" height="76" fill="#6366F1" />\n'
        '    <rect x="0" y="76" width="1280" height="4" fill="#14B8A6" />\n'
        f'    <text x="{X0}" y="52" font-family="Microsoft YaHei, Arial, sans-serif" '
        f'font-size="{FONT_TITLE}" font-weight="bold" fill="#FFFFFF">{_esc(title)}</text>\n'
        "  </g>\n"
        f"{chr(10).join(reveal_parts)}\n"
        "</svg>\n"
    )


def vocab_specs_from_deck() -> list[dict]:
    from scripts.generate_classroom_pptx import build_mental_health_deck

    slides = [
        s
        for s in build_mental_health_deck()
        if s.get("type") == "content" and "话题词块" in s.get("title", "")
    ]
    if len(slides) != 3:
        raise RuntimeError(f"expected 3 vocab slides in deck, got {len(slides)}")
    return slides


def write_vocab_svgs(project_dir: Path) -> list[Path]:
    out_dir = project_dir / "svg_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = vocab_specs_from_deck()
    written: list[Path] = []
    for filename, spec in zip(VOCAB_OUTPUTS, specs, strict=True):
        svg = build_vocab_svg(spec["title"], spec["bullets"])
        path = out_dir / filename
        path.write_text(svg, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build vocab-table SVG slides for ppt-master")
    parser.add_argument(
        "--project",
        type=Path,
        default=DEFAULT_PROJECT,
        help="ppt-master project directory",
    )
    args = parser.parse_args(argv)
    paths = write_vocab_svgs(args.project)
    for p in paths:
        print(f"Wrote: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
