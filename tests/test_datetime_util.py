from utils.datetime_util import format_created_at_display, format_created_at_list, utc_now_str


def test_utc_evening_shows_beijing_time():
    assert format_created_at_display("2026-06-02 11:57:33") == "2026-06-02 19:57:33"


def test_list_format_omits_seconds():
    assert format_created_at_list("2026-06-02 11:57:33") == "2026-06-02 19:57"


def test_utc_now_str_format():
    s = utc_now_str()
    assert len(s) == 19 and s[4] == "-" and s[10] == " "
