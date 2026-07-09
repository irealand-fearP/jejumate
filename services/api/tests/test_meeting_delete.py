"""파티 해산(DELETE /api/meetings/{meeting_id}?owner_secret=...) 테스트.

호스트 액션이므로 승인/거절과 같은 권한 모델(owner_secret)을 쓴다.
관리 코드가 틀리면 403이고, 성공하면 신청·채팅까지 cascade로 지운다.
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


def _create_meeting():
    return local_store.create_meeting(
        category="move",
        title="공항 택시팟",
        description=None,
        place_label="제주공항",
        capacity=3,
        starts_at="2026-07-10T14:00",
        ends_at="2026-07-10T15:00",
        nickname="호스트바당이",
        anonymous_id="host-1",
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


def test_delete_meeting_rejects_wrong_owner_secret(client):
    """관리 코드가 틀리면 403이고 파티는 그대로 남는다."""
    meeting = _create_meeting()

    response = client.delete(f"/api/meetings/{meeting.meeting_id}?owner_secret=틀린코드")

    assert response.status_code == 403
    assert _count("meetings", meeting.meeting_id) == 1


def test_delete_meeting_returns_404_for_unknown_meeting(client):
    response = client.delete("/api/meetings/존재하지않는파티", params={"owner_secret": "x"})
    assert response.status_code == 404


def test_delete_meeting_cascades_applications_and_chats(client):
    """성공 시 파티 + 신청 + 채팅이 함께 지워진다(users/profiles는 보존)."""
    meeting = _create_meeting()
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

    assert _count("meeting_applications", meeting.meeting_id) == 1
    assert _count("meeting_chat_messages", meeting.meeting_id) == 1
    users_before = _users_count()

    response = client.delete(
        f"/api/meetings/{meeting.meeting_id}?owner_secret={meeting.owner_secret}"
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["meeting_id"] == meeting.meeting_id
    assert body["status"] == "deleted"

    assert _count("meetings", meeting.meeting_id) == 0
    assert _count("meeting_applications", meeting.meeting_id) == 0
    assert _count("meeting_chat_messages", meeting.meeting_id) == 0
    # 닉네임·익명ID는 영구 보존 방침 — 해산으로 지우지 않는다.
    assert _users_count() == users_before


def test_deleted_meeting_disappears_from_open_list(client):
    """해산한 파티는 목록(GET /api/meetings)에서도 사라진다."""
    meeting = _create_meeting()
    titles_before = [m.title for m in local_store.list_open_meetings()]
    assert "공항 택시팟" in titles_before

    client.delete(f"/api/meetings/{meeting.meeting_id}?owner_secret={meeting.owner_secret}")

    assert meeting.meeting_id not in [m.id for m in local_store.list_open_meetings()]
