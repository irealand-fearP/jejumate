"""마감 2일 지난 사용자 파티 실제 삭제(cleanup_expired_parties) 테스트.

목록 숨김(grace period)과 달리 이건 복구 불가한 실삭제다. 연관
신청·채팅까지 cascade로 지우되, users/profiles(닉네임·익명ID)와
카톡 수집 파티(source='kakao_chat')는 건드리지 않는다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.repositories import local_store


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


def _create_meeting(nickname: str, anonymous_id: str):
    return local_store.create_meeting(
        category="move",
        title="공항 택시팟",
        description=None,
        place_label="제주공항",
        capacity=3,
        starts_at="2026-07-10T14:00",
        ends_at="2026-07-10T15:00",
        nickname=nickname,
        anonymous_id=anonymous_id,
    )


def _set_ends_at_and_source(meeting_id: str, *, ends_at: datetime, source: str):
    with local_store._connect() as connection:
        connection.execute(
            "UPDATE meetings SET ends_at = ?, source = ? WHERE id = ?",
            (ends_at.isoformat(), source, meeting_id),
        )


def _count(table: str, meeting_id: str) -> int:
    with local_store._connect() as connection:
        column = "id" if table == "meetings" else "meeting_id"
        row = connection.execute(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {column} = ?", (meeting_id,)
        ).fetchone()
    return row["n"]


def _users_count() -> int:
    with local_store._connect() as connection:
        return connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def test_deletes_party_with_applications_and_chats_after_two_days():
    # 시드 모임(고정 날짜)이 시간이 지나 삭제 대상이 되면 기대값이 흔들린다 — 먼저 비운다.
    local_store.cleanup_expired_parties()
    meeting = _create_meeting("호스트바당이", "host-1")
    application = local_store.create_or_update_application(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        message="타고 싶어요",
        anonymous_id="applicant-1",
    )
    local_store.decide_meeting_application(
        meeting_id=meeting.meeting_id,
        application_id=application.application_id,
        owner_secret=meeting.owner_secret,
        decision="approve",
    )
    local_store.create_chat_message(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        content="안녕하세요",
        anonymous_id="applicant-1",
    )

    old = datetime.now(timezone.utc) - timedelta(days=settings.party_delete_after_days, hours=1)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=old, source="service")

    users_before = _users_count()
    deleted = local_store.cleanup_expired_parties()

    assert deleted == 1
    assert _count("meetings", meeting.meeting_id) == 0
    assert _count("meeting_applications", meeting.meeting_id) == 0
    assert _count("meeting_chat_messages", meeting.meeting_id) == 0
    # users/profiles는 영구 보존 방침 — 삭제 대상 아님.
    assert _users_count() == users_before


def test_keeps_party_before_two_days():
    # 시드 모임(고정 날짜)이 시간이 지나 삭제 대상이 되면 기대값이 흔들린다 — 먼저 비운다.
    local_store.cleanup_expired_parties()
    meeting = _create_meeting("호스트바당이", "host-2")
    recent = datetime.now(timezone.utc) - timedelta(days=1)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=recent, source="service")

    assert local_store.cleanup_expired_parties() == 0
    assert _count("meetings", meeting.meeting_id) == 1


def test_keeps_kakao_party_even_after_two_days():
    # 시드 모임(고정 날짜)이 시간이 지나 삭제 대상이 되면 기대값이 흔들린다 — 먼저 비운다.
    local_store.cleanup_expired_parties()
    """카톡 수집 파티는 이 정리 대상이 아니다(별도 수명 주기)."""
    meeting = _create_meeting("호스트바당이", "host-3")
    old = datetime.now(timezone.utc) - timedelta(days=settings.party_delete_after_days + 1)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=old, source="kakao_chat")

    assert local_store.cleanup_expired_parties() == 0
    assert _count("meetings", meeting.meeting_id) == 1
