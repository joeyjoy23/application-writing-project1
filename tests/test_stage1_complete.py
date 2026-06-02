from utils.parsers import stage1_summary_incomplete


def test_stage1_complete_ok():
    text = "## 6. 要点\n\n主体段\n- 要点①：x\n\n结尾段\n- 功能：收尾"
    assert stage1_summary_incomplete(text) is None


def test_stage1_truncated_mid_paren():
    text = "## 6. 要点\n\n主体段\n- 要点①：描述（核心，"
    assert stage1_summary_incomplete(text) is not None
