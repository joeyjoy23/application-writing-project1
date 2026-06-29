#!/usr/bin/env python
"""Generate ppt-master Stage 3 SVG slides from stage3.json (phrase + vocab)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.stage3_svg_layout import (  # noqa: E402
    render_phrase_fix_svg,
    render_phrase_tiers_svg,
    render_vocab_table_svg,
    split_rows,
)

PHRASE_BASE_FILES = (
    "14_phrases_opinion",
    "15_phrases_evidence",
    "16_phrases_logic",
)

DEFAULT_PROJECT = Path(
    r"C:\Users\Joey\tools\ppt-master\projects\yingyongwen-mental-health-v3_ppt169_20260620"
)

_VOCAB_SLUGS = ("opinion", "design", "theme")
_TIER_SLUGS = ("basic", "advanced", "highlight")
_TIER_LABELS = ("必备级", "进阶级", "亮点级")

# After expanding Stage 3, tail slides renumber 20-22 → 26-28
TAIL_RENAMES = {
    "20_transfer.svg": "26_transfer.svg",
    "21_error_deepening.svg": "27_error_deepening.svg",
    "22_summary.svg": "28_summary.svg",
}

OLD_VOCAB_FILES = (
    "17_vocab_opinion.svg",
    "18_vocab_design.svg",
    "19_vocab_theme.svg",
)


def _short_field_name(name: str) -> str:
    if "观点" in name:
        return "观点表达"
    if "设计" in name:
        return "设计元素"
    if "健康" in name or "主题" in name:
        return "心理健康主题"
    return name[:12]


def build_stage3_slide_specs(data: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []

    for base, table in zip(PHRASE_BASE_FILES, data.get("phrase_tables", []), strict=True):
        specs.append(
            {
                "filename": f"{base}.svg",
                "title": f"功能句型 · {table['name']}",
                "kind": "phrase_tiers",
                "table": table,
            }
        )
        specs.append(
            {
                "filename": f"{base}_fix.svg",
                "title": f"功能句型 · {table['name']} · 本题与改一句",
                "kind": "phrase_fix",
                "table": table,
            }
        )

    vocab_idx = 0
    for field in data.get("vocab_fields", []):
        slug = _VOCAB_SLUGS[vocab_idx] if vocab_idx < len(_VOCAB_SLUGS) else f"f{vocab_idx}"
        short = _short_field_name(field["name"])
        for ti, tier in enumerate(field.get("tiers", [])):
            tier_slug = _TIER_SLUGS[ti] if ti < len(_TIER_SLUGS) else f"t{ti}"
            chunks = split_rows(tier.get("rows", []), max_rows=6)
            for ci, chunk in enumerate(chunks):
                num = 17 + vocab_idx * 3 + ti
                suffix = ""
                if len(chunks) > 1:
                    suffix = f" {ci + 1}/{len(chunks)}"
                specs.append(
                    {
                        "filename": f"{num:02d}_vocab_{slug}_{tier_slug}.svg",
                        "title": f"话题词块 · {short} · {tier['level']}{suffix}",
                        "kind": "vocab",
                        "tier": tier["level"],
                        "rows": chunk,
                    }
                )
        vocab_idx += 1

    return specs


def render_slide_spec(spec: dict[str, Any]) -> str:
    if spec["kind"] == "phrase_tiers":
        return render_phrase_tiers_svg(spec["title"], spec["table"])
    if spec["kind"] == "phrase_fix":
        return render_phrase_fix_svg(spec["title"], spec["table"])
    show_chinese = spec["tier"] != "必备级"
    return render_vocab_table_svg(
        spec["title"],
        spec["tier"],
        spec["rows"],
        show_chinese=show_chinese,
    )


def renumber_tail_slides(out_dir: Path) -> None:
    """Move slides 20-22 to 26-28 when Stage 3 expands to 17-25."""
    for old, new in TAIL_RENAMES.items():
        src = out_dir / old
        dst = out_dir / new
        if src.exists() and not dst.exists():
            src.rename(dst)


def cleanup_old_vocab(out_dir: Path) -> None:
    for name in OLD_VOCAB_FILES:
        p = out_dir / name
        if p.exists():
            p.unlink()


def write_stage3_svgs(project_dir: Path, stage3_json: Path) -> list[Path]:
    data = json.loads(stage3_json.read_text(encoding="utf-8"))
    specs = build_stage3_slide_specs(data)
    out_dir = project_dir / "svg_output"
    out_dir.mkdir(parents=True, exist_ok=True)
    cleanup_old_vocab(out_dir)
    written: list[Path] = []
    for spec in specs:
        svg = render_slide_spec(spec)
        path = out_dir / spec["filename"]
        path.write_text(svg, encoding="utf-8")
        written.append(path)
    renumber_tail_slides(out_dir)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Stage 3 SVG slides for ppt-master")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument(
        "--stage3-json",
        type=Path,
        default=None,
        help="stage3.json path (default: project sources or ppt-work)",
    )
    args = parser.parse_args(argv)
    json_path = args.stage3_json
    if json_path is None:
        for candidate in (
            args.project / "sources" / "stage3.json",
            Path(r"d:\Downloads\ppt-work\stage3.json"),
        ):
            if candidate.exists():
                json_path = candidate
                break
    if json_path is None or not json_path.exists():
        print("Error: stage3.json not found; run prepare_ppt_source or pass --stage3-json")
        return 1
    paths = write_stage3_svgs(args.project, json_path)
    for p in paths:
        print(f"Wrote: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
