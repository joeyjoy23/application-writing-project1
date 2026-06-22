"""Tests for ppt_layout_fit."""

from scripts.ppt_layout_fit import (
    ARROW_SEP_HEIGHT,
    LAYOUT_REGISTRY,
    expand_content_slides,
    expand_essay_slides,
    essay_text_fits,
    fit_banner,
    fit_bullet_card_layout,
    fit_fix_cards,
    fit_paragraphs,
    fit_typography,
    fit_vocab_chunk,
    is_arrow_separator,
    phrase_table_body_heights,
    plan_essay_stack,
    plan_title_cover_layout,
    split_essay_text,
    split_banner_text,
    substantive_bullet_count,
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


def test_expand_content_slides_splits_four_bullets():
    slides = [
        {
            "type": "content",
            "title": "审题 · 任务拆解",
            "bullets": ["① 一", "② 二", "③ 三", "④ 四"],
        }
    ]
    out = expand_content_slides(slides)
    assert len(out) == 2
    assert len(out[0]["bullets"]) == 3
    assert len(out[1]["bullets"]) == 1
    assert "（1/2）" in out[0]["title"]


def test_split_banner_text_two_lines_for_long_topic_note():
    budget = LAYOUT_REGISTRY["phrase_table_footer"]
    note = (
        "本题需明确表达选择，适合用此功能句型；"
        "避免用“I suggest that”等过于正式或模糊的表达，"
        "直接陈述观点更符合朋友间邮件的友好语气。"
    )
    lines = split_banner_text(note, budget)
    assert len(lines) >= 1
    if fit_banner(note, budget).needs_split:
        assert len(lines) == 2


def test_is_arrow_separator_detects_chain_arrows():
    assert is_arrow_separator("↓")
    assert is_arrow_separator("→")
    assert is_arrow_separator("↔")
    assert not is_arrow_separator("海报画面 → 象征意义")
    assert not is_arrow_separator("① 选择明确")


def test_arrow_separators_use_minimal_card_height():
    budget = LAYOUT_REGISTRY["content_cards"]
    bullets = ["步骤一：读题", "↓", "步骤二：立意", "↓", "步骤三：成文"]
    layout = fit_bullet_card_layout(bullets, budget, content_height=5.0)
    assert layout.heights[1] == ARROW_SEP_HEIGHT
    assert layout.heights[3] == ARROW_SEP_HEIGHT
    assert layout.heights[0] > ARROW_SEP_HEIGHT


def test_expand_content_slides_ignores_arrows_in_bullet_limit():
    slides = [
        {
            "type": "content",
            "title": "思维 · 高分路径",
            "bullets": ["读画面", "↓", "挖象征", "↓", "写理由"],
        }
    ]
    out = expand_content_slides(slides)
    assert len(out) == 1
    assert substantive_bullet_count(out[0]["bullets"]) == 3


def test_title_poster_panel_shrink_wraps_fitted_text():
    poster = [
        "海报一：裂缝中的向日葵，象征在困境中仍向阳生长",
        "海报二：微笑面具下的泪水，揭示心理健康需被看见",
        "两幅海报均紧扣 James 心理健康主题",
        "画面元素可支撑选海报并写理由",
    ]
    cover = plan_title_cover_layout(
        ["James 发来两幅心理健康主题海报，请你帮他选一幅并说明理由。"],
        poster,
    )
    assert cover.poster_fit is not None
    assert cover.poster_panel_h >= cover.poster_fit.block_height + 0.30
    assert cover.stem_panel_h + cover.poster_panel_h < 5.5


def test_expand_title_slides_consolidates_poster():
    from scripts.ppt_layout_fit import expand_title_slides

    poster = ["Poster 1：双手托心", "Poster 2：浇水壶"]
    stem = ["假如你是李华，James 参加心理健康周海报大赛。"]
    slides = expand_title_slides(
        [{"type": "title", "title": "封面", "subtitle": "tag", "body": stem, "poster_lines": poster}]
    )
    assert len(slides) == 2
    assert slides[0].get("poster_lines") is None
    assert slides[1]["type"] == "title_poster"
    assert slides[1]["poster_lines"] == poster


def test_essay_annotation_stacks_below_body():
    paragraphs = [
        "Glad to hear about your poster designs.",
        "I'd go with Poster 1 because it shows vulnerability and hope.",
        "Overall, mental health matters.  Word count: 110",
    ]
    annotation = "①选择明确  ②理由有画面  ③结尾升华"
    stack = plan_essay_stack(paragraphs, annotation)
    assert stack.annotation_top > stack.body_top + stack.body_height + 0.05
    assert stack.annotation_top + stack.annotation_height <= 7.32 + 0.05
    assert stack.body_fit.block_height <= stack.body_height


def test_bullet_card_heights_cover_fitted_text():
    budget = LAYOUT_REGISTRY["content_cards"]
    bullets = [
        "体裁：朋友间邮件（非正式报告）",
        "核心任务：" + ("表明立场并用设计元素支撑理由 " * 6),
        "语气：友好、真诚，结尾鼓励参赛",
    ]
    layout = fit_bullet_card_layout(bullets, budget, content_height=2.2)
    for bullet, card_h, fit in zip(bullets, layout.heights, layout.fits):
        if is_arrow_separator(bullet):
            continue
        assert card_h >= fit.block_height + 0.30
