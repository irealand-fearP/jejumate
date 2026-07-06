"""
태스크6 API 테스트: GET /posts(피드), POST /search(RAG).
SQLite 인메모리(StaticPool로 커넥션 공유) + MockEmbeddingProvider로 검증한다.
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
from app.models import Post

NOW = datetime(2026, 7, 6, 15, 0, tzinfo=timezone.utc)


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
        test_client._session_factory = TestSession  # 테스트에서 직접 데이터 넣을 때 씀
        yield test_client

    app.dependency_overrides.clear()


def _seed_post(client, **overrides):
    session = client._session_factory()
    defaults = dict(
        source="kakao",
        post_type="party",
        category="ride",
        content="함덕 택시팟 구해요",
        author_nickname="누군가",
        original_timestamp=NOW,
        embedding=[0.0] * 1536,
    )
    defaults.update(overrides)
    post = Post(**defaults)
    session.add(post)
    session.commit()
    session.refresh(post)
    session.close()
    return post


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_feed_excludes_closed_and_expired(client):
    # /posts는 실제 "읽는 시점"(진짜 현재 시각) 기준으로 만료를 판정하므로,
    # 마감시간은 고정된 NOW가 아니라 실제 wall-clock 기준 과거로 잡아야 한다.
    real_past = datetime.now(timezone.utc) - timedelta(minutes=1)
    active = _seed_post(client, content="유효한 글")
    _seed_post(client, content="마감된 글", status="closed")
    _seed_post(client, content="시간 지난 글", deadline=real_past)

    res = client.get("/posts")
    assert res.status_code == 200
    ids = {p["id"] for p in res.json()}
    assert str(active.id) in ids
    assert len(res.json()) == 1


def test_feed_category_filter(client):
    _seed_post(client, category="ride", content="택시팟")
    food = _seed_post(client, category="food", post_type="info", content="맛집")

    res = client.get("/posts", params={"category": "food"})
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["id"] == str(food.id)


def test_search_returns_answer_with_evidence(client):
    post = _seed_post(client, content="함덕 택시팟 구해요")

    res = client.post("/search", json={"query": "함덕 가는 택시팟 있어?"})
    assert res.status_code == 200
    body = res.json()
    assert "evidence" in body
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["id"] == str(post.id)
    assert body["evidence"][0]["content"] == "함덕 택시팟 구해요"


def test_search_no_match(client):
    _seed_post(client, category="food", post_type="info", content="흑돼지 맛집")

    res = client.post("/search", json={"query": "택시팟", "category": "stay"})
    assert res.status_code == 200
    body = res.json()
    assert body["answer"] == "지금 유효한 정보가 없어요"
    assert body["evidence"] == []


def test_search_excludes_closed_evidence(client):
    _seed_post(client, content="마감된 택시팟", status="closed")

    res = client.post("/search", json={"query": "택시팟"})
    body = res.json()
    assert body["evidence"] == []
