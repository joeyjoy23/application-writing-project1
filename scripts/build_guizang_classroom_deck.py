"""Build guizang magazine-style classroom HTML deck (ink-classic + Motion One).

Reuses Architecture V1 slide specs from build_classroom_html_deck, injects
<section> pages into guizang template.html at <!-- SLIDES_HERE -->.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_classroom_html_deck import (  # noqa: E402
    _peel_point_lines,
    build_slide_specs,
)

GUIZANG_SKILL = Path.home() / ".agents/skills/guizang-ppt-skill"
DEFAULT_TEMPLATE = GUIZANG_SKILL / "assets/template.html"
MOTION_SRC = GUIZANG_SKILL / "assets/motion.min.js"
SLIDES_MARKER = "<!-- SLIDES_HERE -->"
MAX_PIPELINE_STEPS = 5
MAX_TABLE_ROWS = 8


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _trim(text: str, n: int = 100) -> str:
    s = re.sub(r"\s+", " ", text.strip())
    return s[: n - 1] + "…" if len(s) > n else s


def _chrome_column(slide: dict[str, Any]) -> str:
    tag = slide.get("tag") or "课堂"
    title = slide.get("title") or ""
    if title.startswith("导入"):
        return "导入 · Warm-up"
    if tag == "Stage 1" or title.startswith("审题") or title.startswith("思维"):
        return "Stage 1 · 审题思维"
    if tag == "Stage 2" or "范文" in title or "PEEL" in title or "三版" in title:
        return "Stage 2 · 范文拆解"
    if tag == "Stage 3" or "句型" in title or "词块" in title:
        return "Stage 3 · 语言积累"
    if tag == "Stage 4" or "易错" in title or "迁移" in title or "讲评" in title:
        return "Stage 4 · 训练迁移"
    if tag == "总结":
        return "总结 · Takeaway"
    return "应用文 · Classroom"


def _kicker_for(slide: dict[str, Any]) -> str:
    title = slide.get("title") or "本页"
    if slide.get("badge"):
        return slide["badge"]
    if slide.get("tier"):
        return slide["tier"]
    parts = title.split(" · ", 1)
    return parts[-1] if len(parts) > 1 else title


def _plan_themes(specs: list[dict[str, Any]]) -> list[str]:
    """Assign guizang theme classes with breathing rhythm (no 3× same)."""
    themes: list[str] = []
    prev = ""
    prev2 = ""
    for i, spec in enumerate(specs):
        if i == 0 or spec.get("variant") == "hero":
            t = "hero dark"
        elif spec.get("warn_panel"):
            t = "dark"
        elif "三版" in (spec.get("title") or ""):
            t = "light"
        elif spec.get("essay"):
            t = "dark" if prev in ("light", "hero light") else "light"
        elif (spec.get("table_rows") or spec.get("phrase_body")) and prev != "light":
            t = "light"
        else:
            t = "dark" if prev in ("light", "hero light") else "light"
        if t == prev == prev2 and t in ("light", "dark"):
            t = "hero light" if t == "light" else "hero dark"
        themes.append(t)
        prev2, prev = prev, t.split()[-1] if " " in t else t
    if len(themes) >= 8 and "hero light" not in themes:
        themes[min(4, len(themes) - 1)] = "hero light"
    return themes


def _chrome_block(slide: dict[str, Any], index: int, total: int) -> str:
    col = _chrome_column(slide)
    return (
        f'<div class="chrome"><div>{_esc(col)}</div>'
        f"<div>{index + 1} / {total}</div></div>"
    )


def _foot_block(slide: dict[str, Any], index: int) -> str:
    title = _esc(slide.get("title") or "")
    return (
        f'<div class="foot"><div class="title">{title}</div>'
        f'<div>P.{index + 1:02d}</div></div>'
    )


def _pipeline_steps(items: list[tuple[str, str]], *, max_steps: int = MAX_PIPELINE_STEPS) -> str:
    parts = ['<div class="pipeline-section"><div class="pipeline" style="grid-template-columns:1fr">']
    for j, (title, desc) in enumerate(items[:max_steps]):
        parts.append(
            f'<div class="step" data-anim="step" style="text-align:left">'
            f'<div class="step-nb">{j + 1:02d}</div>'
            f'<div class="step-title">{_esc(_trim(title, 48))}</div>'
            f'<div class="step-desc">{_esc(_trim(desc, 220))}</div>'
            "</div>"
        )
    parts.append("</div></div>")
    return "\n".join(parts)


def _render_cover(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or "课堂课件"
    subtitle = slide.get("subtitle") or ""
    bullets = slide.get("bullets") or []
    body = "<br>".join(_esc(b) for b in bullets[:4])
    return f"""
