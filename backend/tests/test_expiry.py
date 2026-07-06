"""
태스크7: 배치 없이 읽는 시점에 deadline<now를 판정하는 만료 체크.

deadline이 없는 info 글은 절대 만료되지 않고, party 글은 deadline이 지나면
status가 'active'로 남아있어도 만료로 취급해야 한다(자동 마감).
SQLite(테스트)는 DateTime(timezone=True)라도 tzinfo를 버리므로, aware/naive
어느 쪽이 들어와도 올바르게 비교돼야 한다.
"""
from datetime import datetime, timedelta, timezone

from app.expiry import is_active_post, is_expired


def test_no_deadline_never_expires():
    assert is_expired(None) is False


def test_future_deadline_not_expired():
    future = datetime.now(timezone.utc) + timedelta(minutes=10)
    assert is_expired(future) is False


def test_past_deadline_expired():
    past = datetime.now(timezone.utc) - timedelta(minutes=10)
    assert is_expired(past) is True


def test_naive_deadline_compared_against_aware_now():
    """SQLite에서 조회한 naive datetime도 올바르게 판정돼야 한다."""
    naive_past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    assert is_expired(naive_past) is True

    naive_future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1)
    assert is_expired(naive_future) is False


def test_explicit_now_parameter_used_for_deterministic_check():
    deadline = datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc)
    before = datetime(2026, 7, 6, 14, 59, tzinfo=timezone.utc)
    after = datetime(2026, 7, 6, 15, 1, tzinfo=timezone.utc)
    assert is_expired(deadline, now=before) is False
    assert is_expired(deadline, now=after) is True


class _FakePost:
    def __init__(self, status, deadline):
        self.status = status
        self.deadline = deadline


def test_active_post_with_no_deadline_and_active_status():
    assert is_active_post(_FakePost("active", None)) is True


def test_closed_status_is_never_active_even_without_deadline():
    assert is_active_post(_FakePost("closed", None)) is False


def test_active_status_but_deadline_passed_is_not_active():
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert is_active_post(_FakePost("active", past)) is False
