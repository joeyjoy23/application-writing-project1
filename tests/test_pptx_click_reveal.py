"""Tests for pptx_click_reveal."""

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pptx import Presentation
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.util import Inches

from scripts.generate_classroom_pptx import SlideBuilder
from scripts.pptx_click_reveal import apply_click_reveal

_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"


def _make_anim_pptx(path: Path) -> None:
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    for i in range(1, 4):
        box = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(1), Inches(i), Inches(3), Inches(0.5)
        )
        box.name = f"anim_{i:03d}"
    prs.save(path)


def test_apply_click_reveal_injects_timing(tmp_path):
    pptx = tmp_path / "test.pptx"
    _make_anim_pptx(pptx)
    ok = apply_click_reveal(pptx)
    assert ok is True
    with zipfile.ZipFile(pptx, "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml")
    root = ET.fromstring(slide_xml)
    timing = root.find(f"{{{_P_NS}}}timing")
    assert timing is not None
    assert b"p:timing" in slide_xml or timing.tag.endswith("timing")


def test_apply_click_reveal_table_shapes(tmp_path):
    pptx = tmp_path / "table_anim.pptx"
    prs = Presentation()
    builder = SlideBuilder(prs)
    builder.vocab_table_slide(
        "话题词块 · 测试",
        "必备级",
        [{"english": "cracked heart", "example": "The cracked heart symbolizes vulnerability."}],
        ["english", "example"],
    )
    prs.save(pptx)
    ok = apply_click_reveal(pptx)
    assert ok is True
    with zipfile.ZipFile(pptx, "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml")
    root = ET.fromstring(slide_xml)
    timing = root.find(f"{{{_P_NS}}}timing")
    assert timing is not None


def test_apply_click_reveal_does_not_hide_shapes(tmp_path):
    pptx = tmp_path / "test.pptx"
    _make_anim_pptx(pptx)
    apply_click_reveal(pptx)
    with zipfile.ZipFile(pptx, "r") as zf:
        slide_xml = zf.read("ppt/slides/slide1.xml")
    root = ET.fromstring(slide_xml)
    hidden = [
        c.get("name")
        for host in root.iter(f"{{{_P_NS}}}sp")
        for c in host.iter(f"{{{_P_NS}}}cNvPr")
        if c.get("hidden") == "1"
    ]
    assert hidden == []


def test_apply_click_reveal_no_anim_shapes(tmp_path):
    pptx = tmp_path / "plain.pptx"
    prs = Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(pptx)
    ok = apply_click_reveal(pptx)
    assert ok is True
