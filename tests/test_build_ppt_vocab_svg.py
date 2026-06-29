"""Tests for build_ppt_vocab_svg."""

from __future__ import annotations

import re

from scripts.build_ppt_vocab_svg import build_vocab_svg, vocab_specs_from_deck, write_vocab_svgs


def test_vocab_specs_have_four_tier_bullets():
    for spec in vocab_specs_from_deck():
        assert len(spec["bullets"]) >= 4
        joined = " ".join(spec["bullets"])
        assert "必备" in joined
        assert "进阶" in joined
        assert "亮点" in joined
        assert "例句" in joined


def test_design_vocab_lists_all_tiers_separately():
    spec = next(s for s in vocab_specs_from_deck() if "设计元素" in s["title"])
    svg = build_vocab_svg(spec["title"], spec["bullets"])
    assert "watering can" in svg
    assert "heart-shaped leaves" in svg
    assert "symbolic representation" in svg
    assert "必备 / 进阶 / 亮点" not in svg
    assert len(re.findall(r'id="reveal-\d+"', svg)) == 4


def test_write_vocab_svgs_to_tmp(tmp_path):
    written = write_vocab_svgs(tmp_path)
    assert len(written) == 3
    design = (tmp_path / "svg_output" / "18_vocab_design.svg").read_text(encoding="utf-8")
    assert "watering can" in design
