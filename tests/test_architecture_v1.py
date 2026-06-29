"""Tests for classroom architecture V1 deck builder."""

import json
from pathlib import Path

from scripts.architecture_v1 import (
    ARCHITECTURE_V1_SLOTS,
    _extract_thinking_chain,
    _migration_matches_question,
    _poster_lines,
    _question_lines,
    _stage4_migration,
    build_architecture_deck,
    build_slot_spec,
    inject_module_dividers,
    merge_stage3_into_architecture_deck,
    slots_for_preset,
)
from scripts.parse_stage3 import parse_stage3_file

FIXTURE = Path(__file__).parent / "fixtures" / "stage3_mental_health.md"
S1_SNIP = Path(__file__).parent.parent / "_s1_snip.txt"


def test_80min_has_more_slots_than_40min():
    assert len(slots_for_preset("80min")) > len(slots_for_preset("40min"))


def test_70min_slot_count():
    """70min = 80min minus B4/C3/D8/D10 (19 architecture slots + Stage3)."""
    slots = slots_for_preset("70min")
    assert len(slots) == 19
    ids = {s.slot_id for s in slots}
    assert "A3" in ids
    assert "B0" in ids
    assert ids.isdisjoint({"B4", "C3", "D8", "D10"})
    assert len(slots_for_preset("40min")) < len(slots) < len(slots_for_preset("80min"))


def test_build_architecture_deck_has_title_and_stage3_placeholder():
    data = {
        "question_type_label": "观点理由类",
        "question": "假如你是李华…\n请选择并说明理由。",
        "stage1": "- 我是谁：李华\n- 写给谁：James",
        "stage2": "PEEL\n基础版\nDear James,",
        "stage4": "易错：理由空泛",
    }
    deck = build_architecture_deck(data, preset="40min")
    types = [s["type"] for s in deck]
    assert "title" in types
    assert "_stage3_placeholder" in types
    assert types.index("title") < types.index("_stage3_placeholder")


def test_inject_module_dividers_inserts_before_modules():
    data = {
        "question": "题目",
        "stage1": "审题",
        "stage2": "PEEL",
        "stage4": "迁移",
    }
    base = build_architecture_deck(data, preset="40min")
    out = inject_module_dividers(base, enabled=True)
    assert out[0]["type"] == "divider"
    assert out[0]["name"] == "导入"


def test_merge_stage3_replaces_placeholder():
    data = parse_stage3_file(FIXTURE)
    stage3_specs = [
        {"type": "phrase_table", "part": "body", "title": "功能句型 · 观点", "table": data["phrase_tables"][0]},
    ]
    base = build_architecture_deck({"question": "q", "stage1": "s1", "stage2": "s2", "stage4": "s4"}, preset="40min")
    merged = merge_stage3_into_architecture_deck(base, stage3_specs)
    assert not any(s.get("type") == "_stage3_placeholder" for s in merged)
    assert any(s.get("type") == "phrase_table" for s in merged)


def test_compare_table_parsed_from_stage2():
    stage2 = """四、三版对比分析表
维度\t基础版\t高分版 A\t高分版 B
句式\t简单句\t复合句\t逻辑句
词汇\tfoundation\tdisciplined\tcausal chain
"""
    from scripts.architecture_v1 import _compare_table_rows

    rows = _compare_table_rows(stage2)
    assert rows[0] == ["维度", "基础版", "高分版 A", "高分版 B"]
    assert rows[1][0] == "句式"
    assert "foundation" in rows[2][1]


def test_upgrade_bullets_from_stage2():
    stage2 = """五、高分升级点解析
基础版 → 高分版 A
从"说态度"升级为"说动机"：not out of dullness…
从"说明由"升级为"说画面"：wrestling with ideas…
"""
    from scripts.architecture_v1 import _upgrade_bullets_from_stage2

    pts = _upgrade_bullets_from_stage2(stage2)
    assert len(pts) >= 2
    assert "动机" in pts[0]


def test_poster_lines_splits_poster_chunks():
    q = (
        "题干\n"
        "[图：两张海报：Poster 1是双手托心；Poster 2是浇水壶浇灌植物]"
    )
    posters = _poster_lines(q)
    assert len(posters) >= 2
    assert all(not p.startswith("[图") for p in posters)


def test_question_lines_unescapes_and_splits_poster():
    q = (
        "假如你是李华…\n"
        "[图：Poster 1 文字“It&#x27;s okay not to be okay.”]"
    )
    stem = _question_lines(q)
    assert "&#x27;" not in stem[0]
    assert all(not ln.startswith("[图") for ln in stem)
    posters = _poster_lines(q)
    assert len(posters) == 1
    assert "It's okay" in posters[0]


def test_thinking_path_excludes_mistake_paragraph():
    stage1 = S1_SNIP.read_text(encoding="utf-8") if S1_SNIP.is_file() else (
        "- 学生容易写成：当成给老师汇报\n"
        "- 底层思维路径：先确定选择，再分析海报设计元素与心理健康主题的关联"
    )
    path = _extract_thinking_chain(stage1)
    joined = " ".join(path)
    assert "学生容易写成" not in joined
    assert "底层思维路径" not in joined
    assert "心理健康" in joined or "设计元素" in joined or "↓" in path


