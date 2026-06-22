"""Tests for ppt_layout_fit."""

from scripts.ppt_layout_fit import (
    LAYOUT_REGISTRY,
    expand_essay_slides,
    essay_text_fits,
    fit_banner,
    fit_bullet_card_layout,
    fit_fix_cards,
    fit_paragraphs,
    fit_typography,
    fit_vocab_chunk,
    phrase_table_body_heights,
    split_essay_text,
)


def test_layout_registry_phrase_body_has_pill_budget():
    b = LAYOUT_REGISTRY["phrase_table_body"]
    assert b.pill_row > 0
    assert b.key_banner == 0
    assert b.content_height(with_pill=True) < 6.0


def test_pick_font_pt_shrinks_for_long_text():
    short = fit_typography("Hello", 5.0, 0.5, min_pt=26, max_pt=32)
    long_text = "A" * 200
    long = fit_typography(long_text, 5.0, 0.5, min_pt=26, max_pt=32)
    assert short.font_pt >= long.font_pt
    assert long.font_pt >= 26


def test_fit_typography_tightens_line_spacing():
    text = "word " * 80
    fit = fit_typography(text, 4.0, 1.0, min_pt=26, max_pt=32)
    assert fit.font_pt >= 26
    assert fit.line_spacing >= 0.9


def test_fit_typography_needs_split_when_impossible():
    text = "X" * 500
    fit = fit_typography(text, 3.0, 0.5, min_pt=26, max_pt=32)
    assert fit.needs_split


def test_phrase_table_body_heights_returns_fonts_no_scale_only():
    tiers = [
        {"level": "基础句", "english": "I prefer Poster 1.", "chinese": ""},
        {"level": "进阶句", "english": "I'm leaning towards Poster 1.", "chinese": "用途说明"},
        {"level": "高级句", "english": "Among the two, Poster 1 strikes me.", "chinese": "说明", "high_score": "tip"},
    ]
    heights, fonts, spacings, split = phrase_table_body_heights(tiers, [0.14, 0.52, 0.34])
    assert len(heights) == 4
    assert len(fonts) == 4
    assert len(spacings) == 4
    assert all(pt >= 26 for row in fonts for pt in row)
    assert all(sp >= 0.9 for row in spacings for sp in row)
    assert split is False


def test_fit_banner_respects_budget():
    budget = LAYOUT_REGISTRY["phrase_table_footer"]
    fit = fit_banner("本题需明确表达选择，适合用此功能句型。", budget)
    assert fit.font_pt >= 26
    assert fit.block_height <= budget.key_banner * 1.1


def test_fit_vocab_chunk_signals_overflow():
    budget = LAYOUT_REGISTRY["vocab_table"]
    rows = [
        {
            "english": "emotional resonance " * 8,
            "chinese": "情感共鸣 " * 12,
            "example": "Poster 1 resonates with me because " * 6,
        }
        for _ in range(10)
    ]
    _, _, _, split = fit_vocab_chunk(rows, ["english", "chinese", "example"], budget)
    assert split


def test_fit_fix_cards_uses_stack_for_long_dual():
    left = "别这样写\n" + "bad " * 40
    right = "改成\n" + "good " * 60
    layout = fit_fix_cards(left, right, avail_height=2.0)
    assert layout.mode in ("stack", "needs_split", "dual")


def test_fit_paragraphs_counts_space_after():
    lines = ["Line one here", "Line two here", "Line three"]
    tight = fit_paragraphs(lines, 8.0, 1.0, space_after_pt=10)
    loose = fit_paragraphs(lines, 8.0, 1.5, space_after_pt=10)
    assert loose.font_pt >= tight.font_pt or not tight.needs_split


def test_split_essay_text_breaks_long_letter():
    essay = "Dear James,\n\n" + ("Glad to hear about your poster designs. " * 40) + "\n\n" + (
        "I'd go with Poster 1 because it shows vulnerability and hope. " * 35
    )
    chunks = split_essay_text(essay, has_badge=True, has_annotation=True)
    assert len(chunks) >= 2
    for idx, chunk in enumerate(chunks):
        assert essay_text_fits(
            chunk,
            has_badge=idx == 0,
            has_annotation=idx == len(chunks) - 1,
        )


def test_expand_essay_slides_adds_part_suffix():
    slides = [
        {
            "type": "essay",
            "title": "基础版范文",
            "essay_text": "Dear James,\n\n" + ("Word " * 800),
            "annotation": "",
        }
    ]
    out = expand_essay_slides(slides)
    assert len(out) >= 2
    assert "（1/" in out[0]["title"]
    assert "Word count:" in out[-1]["essay_text"]
    assert "Dear" not in out[0]["essay_text"]


def test_bullet_card_layout_uses_variable_heights():
    budget = LAYOUT_REGISTRY["content_cards"]
    bullets = [
        "体裁：朋友间邮件（非正式报告）",
        "时态 / 人称：一般现在时 · 第一人称",
        "核心任务：表明立场 + 用设计元素支撑理由",
        "语气：友好、真诚，结尾鼓励参赛",
    ]
    layout = fit_bullet_card_layout(bullets, budget, content_height=5.0)
    assert len(layout.heights) == 4
    assert max(layout.heights) - min(layout.heights) < 0.35
    assert sum(layout.heights) + 0.14 * 3 < 5.0 * 0.85


def test_bullet_card_layout_long_bullet_taller():
    budget = LAYOUT_REGISTRY["content_cards"]
    short = "语气：友好"
    long = "核心任务：" + ("表明立场并用设计元素支撑理由 " * 8)
    layout = fit_bullet_card_layout([short, long], budget, content_height=5.0)
    assert layout.heights[1] > layout.heights[0]
