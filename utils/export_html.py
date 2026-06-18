"""将应用文备课四阶段结果导出为独立 HTML 页面（排版贴近网页展示）。"""

from __future__ import annotations

import html as html_module
from datetime import datetime

import markdown

from utils.datetime_util import format_created_at_display, display_tz
from utils.export_word import STAGE_TITLES
_EXPORT_CSS = """
:root {
  --font-base: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif;
  --c-ink: #1e293b;
  --c-ink-muted: #64748b;
  --c-primary: #2563eb;
  --c-paper: #f8fafc;
  --c-card: #ffffff;
  --c-border: #e2e8f0;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 2rem 1.25rem 3rem;
  font-family: var(--font-base);
  font-size: 15px;
  line-height: 1.65;
  color: var(--c-ink);
  background: var(--c-paper);
}
.wrap { max-width: 920px; margin: 0 auto; }
.doc-title {
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--c-primary);
  margin: 0 0 0.35rem;
}
.doc-meta { color: var(--c-ink-muted); font-size: 0.9rem; margin-bottom: 1.75rem; }
.section {
  background: var(--c-card);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 1.1rem 1.25rem 1.25rem;
  margin-bottom: 1.25rem;
}
.section h2 {
  margin: 0 0 0.85rem;
  font-size: 1.05rem;
  color: var(--c-primary);
  border-bottom: 1px solid var(--c-border);
  padding-bottom: 0.45rem;
}
.section-body h1, .section-body h2, .section-body h3, .section-body h4 {
  color: var(--c-primary);
  margin: 1.1rem 0 0.5rem;
  line-height: 1.35;
}
.section-body h5, .section-body h6 { margin: 0.85rem 0 0.4rem; }
.section-body p { margin: 0.5rem 0; }
.section-body ul, .section-body ol { margin: 0.45rem 0 0.65rem 1.35rem; }
.section-body li { margin: 0.2rem 0; }
.section-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.75rem 0;
  font-size: 0.92rem;
}
.section-body th, .section-body td {
  border: 1px solid var(--c-border);
  padding: 0.45rem 0.55rem;
  vertical-align: top;
}
.section-body th { background: #f1f5f9; }
.section-body code {
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.9em;
  background: #f1f5f9;
  padding: 0.1em 0.35em;
  border-radius: 4px;
}
.section-body pre {
  background: #f1f5f9;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  overflow-x: auto;
  font-size: 0.88rem;
}
.section-body pre code { background: none; padding: 0; }
.muted { color: var(--c-ink-muted); }
.qtype { margin: 0.35rem 0 0; font-weight: 600; color: #336699; }
.doc-footer {
  margin-top: 2rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--c-border);
  text-align: right;
  color: var(--c-ink-muted);
  font-size: 0.82rem;
}
.doc-footer strong { color: var(--c-ink); letter-spacing: 0.06em; }
@media print {
  body { background: #fff; padding: 0.5rem; }
  .section { break-inside: avoid; box-shadow: none; }
}
"""


def _html_report_time_line(saved_at_utc: str | None) -> str:
    if saved_at_utc:
        shown = format_created_at_display(saved_at_utc)
        dt = datetime.strptime(shown, "%Y-%m-%d %H:%M:%S")
    else:
        dt = datetime.now(display_tz()).replace(tzinfo=None)
    return f"生成时间：{dt.strftime('%Y年%m月%d日 %H:%M')}（北京时间）"


def _format_body_markdown(stage: int, raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return ""
    from ui.stage_display import _format_stage_body

    return _format_stage_body(str(raw).strip(), stage=stage)


def _markdown_fragment_to_html(md: str) -> str:
    if not md.strip():
        return '<p class="muted">（暂无内容）</p>'
    return markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
        output_format="html5",
    )


def _section_html(title: str, body_html: str) -> str:
    return (
        f'<section class="section">'
        f"<h2>{html_module.escape(title)}</h2>"
        f'<div class="section-body">{body_html}</div>'
        f"</section>"
    )


def export_workflow_to_html(
    *,
    question: str,
    stage1_summary: str | None = None,
    stage2_raw: str | None = None,
    stage3_raw: str | None = None,
    stage4_raw: str | None = None,
    saved_at_utc: str | None = None,
    question_type_label: str | None = None,
) -> bytes:
    """生成 UTF-8 HTML 文件字节流。"""
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>高考英语应用文备课分析报告</title>",
        f"<style>{_EXPORT_CSS}</style>",
        "</head>",
        "<body>",
        '<div class="wrap">',
        '<h1 class="doc-title">高考英语应用文备课分析报告</h1>',
        f'<p class="doc-meta">{html_module.escape(_html_report_time_line(saved_at_utc))}</p>',
    ]

    q_text = (question or "").strip() or "（未填写）"
    q_html = f"<p>{html_module.escape(q_text).replace(chr(10), '<br>')}</p>"
    parts.append(_section_html("题目原文", q_html))

    if question_type_label:
        parts.append(
            f'<p class="qtype">题目类型：{html_module.escape(question_type_label)}</p>'
        )

    stage_payloads = [
        (1, stage1_summary),
        (2, stage2_raw),
        (3, stage3_raw),
        (4, stage4_raw),
    ]
    for stage_num, raw in stage_payloads:
        if not raw or not str(raw).strip():
            continue
        md = _format_body_markdown(stage_num, str(raw).strip())
        body_html = _markdown_fragment_to_html(md)
        parts.append(_section_html(STAGE_TITLES[stage_num], body_html))

    parts.extend(
        [
            '<footer class="doc-footer"><strong>Joyverse</strong></footer>',
            "</div>",
            "</body>",
            "</html>",
        ]
    )
    return "\n".join(parts).encode("utf-8")