<section class="slide {theme}" data-animate="hero">
{_chrome_block(slide, index, total)}
<div class="frame" style="display:grid;gap:5vh;align-content:center;min-height:78vh">
  <div class="kicker" data-anim>高考英语 · 应用文课堂</div>
  <h1 class="display-zh" data-anim>{_esc(title)}</h1>
  {f'<p class="lead" style="max-width:62vw" data-anim>{_esc(subtitle)}</p>' if subtitle else ''}
  {f'<p class="body-serif" style="max-width:58vw;opacity:.82" data-anim>{body}</p>' if body else ''}
</div>
{_foot_block(slide, index)}
</section>"""


def _render_content(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or ""
    kicker = _kicker_for(slide)
    bullets = slide.get("bullets") or []
    items = [(b, "") for b in bullets]
    warn = slide.get("warn_panel")
    callout = ""
    if warn and bullets:
        callout = (
            f'<div class="callout" data-anim="step" style="margin-top:4vh">'
            f"{_esc(bullets[0])}</div>"
        )
        items = [(b, "") for b in bullets[1:]]
    pipeline = _pipeline_steps(items) if items else ""
    anim = "pipeline" if items else "cascade"
    return f"""
<section class="slide {theme}" data-animate="{anim}">
{_chrome_block(slide, index, total)}
<div class="frame" style="padding-top:4vh">
  <div class="kicker" data-anim>{_esc(kicker)}</div>
  <h2 class="h-xl" data-anim>{_esc(title)}</h2>
  {callout}
  {pipeline}
</div>
{_foot_block(slide, index)}
</section>"""


def _render_peel(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or "PEEL"
    peel = slide.get("peel") or []
    items: list[tuple[str, str]] = []
    for pt in peel:
        label = pt.get("label") or "Point"
        lines = _peel_point_lines(pt)
        items.append((label, " · ".join(lines[:3])))
    return f"""
<section class="slide {theme}" data-animate="pipeline">
{_chrome_block(slide, index, total)}
<div class="frame" style="padding-top:4vh">
  <div class="kicker" data-anim>PEEL · 写作骨架</div>
  <h2 class="h-xl" data-anim>{_esc(title)}</h2>
  {_pipeline_steps(items)}
</div>
{_foot_block(slide, index)}
</section>"""


def _render_essay(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or "范文"
    essay = slide.get("essay") or ""
    paras = [p.strip() for p in essay.split("\n\n") if p.strip()]
    if not paras:
        paras = [essay] if essay else ["（见备课包范文）"]
    lines_html = "".join(
        f'<p class="body-serif en" data-anim="line" style="margin-bottom:2.2vh;line-height:1.72">'
        f"{_esc(p)}</p>"
        for p in paras[:8]
    )
    note = slide.get("annotation") or ""
    return f"""
<section class="slide {theme}" data-animate="quote">
{_chrome_block(slide, index, total)}
<div class="frame" style="padding-top:3vh">
  <div class="kicker" data-anim>Model Essay</div>
  <h2 class="h1-zh" data-anim>{_esc(title)}</h2>
  <div style="margin-top:3vh;max-width:88vw">{lines_html}</div>
  {f'<p class="meta-row" data-anim>{_esc(note)}</p>' if note else ''}
</div>
{_foot_block(slide, index)}
</section>"""


def _render_table(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or "对比表"
    headers = slide.get("table_headers") or []
    rows = slide.get("table_rows") or []
    row_items = []
    for row in rows[:MAX_TABLE_ROWS]:
        dim = str(row[0]) if row else ""
        rest = " · ".join(str(c) for c in row[1:4]) if len(row) > 1 else ""
        row_items.append((dim, rest))
    extra = ""
    if len(rows) > MAX_TABLE_ROWS:
        extra = (
            f'<p class="meta-row" data-anim>… 共 {len(rows)} 行，'
            f"其余见 speaker notes</p>"
        )
    return f"""
<section class="slide {theme}" data-animate="pipeline">
{_chrome_block(slide, index, total)}
<div class="frame" style="padding-top:3vh">
  <div class="kicker" data-anim>{_esc(" · ".join(str(h) for h in headers[:2]))}</div>
  <h2 class="h-xl" data-anim>{_esc(title)}</h2>
  {_pipeline_steps(row_items, max_steps=MAX_TABLE_ROWS)}
  {extra}
</div>
{_foot_block(slide, index)}
</section>"""


def _render_phrase_table(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or "功能句型"
    rows = slide.get("phrase_body") or []
    items = []
    for row in rows[:MAX_PIPELINE_STEPS]:
        tier = row.get("tier") or ""
        en = row.get("en") or ""
        zh = row.get("zh") or row.get("note") or ""
        items.append((tier or "句型", f"{en} — {zh}".strip(" —")))
    return f"""
