"""만료 파티 실제 삭제(cleanup_expired_parties) 테스트.

목록 숨김(grace period)과 달리 이건 복구 불가한 실삭제다. 두 갈래 규칙:
- 사용자 파티: 마감(ends_at) 후 2일
- 카톡 수집 파티: 원문 채팅 입력 시각(created_at) 후 4시간

연관 신청·채팅까지 cascade로 지우되, users/profiles(닉네임·익명ID)와
생활게시판 글(board_posts)은 건드리지 않는다.
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


def _set_created_at_and_source(meeting_id: str, *, created_at: datetime, source: str):
    with local_store._connect() as connection:
        connection.execute(
            "UPDATE meetings SET created_at = ?, source = ? WHERE id = ?",
            (created_at.isoformat(), source, meeting_id),
        )


def _insert_board_post(post_id: str, *, source: str) -> None:
    with local_store._connect() as connection:
        connection.execute(
            """
            INSERT INTO board_posts (id, category, title, body, author_nickname, source, created_at)
            VALUES (?, 'share', '오픈채팅 나눔 글', '본문', '오픈채팅', ?, ?)
            """,
            (post_id, source, local_store._now()),
        )


def _board_post_count(post_id: str) -> int:
    with local_store._connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM board_posts WHERE id = ?", (post_id,)
        ).fetchone()
    return row["n"]


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


def test_keeps_kakao_party_with_old_ends_at_but_recent_created_at():
    """카톡 파티는 ends_at이 아무리 오래됐어도 created_at 기준으로만 지운다 —
    방금 등록된 파티는 마감 시각이 과거여도 남아 있어야 한다."""
    # 시드 모임(고정 날짜)이 시간이 지나 삭제 대상이 되면 기대값이 흔들린다 — 먼저 비운다.
    local_store.cleanup_expired_parties()
    meeting = _create_meeting("호스트바당이", "host-3")
    old = datetime.now(timezone.utc) - timedelta(days=settings.party_delete_after_days + 1)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=old, source="kakao_chat")

    assert local_store.cleanup_expired_parties() == 0
    assert _count("meetings", meeting.meeting_id) == 1


def test_deletes_kakao_party_created_over_four_hours_ago():
    """카톡 수집 파티는 원문 입력 후 kakao_party_delete_after_hours(기본 4시간)가 지나면 삭제된다."""
    local_store.cleanup_expired_parties()
    meeting = _create_meeting("호스트바당이", "host-4")
    old = datetime.now(timezone.utc) - timedelta(
        hours=settings.kakao_party_delete_after_hours, minutes=1
    )
    _set_created_at_and_source(meeting.meeting_id, created_at=old, source="kakao_chat")

    assert local_store.cleanup_expired_parties() == 1
    assert _count("meetings", meeting.meeting_id) == 0


def test_keeps_kakao_party_created_under_three_hours_ago():
    """3시간 전 등록된 카톡 파티는 아직 살아 있어야 한다(4시간 규칙)."""
    local_store.cleanup_expired_parties()
    meeting = _create_meeting("호스트바당이", "host-5")
    recent = datetime.now(timezone.utc) - timedelta(hours=3)
    _set_created_at_and_source(meeting.meeting_id, created_at=recent, source="kakao_chat")

    assert local_store.cleanup_expired_parties() == 0
    assert _count("meetings", meeting.meeting_id) == 1


def test_coldstart_party_uses_original_kst_message_time_and_four_hour_expiry():
    """오프셋 없는 카톡 내보내기 시각은 KST로 해석해 화면·유효기간에 함께 쓴다."""
    local_store.create_coldstart_meeting(
        item_id=987654321,
        title="원문 시간 테스트",
        meeting_category="move",
        description="공항 이동 동행을 구합니다.",
        created_at="2026-07-13 18:43:00",
    )

    with local_store._connect() as connection:
        row = connection.execute(
            "SELECT starts_at, ends_at, created_at FROM meetings WHERE title = ?",
            ("원문 시간 테스트",),
        ).fetchone()

    assert row["starts_at"] == "2026-07-13T09:43:00+00:00"
    assert row["created_at"] == row["starts_at"]
    assert datetime.fromisoformat(row["ends_at"]) - datetime.fromisoformat(row["starts_at"]) == timedelta(
        hours=settings.kakao_party_delete_after_hours
    )


def test_cleanup_never_touches_kakao_board_posts():
    """생활게시판의 오픈채팅 글은 파티 정리와 무관하게 보존한다(사용자 명시 지시)."""
    local_store.cleanup_expired_parties()
    _insert_board_post("board-kakao-1", source="kakao_chat")

    # 삭제 대상 카톡 파티를 하나 만들어 정리를 실제로 돌린다.
    meeting = _create_meeting("호스트바당이", "host-6")
    old = datetime.now(timezone.utc) - timedelta(
        hours=settings.kakao_party_delete_after_hours, minutes=1
    )
    _set_created_at_and_source(meeting.meeting_id, created_at=old, source="kakao_chat")

    assert local_store.cleanup_expired_parties() == 1
    assert _count("meetings", meeting.meeting_id) == 0
    # 파티는 지워졌지만 게시판 글은 그대로다.
    assert _board_post_count("board-kakao-1") == 1
