from datetime import datetime, timedelta, timezone

from utils.share_util import (
    build_share_url,
    expires_at_from_now,
    is_share_expired,
    share_ttl_days,
)


def test_build_share_url():
    url = build_share_url("abc123", "https://app.streamlit.app")
    assert url == "https://app.streamlit.app/?share=abc123"


def test_build_share_url_strips_trailing_slash():
    url = build_share_url("t", "https://app.streamlit.app/")
    assert url.endswith("?share=t")


def test_is_share_expired_future():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    assert not is_share_expired(future)


def test_is_share_expired_past():
    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    assert is_share_expired(past)


def test_expires_at_from_now_default_days():
    assert share_ttl_days() >= 1
    exp = expires_at_from_now()
    assert not is_share_expired(exp)