<section class="slide {theme}" data-animate="pipeline">
{_chrome_block(slide, index, total)}
<div class="frame" style="padding-top:3vh">
  <div class="kicker" data-anim>Stage 3 · Phrases</div>
  <h2 class="h1-zh" data-anim>{_esc(title)}</h2>
  {_pipeline_steps(items)}
</div>
{_foot_block(slide, index)}
</section>"""


def _render_fix(slide: dict[str, Any], index: int, total: int, theme: str) -> str:
    title = slide.get("title") or "改错"
    bad = slide.get("fix_bad") or ""
    good = slide.get("fix_good") or ""
    return f"""
<section class="slide {theme}" data-animate="directional">
{_chrome_block(slide, index, total)}
<div class="frame grid-2-6-6" style="padding-top:5vh;gap:4vw">
  <div data-anim="left" style="padding:2vh 1vw;border-left:3px solid currentColor;opacity:.65">
    <div class="kicker">别这样写</div>
    <p class="body-serif en">{_esc(bad)}</p>
  </div>
  <div data-anim="right" style="padding:2vh 1vw;border-left:3px solid currentColor">
    <div class="kicker">可以这样写</div>
    <p class="body-serif en">{_esc(good)}</p>
  </div>
</div>
<div class="foot"><div class="title">{_esc(title)}</div><div>P.{index + 1:02d}</div></div>
</section>"""


def render_guizang_slide(
    slide: dict[str, Any], index: int, total: int, theme: str
) -> str:
    if index == 0 or slide.get("variant") == "hero":
        return _render_cover(slide, index, total, theme)
    if slide.get("peel"):
        return _render_peel(slide, index, total, theme)
    if slide.get("essay"):
        return _render_essay(slide, index, total, theme)
    if slide.get("phrase_body"):
        return _render_phrase_table(slide, index, total, theme)
    if slide.get("table_headers") and slide.get("table_rows"):
        return _render_table(slide, index, total, theme)
    if slide.get("fix_bad") or slide.get("fix_good"):
        return _render_fix(slide, index, total, theme)
    return _render_content(slide, index, total, theme)


def render_guizang_html(
    specs: list[dict[str, Any]],
    *,
    deck_title: str,
    template_text: str,
) -> str:
    if SLIDES_MARKER not in template_text:
        raise ValueError(f"template missing {SLIDES_MARKER}")
    themes = _plan_themes(specs)
    total = len(specs)
    slides_html = "\n".join(
        render_guizang_slide(spec, i, total, themes[i]) for i, spec in enumerate(specs)
    )
    out = template_text.replace(
        "<title>[必填] 替换为 PPT 标题 · Deck Title</title>",
        f"<title>{_esc(deck_title)}</title>",
    )
    return out.replace(SLIDES_MARKER, slides_html)


def write_guizang_deck(
    specs: list[dict[str, Any]],
    out_dir: Path,
    *,
    deck_title: str,
    template_path: Path = DEFAULT_TEMPLATE,
) -> Path:
    if not template_path.is_file():
        raise FileNotFoundError(f"guizang template not found: {template_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = out_dir / "assets"
    assets.mkdir(exist_ok=True)
    if MOTION_SRC.is_file():
        shutil.copy2(MOTION_SRC, assets / "motion.min.js")
    html_path = out_dir / "index.html"
    template_text = template_path.read_text(encoding="utf-8")
    html_path.write_text(
        render_guizang_html(specs, deck_title=deck_title, template_text=template_text),
        encoding="utf-8",
    )
    return html_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Build guizang magazine classroom HTML deck")
    ap.add_argument(
        "--export",
        type=Path,
        default=Path(r"D:\Downloads\ppt-work\2026-06-14-deepseek\export-data.json"),
    )
    ap.add_argument(
        "--stage3",
        type=Path,
        default=Path(r"D:\Downloads\ppt-work\2026-06-14-deepseek\stage3.json"),
    )
    ap.add_argument("--preset", choices=("40min", "70min", "80min"), default="80min")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=Path(r"D:\Downloads\ppt-work\2026-06-14-deepseek\humanize-run\guizang-deck"),
    )
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    args = ap.parse_args()

    data = json.loads(args.export.read_text(encoding="utf-8"))
    specs = build_slide_specs(
        data,
        stage3_path=args.stage3 if args.stage3.is_file() else None,
        preset=args.preset,
    )
    title = specs[0].get("title") if specs else "课堂课件"
    path = write_guizang_deck(
        specs,
        args.out_dir,
        deck_title=title,
        template_path=args.template,
    )
    print(f"Wrote {len(specs)} guizang slides -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
