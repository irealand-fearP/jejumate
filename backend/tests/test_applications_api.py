"""
태스크13: 참여 신청 API. 닉네임+메시지로 신청 → pending 저장.
신청/승인 데이터(applications)는 RAG 임베딩·검색 대상이 아니다(기획서 3장-11).
"""
from datetime import datetime, timedelta, timezone

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


def _seed_party_post(client, **overrides):
    session = client._session_factory()
    defaults = dict(
        source="user_post",
        post_type="party",
        category="ride",
        content="함덕 택시팟 구해요",
        author_nickname="글쓴이",
        original_timestamp=NOW,
        capacity=4,
        owner_secret="1234",
        embedding=[0.0] * 1536,
    )
    defaults.update(overrides)
    post = Post(**defaults)
    session.add(post)
    session.commit()
    session.refresh(post)
    session.close()
    return post


def test_apply_to_party_post_creates_pending_application(client):
    post = _seed_party_post(client)

    res = client.post(
        f"/posts/{post.id}/applications",
        json={"nickname": "신청자", "message": "같이 가고 싶어요"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["nickname"] == "신청자"
    assert body["message"] == "같이 가고 싶어요"
    assert body["status"] == "pending"

    session = client._session_factory()
    stored = session.query(Application).one()
    assert stored.post_id == post.id
    assert stored.status == "pending"
    session.close()


def test_apply_without_message_is_allowed(client):
    post = _seed_party_post(client)
    res = client.post(f"/posts/{post.id}/applications", json={"nickname": "신청자"})
    assert res.status_code == 201
    assert res.json()["message"] is None


def test_apply_to_nonexistent_post_returns_404(client):
    res = client.post(
        "/posts/00000000-0000-0000-0000-000000000000/applications",
        json={"nickname": "신청자"},
    )
    assert res.status_code == 404


def test_apply_to_info_post_rejected(client):
    post = _seed_party_post(client, post_type="info", category="food", capacity=None, owner_secret=None)
    res = client.post(f"/posts/{post.id}/applications", json={"nickname": "신청자"})
    assert res.status_code == 400


def test_apply_to_closed_post_rejected(client):
    post = _seed_party_post(client, status="closed")
    res = client.post(f"/posts/{post.id}/applications", json={"nickname": "신청자"})
    assert res.status_code == 400


def test_apply_to_expired_post_rejected(client):
    post = _seed_party_post(client, deadline=NOW - timedelta(minutes=1))
    res = client.post(f"/posts/{post.id}/applications", json={"nickname": "신청자"})
    assert res.status_code == 400


def test_application_does_not_create_a_searchable_post(client):
    """신청 데이터는 posts 테이블에 들어가지 않으므로 RAG 검색 결과에 영향 없다."""
    post = _seed_party_post(client)
    before = client.post("/search", json={"query": "택시팟"}).json()

    client.post(f"/posts/{post.id}/applications", json={"nickname": "신청자", "message": "저요"})

    after = client.post("/search", json={"query": "택시팟"}).json()
    assert before == after
