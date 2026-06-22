"""Application-letter essay layout: three paragraphs + first-line indent."""

from __future__ import annotations

import re
import textwrap

# Closing phrases — last paragraph (套话祝愿，课堂不上屏)
_CLOSING_RE = re.compile(
    r"(?P<closing>"
    r"(?:Anyway,\s*)?"
    r"(?:I hope this helps!?|Hope this helps!?)"
    r"[^.!?]*[.!?]"
    r"(?:\s*You've got great taste[^.!?]*[.!?])?"
    r"(?:\s*Good luck[^.!?]*[.!?])?"
    r")\s*$",
    re.IGNORECASE,
)

# Body starts at explicit choice / recommendation
_CHOICE_RE = re.compile(
    r"(I'd go with|I'd choose|Personally,\s*I'd choose|I recommend)\b",
    re.IGNORECASE,
)

# Substantive third paragraph (升华段，不是 Good luck)
_SUMMARY_START_RE = re.compile(
    r"\b(Overall,|In conclusion,|In summary,|To sum up,|All in all,)\s",
    re.IGNORECASE,
)

_BODY_BREAK_RE = re.compile(
    r"\b(But the smile\?|The text [\"']|However,|Therefore,)\s",
    re.IGNORECASE,
)


def _is_closing_paragraph(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _CLOSING_RE.search(t):
        return True
    lower = t.lower()
    return any(
        phrase in lower
        for phrase in (
            "hope this helps",
            "good luck",
            "best wishes",
            "looking forward",
            "yours sincerely",
            "yours faithfully",
        )
    )


def split_essay_three_paragraphs(text: str) -> tuple[str, list[str]]:
    """Split full letter into salutation + body blocks (may include sign-off)."""
    raw = re.sub(r"\r\n", "\n", text.strip())
    sal_match = re.match(r"(Dear\s+[^,\n]+,)\s*", raw, re.IGNORECASE)
    if not sal_match:
        return ("", [raw])

    salutation = sal_match.group(1)
    rest = raw[sal_match.end() :].strip()
    blocks = [b.strip() for b in re.split(r"\n\s*\n+", rest) if b.strip()]

    if len(blocks) >= 3:
        return (salutation, blocks[:3])
    if len(blocks) == 2:
        opening, tail = blocks
        closing_m = _CLOSING_RE.search(tail)
        if closing_m:
            body = tail[: closing_m.start()].strip()
            closing = closing_m.group("closing").strip()
            if body:
                return (salutation, [opening, body, closing])
        return (salutation, [opening, tail, ""])

    body_text = blocks[0] if blocks else rest
    closing_m = _CLOSING_RE.search(body_text)
    closing = ""
    if closing_m:
        closing = closing_m.group("closing").strip()
        body_text = body_text[: closing_m.start()].strip()

    choice_m = _CHOICE_RE.search(body_text)
    if choice_m:
        opening = body_text[: choice_m.start()].strip()
        main = body_text[choice_m.start() :].strip()
        if opening and main and closing:
            return (salutation, [opening, main, closing])

    return (salutation, [body_text, "", closing])


def _split_middle_at_summary(main: str) -> tuple[str, str] | None:
    m = _SUMMARY_START_RE.search(main)
    if not m:
        return None
    left = main[: m.start()].strip()
    right = main[m.start() :].strip()
    if left and right:
        return left, right
    return None


def _split_middle_at_body_break(main: str) -> tuple[str, str] | None:
    m = _BODY_BREAK_RE.search(main)
    if not m:
        return None
    left = main[: m.start()].strip()
    right = main[m.start() :].strip()
    if left and right:
        return left, right
    return None


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _ensure_three_body_blocks(paragraphs: list[str]) -> list[str]:
    """Exactly 3 classroom paragraphs: 开篇 / 主体 / 升华."""
    paras = [p.strip() for p in paragraphs if p.strip()]
    while paras and _is_closing_paragraph(paras[-1]):
        paras.pop()
    if not paras:
        return []

    if len(paras) >= 3:
        return paras[:3]

    if len(paras) == 2:
        opening, main = paras
        summary_split = _split_middle_at_summary(main)
        if summary_split:
            return [opening, summary_split[0], summary_split[1]]
        body_split = _split_middle_at_body_break(main)
        if body_split:
            return [opening, body_split[0], body_split[1]]
        sents = _split_sentences(main)
        if len(sents) >= 3:
            mid = max(1, len(sents) // 2)
            return [opening, " ".join(sents[:mid]), " ".join(sents[mid:])]
        if len(sents) == 2:
            return [opening, sents[0], sents[1]]
        return [opening, main, ""]

    text = paras[0]
    choice_m = _CHOICE_RE.search(text)
    if choice_m:
        opening = text[: choice_m.start()].strip()
        main = text[choice_m.start() :].strip()
        summary_split = _split_middle_at_summary(main)
        if opening and summary_split:
            return [opening, summary_split[0], summary_split[1]]
        body_split = _split_middle_at_body_break(main)
        if opening and body_split:
            return [opening, body_split[0], body_split[1]]
        sents = _split_sentences(main)
        if opening and len(sents) >= 2:
            mid = max(1, len(sents) // 2)
            return [opening, " ".join(sents[:mid]), " ".join(sents[mid:])]
        if opening:
            return [opening, main, ""]

    sents = _split_sentences(text)
    if len(sents) >= 3:
        n = len(sents)
        a = max(1, n // 3)
        b = max(a + 1, (2 * n) // 3)
        return [" ".join(sents[:a]), " ".join(sents[a:b]), " ".join(sents[b:])]
    return paras


def classroom_body_paragraphs(text: str) -> list[str]:
    """Three body paragraphs for slides: no Dear …, no Good luck sign-off."""
    _sal, paras = split_essay_three_paragraphs(text)
    three = _ensure_three_body_blocks(paras)
    return [p for p in three if p.strip()]


def estimate_display_line_count(
    paragraphs: list[str],
    *,
    chars_per_line: float = 52,
) -> float:
    total = 0.0
    for block in paragraphs:
        n = max(1, int(len(block) / chars_per_line) + block.count("\n"))
        total += n
    return total


def essay_layout_for_length(paragraphs: list[str]) -> tuple[float, int, int]:
    """Return (line_spacing, para_space_before_pt, indent_spaces)."""
    total_chars = sum(len(p) for p in paragraphs)
    est_lines = estimate_display_line_count(paragraphs, chars_per_line=48)
    if total_chars >= 650 or est_lines >= 18:
        return 0.92, 6, 3
    if total_chars >= 450 or est_lines >= 12:
        return 0.98, 8, 4
    return 1.02, 10, 4


def wrap_paragraph_lines(
    paragraph: str,
    *,
    width: int = 58,
    indent_chars: int = 0,
) -> list[str]:
    """Word-wrap one paragraph; first line may include leading indent spaces."""
    if not paragraph.strip():
        return []
    prefix = " " * indent_chars if indent_chars else ""
    wrapped = textwrap.wrap(
        paragraph.strip(),
        width=max(20, width - indent_chars),
        break_long_words=False,
        break_on_hyphens=False,
    )
    if not wrapped:
        return []
    if prefix:
        wrapped[0] = prefix + wrapped[0]
    return wrapped


_WORD_COUNT_RE = re.compile(r"Word count:\s*(\d+)", re.IGNORECASE)
_NEXT_ESSAY_RE = re.compile(r"^\s*\d+\.\s*高分版\s*[AB]", re.MULTILINE | re.IGNORECASE)
_ANNOTATION_SPLIT_RE = re.compile(r"中文批注[：:]\s*", re.IGNORECASE)


def split_essay_source(raw: str) -> tuple[str, int | None, str]:
    """Split raw Stage2 essay block into English letter, word count, Chinese annotation."""
    text = re.sub(r"\r\n", "\n", (raw or "").strip())
    if not text:
        return "", None, ""

    next_m = _NEXT_ESSAY_RE.search(text)
    if next_m:
        text = text[: next_m.start()].strip()

    annotation = ""
    ann_m = _ANNOTATION_SPLIT_RE.search(text)
    if ann_m:
        annotation = text[ann_m.end() :].strip()
        text = text[: ann_m.start()].strip()

    word_count: int | None = None
    wc_m = _WORD_COUNT_RE.search(text)
    if wc_m:
        word_count = int(wc_m.group(1))
        text = text[: wc_m.start()].strip()

    if "Dear " in text:
        text = text[text.find("Dear ") :]
    return text.strip(), word_count, annotation


def count_english_words(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def prepare_classroom_essay_body(raw: str) -> tuple[list[str], int, str]:
    """Return body paragraphs (no salutation/closing), word count, Chinese annotation."""
    english, word_count, embedded_ann = split_essay_source(raw)
    paragraphs = classroom_body_paragraphs(english) if english.strip() else []
    if not paragraphs and english.strip():
        paragraphs = [english.strip()]
    wc = word_count if word_count is not None else count_english_words(" ".join(paragraphs))
    return paragraphs, wc, embedded_ann.strip()


def prepare_classroom_essay_display(
    raw: str,
    *,
    annotation_fallback: str = "",
) -> tuple[list[str], str]:
    """Body paragraphs for classroom slides: no salutation/closing; Word count inline on last para."""
    paragraphs, wc, embedded_ann = prepare_classroom_essay_body(raw)
    annotation = (embedded_ann or annotation_fallback or "").strip()
    if paragraphs:
        last = re.sub(r"\s*Word count:\s*\d+\s*$", "", paragraphs[-1], flags=re.IGNORECASE).rstrip()
        paragraphs[-1] = f"{last}  Word count: {wc}"
    return paragraphs, annotation


def classroom_essay_plain_text(paragraphs: list[str]) -> str:
    return "\n\n".join(paragraphs)