def test_stage4_migration_rejects_lucy_for_james_question():
    question = "James 心理健康周海报设计大赛"
    lucy_item = "你是李华，你的朋友Lucy参加了校园环保海报设计大赛"
    assert not _migration_matches_question(lucy_item, question)
    stage4 = f"三、课后练习题\n- 写作题：{lucy_item}，请说明理由。"
    pts = _stage4_migration(stage4, question)
    assert pts
    assert all("Lucy" not in p for p in pts)
    assert all("环保" not in p for p in pts)


def test_title_spec_has_poster_lines_when_present():
    slot = next(s for s in ARCHITECTURE_V1_SLOTS if s.slot_id == "A1")
    spec = build_slot_spec(
        slot,
        {
            "question_type_label": "观点理由类",
            "question": "题干第一行\n[图：两张海报描述]",
            "stage1": "",
            "stage2": "",
            "stage4": "",
        },
    )
    assert spec is not None
    assert "poster_lines" in spec
    assert spec["body"] == ["题干第一行"]


def test_stage1_tasks_not_duplicate_triplet():
    from scripts.architecture_v1 import _stage1_tasks, _stage1_triplet

    stage1 = (
        "### 2.1 三元审题\n"
        "- **我是谁**：交换生朋友李华\n"
        "- **写给谁**：交换生朋友James\n"
        "- **为了什么**：给他在心理健康周海报设计大赛中选择一个版本并说明理由\n"
        "### 要点与结构规划\n"
        "开头段\n- 功能：问候 + 表明写作目的\n"
        "主体段\n- 要点[1]：选择 Poster 1（核心）\n"
        "结尾段\n- 功能：鼓励收束\n"
    )
    triplet = _stage1_triplet(stage1)
    tasks = _stage1_tasks(stage1)
    assert "李华" in triplet[0]
    assert not any("李华" in t for t in tasks)
    assert tasks[0].startswith("①")


def test_stage1_one_truth_on_triplet_spec():
    from scripts.architecture_v1 import ARCHITECTURE_V1_SLOTS, build_slot_spec

    stage1 = (
        "动笔前自检五问：\n1. 语气 — a\n"
        "💡 一句大实话\n"
        "本题最危险的陷阱是理由空泛。\n"
        "### 2.1 三元审题\n"
        "- **我是谁**：李华\n- **写给谁**：James\n- **为了什么**：选海报\n"
    )
    slot = next(s for s in ARCHITECTURE_V1_SLOTS if s.slot_id == "B1")
    spec = build_slot_spec(slot, {"stage1": stage1, "stage2": "", "stage4": "", "question": ""})
    assert spec is not None
    assert "callout" in spec
    assert "陷阱" in spec["callout"]
    assert "我是谁" in spec["bullets"][0]


def test_stage1_self_check_five_parsed_from_export_style():
    from scripts.architecture_v1 import _stage1_self_check_five, build_slot_spec

    stage1 = (
        "动笔前自检五问：\n"
        "**1. 语气** — 朋友间建议还是正式报告？\n"
        "**2. 结构** — 有具体理由还是只有我觉得好？\n"
        "**3. 逻辑** — 是否说明为什么选这个？\n"
        "**4. 立意** — 是否写出深层意义？\n"
        "**5. 语言** — 是否用了关键表达？\n"
        "💡 一句大实话\n"
        "陷阱是理由空泛。"
    )
    bullets = _stage1_self_check_five(stage1)
    assert len(bullets) == 5
    assert bullets[0].startswith("语气")

    slot = next(s for s in ARCHITECTURE_V1_SLOTS if s.slot_id == "B0")
    specs = build_slot_spec(slot, {"stage1": stage1, "stage2": "", "stage4": "", "question": ""})
    assert isinstance(specs, list)
    assert len(specs) == 1
    assert specs[0]["title"] == "审题 · 动笔自检五问"
    assert len(specs[0]["bullets"]) == 5


def test_peel_parses_supporting_points_heading():
    from scripts.architecture_v1 import _peel_from_stage2

    stage2 = (
        "一、PEEL 写作策略\n"
        "支撑要点 Point 1（先选 Poster 1/2）\n"
        "核心句（P）\n"
        '"I\'d go with Poster 1."\n'
        "拓展策略（E）\n"
        "- 具象化：把「选择」绑定到画面元素\n"
        "连至下一点（L）\n"
        '- 过渡连接："Here\'s why I think so."\n'
        "支撑要点 Point 2（说明理由）\n"
        "核心句（P）\n"
        '"The cracked heart captures the theme."\n'
        "拓展策略（E）\n"
        "- 元素含义：crack represents struggles\n"
        "连至下一点（L）\n"
        '- 隐性融入："Overall, Poster 1 feels authentic."\n'
    )
    points = _peel_from_stage2(stage2)
    assert len(points) == 2
    assert "支撑要点" in points[0].get("heading", "")
    assert points[0]["p"]
    assert points[0]["e_items"]
    assert points[0]["l"]
    assert "Poster 1" in points[0]["l"] or "why" in points[0]["l"].lower()
