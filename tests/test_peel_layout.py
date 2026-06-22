"""Tests for PEEL slide layout fit and Stage2 parsing."""

from scripts.architecture_v1 import _peel_from_stage2
from scripts.ppt_layout_fit import (
    expand_peel_slides,
    estimate_peel_dual_body_height,
    fit_peel_point,
    normalize_peel_point,
    peel_dual_needs_split,
    peel_point_body_lines,
)

STAGE2_STRUCTURED = """
### 一、PEEL 写作策略卡

#### ★核心要点 Point 1：选择

##### 核心句（P）

I'd go with Poster 1.

##### 拓展策略（E）

- 具体化：the cracked heart with a smile
- 感受：it immediately caught my eye

##### 连至下一点（L）

Here's why I think so.

#### ★核心要点 Point 2：理由

##### 核心句（P）

The cracked heart with a smile perfectly captures the essence of mental health.

##### 拓展策略（E）

- 裂痕代表挣扎，微笑表明不完美也没关系
- 影响：this combination makes the message relatable and comforting

##### 连至下一点（L）

Overall, Poster 1 feels more authentic and emotionally resonant.

## 1. 基础版（9 分档）

Dear James,
"""


def test_peel_from_stage2_parses_structured_fields():
    points = _peel_from_stage2(STAGE2_STRUCTURED)
    assert len(points) == 2
    assert "Poster 1" in points[0]["p"]
    assert len(points[0]["e_items"]) <= 2
    assert points[0]["l"].startswith("Here's")


def test_normalize_peel_point_caps_e_items():
    point = {
        "p": "P text",
        "e_items": ["e1", "e2", "e3"],
        "l": "L text",
    }
    norm = normalize_peel_point(point)
    assert len(norm["e_items"]) == 2


def test_peel_point_body_lines_match_renderer_prefix():
    lines = peel_point_body_lines({"p": "Hello", "e_items": ["detail"], "l": "Link"})
    assert lines[0].startswith("P  ")
    assert lines[1].startswith("E  ")


def _mental_health_peel_points():
    from scripts.generate_classroom_pptx import build_mental_health_deck

    peel = next(s for s in build_mental_health_deck() if s.get("type") == "peel")
    return peel["points"]


def test_peel_dual_needs_split_on_tight_budget():
    point = _mental_health_peel_points()[0]
    assert fit_peel_point(point, 5.85, 0.9).needs_split


def test_expand_peel_slides_splits_overflow_to_two_pages():
    pts = _mental_health_peel_points()
    slides = [
        {
            "type": "peel",
            "title": "PEEL 写作骨架",
            "points": pts,
        }
    ]
    from scripts import ppt_layout_fit as plf

    orig = plf.peel_dual_needs_split
    plf.peel_dual_needs_split = lambda _pts: True
    try:
        out = plf.expand_peel_slides(slides)
    finally:
        plf.peel_dual_needs_split = orig
    assert len(out) == 2
    assert all(s.get("layout") == "single" for s in out)
    assert "Point 1" in out[0]["title"]


def test_expand_peel_slides_keeps_dual_when_fits():
    pts = _mental_health_peel_points()
    slides = [{"type": "peel", "title": "PEEL 写作骨架", "points": pts}]
    out = expand_peel_slides(slides)
    assert len(out) == 1
    assert out[0].get("layout") == "dual"


def test_fit_peel_point_sizes_to_content_block():
    point = {"p": "Short point.", "e_items": ["One detail."], "l": "Link."}
    fit = fit_peel_point(point, 5.85, 4.5)
    assert fit.font_pt >= 26
    assert fit.block_height < 2.0
    assert not fit.needs_split
