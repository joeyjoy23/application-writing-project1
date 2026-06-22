"""Integration test: classroom_to_deck student content."""

import json
from pathlib import Path

from scripts.deck_from_classroom import classroom_to_deck
from scripts.parse_classroom_html import parse_classroom_html
from scripts.prepare_ppt_source import parse_export_html


def test_classroom_deck_stage4_no_teacher_guidance_on_slides():
    export_path = Path(r"d:/Downloads/应用文分析_2026-06-18_glm-4.6v.html")
    classroom_path = Path(r"d:/Downloads/应用文分析_2026-06-18_glm-4.6v-课件.html")
    if not export_path.is_file() or not classroom_path.is_file():
        return

    export_data = parse_export_html(export_path)
    classroom = parse_classroom_html(classroom_path)
    deck = classroom_to_deck(classroom, export_data, stage3_specs=[])

    joined = json.dumps(deck, ensure_ascii=False)
    assert "教师操作" not in joined
    assert "教师引导" not in joined
    assert "引导：用 Stage 3" not in joined

    activity = next(s for s in deck if "练一练" in s.get("title", ""))
    assert activity.get("badge") == "当堂操练"
    assert not any("10′" in b or "15′" in b for b in activity.get("bullets", []))

    warn = next(s for s in deck if "易错" in s.get("title", "") or s.get("badge") == "动笔易错")
    assert not any("引导" in b for b in warn.get("bullets", []))

    assert any("思维" in s.get("title", "") for s in deck)
