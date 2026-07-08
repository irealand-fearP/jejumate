"""채팅 메시지 발신자 식별(sender_anonymous_id) 통합 테스트.

말풍선 정렬(내 메시지 vs 상대 메시지)을 프론트에서 정확히 판단하려면 닉네임이 아니라
anonymous_id로 발신자를 구분해야 한다(닉네임은 중복될 수 있음). 신청 -> 승인 -> 채팅
전체 흐름을 실제 sqlite DB에 재현해서 각 메시지의 sender_anonymous_id가 실제 발신자와
일치하는지 검증한다.
"""
from __future__ import annotations

import pytest

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


def test_chat_message_includes_sender_anonymous_id_for_each_participant():
    # 호스트가 모임을 만들고, 참가자가 신청 -> 승인된다.
    meeting = _create_meeting("호스트바당이", "host-anon-1")
    application = local_store.create_or_update_application(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        message="같이 타고 싶어요",
        anonymous_id="applicant-anon-1",
    )
    local_store.decide_meeting_application(
        meeting_id=meeting.meeting_id,
        application_id=application.application_id,
        owner_secret=meeting.owner_secret,
        decision="approve",
    )

    # 참가자와 호스트가 채팅을 주고받는다.
    local_store.create_chat_message(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        content="몇 시에 출발하나요?",
        anonymous_id="applicant-anon-1",
    )
    local_store.create_chat_message(
        meeting_id=meeting.meeting_id,
        nickname="호스트바당이",
        content="2시에 출발할게요",
        anonymous_id="host-anon-1",
        owner_secret=meeting.owner_secret,
    )

    result = local_store.list_chat_messages(meeting_id=meeting.meeting_id, anonymous_id="applicant-anon-1")

    assert [message.content for message in result.messages] == ["몇 시에 출발하나요?", "2시에 출발할게요"]
    assert result.messages[0].sender_anonymous_id == "applicant-anon-1"
    assert result.messages[1].sender_anonymous_id == "host-anon-1"


def test_create_chat_message_response_also_includes_sender_anonymous_id():
    """전송 직후 응답(create_chat_message 반환값)에도 sender_anonymous_id가 채워져야
    프론트가 재조회 없이 바로 내 메시지를 오른쪽 정렬할 수 있다."""
    meeting = _create_meeting("호스트바당이", "host-anon-2")

    result = local_store.create_chat_message(
        meeting_id=meeting.meeting_id,
        nickname="호스트바당이",
        content="첫 메시지",
        anonymous_id="host-anon-2",
        owner_secret=meeting.owner_secret,
    )

    assert result.messages[-1].sender_anonymous_id == "host-anon-2"
