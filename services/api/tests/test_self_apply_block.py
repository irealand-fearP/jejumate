"""호스트 본인의 파티 셀프 신청 차단 테스트 (work-order-2026-07-10-self-apply-fix.md).

사용자가 직접 발견한 버그: 내가 만든 파티에 내가 신청할 수 있었고, 그 신청이
호스트 승인(관리) 목록에도 그대로 떴다. 신청 생성 시점에 신청자의 users.id가
모임의 host_user_id와 같으면 거부하도록 고쳤다 — 프론트 버튼 숨김과 별개로
API 자체가 방어선이 되어야 한다(프론트를 안 거치는 직접 호출도 막는다).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories import local_store


@pytest.fixture(autouse=True)
def isolated_sqlite_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite3"
    monkeypatch.setattr(local_store, "DB_PATH", db_path)
    monkeypatch.setattr(local_store, "USE_POSTGRES", False)
    local_store.ensure_database()
    yield


@pytest.fixture
def client():
    return TestClient(create_app())


def _create_meeting(anonymous_id: str = "host-anon-1"):
    return local_store.create_meeting(
        category="move",
        title="공항 택시팟",
        description=None,
        place_label="제주공항",
        capacity=3,
        starts_at="2026-07-10T14:00",
        ends_at="2026-07-10T15:00",
        nickname="호스트바당이",
        anonymous_id=anonymous_id,
    )


def test_create_or_update_application_rejects_host_self_apply():
    meeting = _create_meeting(anonymous_id="host-anon-1")
    with pytest.raises(local_store.SelfApplicationError):
        local_store.create_or_update_application(
            meeting_id=meeting.meeting_id,
            nickname="호스트바당이",
            message="셀프 신청 시도",
            anonymous_id="host-anon-1",
        )


def test_self_apply_does_not_create_application_row():
    """예외가 나도 신청 레코드가 남으면 안 된다 — 호스트 관리 목록에 셀프 신청이
    떠서 발견된 버그라, 거부 후 목록에도 안 잡히는지 같이 확인한다."""
    meeting = _create_meeting(anonymous_id="host-anon-2")
    with pytest.raises(local_store.SelfApplicationError):
        local_store.create_or_update_application(
            meeting_id=meeting.meeting_id,
            nickname="호스트바당이",
            message=None,
            anonymous_id="host-anon-2",
        )

    applications = local_store.list_meeting_applications(
        meeting_id=meeting.meeting_id, owner_secret=meeting.owner_secret
    )
    assert applications.applications == []


def test_different_user_can_still_apply_normally():
    """회귀 확인: 다른 사용자의 정상 신청은 그대로 성공해야 한다."""
    meeting = _create_meeting(anonymous_id="host-anon-3")
    application = local_store.create_or_update_application(
        meeting_id=meeting.meeting_id,
        nickname="참가자물결이",
        message="같이 타고 싶어요",
        anonymous_id="applicant-anon-3",
    )
    assert application.status == "pending"

    applications = local_store.list_meeting_applications(
        meeting_id=meeting.meeting_id, owner_secret=meeting.owner_secret
    )
    assert len(applications.applications) == 1


def test_post_application_api_rejects_host_with_400(client):
    """API 계층(방어선) 확인: 호스트 anonymous_id로 POST하면 400 + 한국어 메시지."""
    meeting = _create_meeting(anonymous_id="host-anon-4")
    response = client.post(
        f"/api/meetings/{meeting.meeting_id}/applications",
        json={"nickname": "호스트바당이", "anonymous_id": "host-anon-4"},
    )
    assert response.status_code == 400
    assert "본인" in response.json()["detail"]


def test_post_application_api_allows_other_user(client):
    """회귀 확인(API 계층): 다른 사용자는 그대로 201/200으로 성공해야 한다."""
    meeting = _create_meeting(anonymous_id="host-anon-5")
    response = client.post(
        f"/api/meetings/{meeting.meeting_id}/applications",
        json={"nickname": "참가자물결이", "anonymous_id": "applicant-anon-5"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "pending"
