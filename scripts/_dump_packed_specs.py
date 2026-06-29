#!/usr/bin/env python
from pathlib import Path
import sys

_PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT))

from scripts.one_click_classroom_ppt import _build_v2_slides
from scripts.generate_classroom_pptx_v2 import _inject_v2_structure
from scripts.ppt_layout_fit import pack_slides, expand_title_slides, expand_peel_slides, expand_essay_slides, expand_content_slides

out = Path(r"D:/Downloads/ppt-work")
slides = _build_v2_slides(
    out / "stage3.json",
    None,
    vocab_max_rows=6,
    use_custom_plan=False,
    export_data_path=None,
    preset="70min",
    template_id="dual_poster_opinion",
)
slides = expand_content_slides(
    expand_peel_slides(expand_essay_slides(expand_title_slides(_inject_v2_structure(slides))))
)
packed = pack_slides(slides)
lines = []
for i, s in enumerate(packed, 1):
    part = s.get("part", "")
    bullets_n = len(s.get("bullets") or [])
    tiers_n = len((s.get("table") or {}).get("tiers") or [])
    rows_n = len(s.get("rows") or [])
    lines.append(
        f"{i:2d} {s.get('type','?'):12s} part={str(part):14s} b={bullets_n} tiers={tiers_n} rows={rows_n} | {s.get('title','')}"
    )
Path(r"D:/Downloads/ppt-work/packed-specs.txt").write_text("\n".join(lines), encoding="utf-8")
print("packed", len(packed))
