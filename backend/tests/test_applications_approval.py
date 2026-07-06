"""
태스크14: 글쓴이 승인/거절('같이 가기로 하기') + 모집 현황(승인 count vs 정원).
관리 코드(owner_secret) 확인 기반. 정원 초과 승인은 서버에서 막는다.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.embedding import MockEmbeddingProvider
from app.main import app, get_db, get_embedder
from app.models import Application, Post

NOW = datetime.now(timezone.utc)


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_embedder] = lambda: MockEmbeddingProvider()
    with TestClient(app) as test_client:
        test_client._session_factory = TestSession
        yield test_client
    app.dependency_overrides.clear()


def _seed_party_post(client, capacity=2, owner_secret="1234"):
    session = client._session_factory()
    post = Post(
        source="user_post",
        post_type="party",
        category="ride",
        content="함덕 택시팟 구해요",
        author_nickname="글쓴이",
        original_timestamp=NOW,
        capacity=capacity,
        owner_secret=owner_secret,
        embedding=[0.0] * 1536,
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    session.close()
    return post


def _apply(client, post_id, nickname="신청자"):
    res = client.post(f"/posts/{post_id}/applications", json={"nickname": nickname, "message": "저요"})
    return res.json()["id"]


def test_status_reports_capacity_and_approved_count(client):
    post = _seed_party_post(client, capacity=4)
    res = client.get(f"/posts/{post.id}/status")
    assert res.status_code == 200
    body = res.json()
    assert body["capacity"] == 4
    assert body["approved_count"] == 0
    assert body["is_closed"] is False


def test_list_applications_without_code_shows_nickname_only(client):
    post = _seed_party_post(client)
    _apply(client, post.id, nickname="신청자1")

    res = client.get(f"/posts/{post.id}/applications")
    body = res.json()
    assert body["authorized"] is False
    assert body["applications"] == [{"id": None, "nickname": "신청자1", "message": None, "status": None}]


def test_list_applications_with_wrong_code_is_unauthorized(client):
    post = _seed_party_post(client, owner_secret="1234")
    _apply(client, post.id)

    res = client.get(f"/posts/{post.id}/applications", params={"owner_secret": "9999"})
    assert res.json()["authorized"] is False


def test_list_applications_with_correct_code_shows_full_detail(client):
    post = _seed_party_post(client, owner_secret="1234")
    app_id = _apply(client, post.id, nickname="신청자1")

    res = client.get(f"/posts/{post.id}/applications", params={"owner_secret": "1234"})
    body = res.json()
    assert body["authorized"] is True
    assert body["applications"] == [
        {"id": app_id, "nickname": "신청자1", "message": "저요", "status": "pending"}
    ]


def test_approve_requires_correct_owner_secret(client):
    post = _seed_party_post(client, owner_secret="1234")
    app_id = _apply(client, post.id)

    res = client.post(
        f"/posts/{post.id}/applications/{app_id}/approve", params={"owner_secret": "0000"}
    )
    assert res.status_code == 403


def test_approve_increments_approved_count(client):
    post = _seed_party_post(client, capacity=2, owner_secret="1234")
    app_id = _apply(client, post.id)

    res = client.post(
        f"/posts/{post.id}/applications/{app_id}/approve", params={"owner_secret": "1234"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"

    status = client.get(f"/posts/{post.id}/status").json()
    assert status["approved_count"] == 1


def test_approve_blocked_when_capacity_full(client):
    post = _seed_party_post(client, capacity=1, owner_secret="1234")
    first = _apply(client, post.id, nickname="1번")
    second = _apply(client, post.id, nickname="2번")

    ok = client.post(f"/posts/{post.id}/applications/{first}/approve", params={"owner_secret": "1234"})
    assert ok.status_code == 200

    full = client.post(f"/posts/{post.id}/applications/{second}/approve", params={"owner_secret": "1234"})
    assert full.status_code == 409


def test_reject_removes_from_list(client):
    post = _seed_party_post(client, owner_secret="1234")
    app_id = _apply(client, post.id, nickname="신청자1")

    res = client.post(f"/posts/{post.id}/applications/{app_id}/reject", params={"owner_secret": "1234"})
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    listing = client.get(f"/posts/{post.id}/applications", params={"owner_secret": "1234"}).json()
    assert listing["applications"] == []


def test_approve_already_processed_application_rejected(client):
    post = _seed_party_post(client, capacity=2, owner_secret="1234")
    app_id = _apply(client, post.id)
    client.post(f"/posts/{post.id}/applications/{app_id}/approve", params={"owner_secret": "1234"})

    res = client.post(f"/posts/{post.id}/applications/{app_id}/approve", params={"owner_secret": "1234"})
    assert res.status_code == 400
