"""数据库共用工具测试。"""

from db.common import format_stages_mask, make_question_hash, topic_summary


def test_make_question_hash_normalizes_newlines():
    a = make_question_hash("题目\n")
    b = make_question_hash("题目")
    assert a == b


def test_format_stages_mask():
    assert format_stages_mask("1010") == "S1✓ S2· S3✓ S4·"


def test_topic_summary_truncates():
    long_q = "题" * 200
    assert len(topic_summary(long_q)) == 100
