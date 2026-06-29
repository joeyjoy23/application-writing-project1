"""Layout Solver Lite — conservative WPS-safe layout decisions."""

from scripts.layout_solver_lite import (
    estimate_real_text_height,
    final_container_height,
    plan_text_block,
    solve_fix_cards_layout,
    solve_title_layout,
)


def test_estimate_real_text_height_conservative_for_cjk():
    h = estimate_real_text_height("心理健康很重要，我们要关注。", 28, 5.0, bullet=True)
    assert h >= 0.5
    h_en = estimate_real_text_height("Short line.", 28, 5.0)
    assert h > h_en * 0.9


def test_final_container_height_includes_padding():
    inner = 1.0
    outer = final_container_height(inner)
    assert outer > inner


def test_title_layout_skips_stem_when_body_empty():
    plan = solve_title_layout({"type": "title", "body": [], "task_tag": "选海报 · 写理由"})
    assert plan.show_stem_panel is False
    assert "本课任务" in plan.task_pill_text


def test_plan_text_block_shape_envelope():
    plan = plan_text_block("• 基础：先读懂题干，圈出关键词。", 11.0, bullet=True)
    assert plan.container_height >= plan.inner_height


def test_fix_cards_dual_when_room():
    left = "别这样写\nI think mental health is not important."
    right = "改成\nI believe mental health matters deeply."
    mode, plans = solve_fix_cards_layout(left, right, avail_height=3.0)
    assert mode in ("dual", "stack", "single")
    assert plans
    for p in plans:
        assert p.container_height >= 0.72
