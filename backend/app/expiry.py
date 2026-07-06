"""
태스크7: 시간 민감 자동 마감. 배치/크론 없이 "읽는 시점"에 deadline<now를 계산한다.

SQLite는 DateTime(timezone=True) 컬럼이라도 왕복하면 tzinfo를 버린다(운영 DB인
Postgres는 그대로 유지). 그래서 비교 전에 항상 naive UTC로 정규화해 aware/naive
어느 조합이 들어와도 안전하게 비교한다.
"""
from datetime import datetime, timezone


def _to_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def is_expired(deadline: datetime | None, now: datetime | None = None) -> bool:
    """deadline이 없으면(정보성 글 등) 절대 만료되지 않는다."""
    if deadline is None:
        return False
    now = now or datetime.now(timezone.utc)
    return _to_naive_utc(deadline) < _to_naive_utc(now)


def is_active_post(post, now: datetime | None = None) -> bool:
    """수동 마감(status=closed)이거나 마감시간이 지난 글은 활성이 아니다."""
    if post.status == "closed":
        return False
    return not is_expired(post.deadline, now)
