"""마감(ends_at) 지난 파티의 공개 목록 노출 규칙 테스트.

카톡 수집 파티(source='kakao_chat')는 마감 즉시 숨긴다(기존 동작, 회귀 확인용).
사용자가 만든 서비스 파티(source='service')는 마감 직후 바로 사라지면 매정하므로
grace period(설정값, 기본 1시간)만큼 여유를 두고 숨긴다.

대상 함수: list_open_meetings()(GET /api/meetings), get_home_data()(홈 미리보기).
내정보 화면(list_notifications_for_applicant, get_meeting_by_id 등)은 이 필터를
쓰지 않는 별도 조회 경로이므로 여기서 회귀 없음도 함께 확인한다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.repositories import local_store


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    """테스트마다 독립된 sqlite 파일을 쓰도록 DB_PATH를 갈아끼운다(다른 테스트/실제 데이터 오염 방지)."""
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
    """테스트 편의를 위해 ends_at/source를 직접 갱신한다(실제 API 경로에는 없는 조작)."""
    with local_store._connect() as connection:
        connection.execute(
            "UPDATE meetings SET ends_at = ?, source = ? WHERE id = ?",
            (ends_at.isoformat(), source, meeting_id),
        )


def _open_meeting_ids() -> set[str]:
    return {m.id for m in local_store.list_open_meetings()}


def _home_meeting_ids() -> set[str]:
    home = local_store.get_home_data()
    return {m.id for m in home.meetings}


def test_service_meeting_visible_when_not_yet_ended():
    meeting = _create_meeting("호스트바당이", "host-1")
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=future, source="service")

    assert meeting.meeting_id in _open_meeting_ids()
    assert meeting.meeting_id in _home_meeting_ids()


def test_service_meeting_visible_within_grace_period():
    meeting = _create_meeting("호스트바당이", "host-2")
    just_ended = datetime.now(timezone.utc) - timedelta(minutes=30)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=just_ended, source="service")

    assert settings.service_meeting_hide_grace_minutes >= 30
    assert meeting.meeting_id in _open_meeting_ids()
    assert meeting.meeting_id in _home_meeting_ids()


def test_service_meeting_hidden_after_grace_period():
    meeting = _create_meeting("호스트바당이", "host-3")
    long_ended = datetime.now(timezone.utc) - timedelta(
        minutes=settings.service_meeting_hide_grace_minutes + 30
    )
    _set_ends_at_and_source(meeting.meeting_id, ends_at=long_ended, source="service")

    assert meeting.meeting_id not in _open_meeting_ids()
    assert meeting.meeting_id not in _home_meeting_ids()


def test_kakao_meeting_hidden_immediately_after_ending_no_grace():
    """카톡 파티는 grace 없이 마감 즉시 숨겨진다(기존 동작 회귀 확인)."""
    meeting = _create_meeting("호스트바당이", "host-4")
    just_ended = datetime.now(timezone.utc) - timedelta(minutes=1)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=just_ended, source="kakao_chat")

    assert meeting.meeting_id not in _open_meeting_ids()
    assert meeting.meeting_id not in _home_meeting_ids()


def test_recent_kakao_meeting_is_marked_new_for_filter_badge():
    """최근 오픈채팅 글도 오픈채팅 필터의 N 배지를 켤 수 있어야 한다."""
    meeting = _create_meeting("오픈채팅", "host-kakao-new")
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    _set_ends_at_and_source(meeting.meeting_id, ends_at=future, source="kakao_chat")

    listed = {item.id: item for item in local_store.list_open_meetings()}

    assert listed[meeting.meeting_id].source == "kakao_chat"
    assert listed[meeting.meeting_id].is_new is True


def test_expired_service_meeting_still_visible_in_my_applications():
    """마감+grace 지난 파티라도 내정보(참여중인 파티, 신청자 알림 조회)에는 여전히 보여야 한다."""
    meeting = _create_meeting("호스트바당이", "host-5")
    application = local_store.create_or_update_application(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        message="같이 타고 싶어요",
        anonymous_id="applicant-anon-5",
    )
    long_ended = datetime.now(timezone.utc) - timedelta(
        minutes=settings.service_meeting_hide_grace_minutes + 30
    )
    _set_ends_at_and_source(meeting.meeting_id, ends_at=long_ended, source="service")

    # 공개 목록에서는 사라졌지만
    assert meeting.meeting_id not in _open_meeting_ids()

    # 신청자 본인의 알림 목록에는 여전히 보인다.
    notifications = local_store.list_notifications_for_applicant(anonymous_id="applicant-anon-5")
    assert application.application_id in [n.application_id for n in notifications.notifications]

    # 호스트의 신청자 관리(owner_secret 기반) 조회에도 여전히 보인다.
    applications = local_store.list_meeting_applications(
        meeting_id=meeting.meeting_id, owner_secret=meeting.owner_secret
    )
    assert application.application_id in [a.application_id for a in applications.applications]

    # 모임 상세(get_meeting_by_id)도 상태와 무관하게 여전히 조회된다.
    fetched = local_store.get_meeting_by_id(meeting_id=meeting.meeting_id)
    assert fetched.id == meeting.meeting_id
