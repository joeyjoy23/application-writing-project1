"""Tests for scripts/validate_ppt_svg.py"""

from pathlib import Path

from scripts.validate_ppt_svg import validate_svg_file


def test_passes_valid_minimal_svg(tmp_path: Path) -> None:
    svg = tmp_path / "ok.svg"
    svg.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <g id="header">
    <text font-size="51">Title</text>
  </g>
  <text font-size="35">Body line one</text>
</svg>""",
        encoding="utf-8",
    )
    report = validate_svg_file(svg)
    assert report.errors == []


def test_detects_small_font_and_joyverse(tmp_path: Path) -> None:
    svg = tmp_path / "bad.svg"
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg">
  <text font-size="24">Too small</text>
  <text>Joyverse footer</text>
</svg>""",
        encoding="utf-8",
    )
    report = validate_svg_file(svg)
    assert any("font-size" in e for e in report.errors)
    assert any("Joyverse" in e for e in report.errors)


def test_detects_page_number_pattern(tmp_path: Path) -> None:
    svg = tmp_path / "paged.svg"
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg">
  <text font-size="35">Slide 12 / 28</text>
</svg>""",
        encoding="utf-8",
    )
    report = validate_svg_file(svg)
    assert any("page number" in e for e in report.errors)
