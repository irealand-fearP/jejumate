"""파티(모임) 탈퇴 기능 통합 테스트.

승인된 참가자가 스스로 신청을 삭제(deleteMyApplication -> delete_my_application)하면
approved_count가 실제로 감소하는지 확인한다. 프론트는 기존 함수를 호출만 하므로,
백엔드 로직 자체가 신청 -> 승인 -> 탈퇴 전체 흐름에서 여전히 올바른지가 검증 대상이다.
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


def _create_meeting(nickname: str, anonymous_id: str, capacity: int = 3):
    return local_store.create_meeting(
        category="move",
        title="공항 택시팟",
        description=None,
        place_label="제주공항",
        capacity=capacity,
        starts_at="2026-07-10T14:00",
        ends_at="2026-07-10T15:00",
        nickname=nickname,
        anonymous_id=anonymous_id,
    )


def test_leaving_approved_meeting_decrements_approved_count():
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

    status_after_approve = local_store.get_meeting_status(meeting_id=meeting.meeting_id)
    assert status_after_approve.approved_count == 1

    # 승인된 참가자가 스스로 탈퇴한다(프론트의 deleteMyApplication -> DELETE
    # /api/meetings/{id}/applications/{id}?anonymous_id=... 호출과 동일한 파라미터).
    result = local_store.delete_my_application(
        meeting_id=meeting.meeting_id,
        application_id=application.application_id,
        anonymous_id="applicant-anon-1",
    )
    assert result.status == "deleted"

    status_after_leave = local_store.get_meeting_status(meeting_id=meeting.meeting_id)
    assert status_after_leave.approved_count == 0

    # 탈퇴 후에는 신청 목록에서도 사라져야 한다(호스트 관리 화면 재조회 시나리오).
    applications = local_store.list_meeting_applications(
        meeting_id=meeting.meeting_id, owner_secret=meeting.owner_secret
    )
    assert application.application_id not in [item.application_id for item in applications.applications]


def test_leaving_pending_application_does_not_change_approved_count():
    """아직 승인되지 않은(pending) 신청을 삭제하면 approved_count는 그대로여야 한다
    (approved 상태일 때만 감소 로직이 타야 정상)."""
    meeting = _create_meeting("호스트바당이", "host-anon-2")
    application = local_store.create_or_update_application(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        message="같이 타고 싶어요",
        anonymous_id="applicant-anon-2",
    )

    status_before = local_store.get_meeting_status(meeting_id=meeting.meeting_id)
    assert status_before.approved_count == 0

    local_store.delete_my_application(
        meeting_id=meeting.meeting_id,
        application_id=application.application_id,
        anonymous_id="applicant-anon-2",
    )

    status_after = local_store.get_meeting_status(meeting_id=meeting.meeting_id)
    assert status_after.approved_count == 0


def test_leaving_with_mismatched_anonymous_id_is_rejected():
    """본인 신청이 아니면 삭제되면 안 된다 — anonymous_id로 본인 확인하는 권한 모델을 지킨다."""
    meeting = _create_meeting("호스트바당이", "host-anon-3")
    application = local_store.create_or_update_application(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        message=None,
        anonymous_id="applicant-anon-3",
    )
    local_store.decide_meeting_application(
        meeting_id=meeting.meeting_id,
        application_id=application.application_id,
        owner_secret=meeting.owner_secret,
        decision="approve",
    )

    with pytest.raises(local_store.ApplicantMismatchError):
        local_store.delete_my_application(
            meeting_id=meeting.meeting_id,
            application_id=application.application_id,
            anonymous_id="someone-else",
        )

    # 거부됐으니 approved_count는 그대로 유지돼야 한다.
    status = local_store.get_meeting_status(meeting_id=meeting.meeting_id)
    assert status.approved_count == 1
