"""
태스크9: 파티 등록 폼 API. 로그인 없이 4자리 관리 코드(owner_secret)를 발급해
글쓴이 권한을 증명한다(화면흐름.md 6장 "관리 코드: 4821" 참고).
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.main import app, get_db
from app.models import Post


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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_party_post_returns_4digit_owner_secret(client):
    res = client.post(
        "/posts/party",
        json={
            "category": "ride",
            "content": "함덕 가는 택시팟 구해요, 4시반 출발",
            "capacity": 4,
            "deadline_minutes": 60,
            "nickname": "제주감귤",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["owner_secret"].isdigit()
    assert len(body["owner_secret"]) == 4
    assert body["id"]


def test_created_party_post_is_stored_with_correct_fields(client):
    before = datetime.now(timezone.utc)
    res = client.post(
        "/posts/party",
        json={
            "category": "run",
            "content": "제주대 운동장 러닝 같이 하실 분",
            "capacity": 3,
            "deadline_minutes": 30,
            "nickname": "달리는춘식이",
        },
    )
    post_id = res.json()["id"]

    feed = client.get("/posts", params={"category": "run"})
    matched = [p for p in feed.json() if p["id"] == post_id]
    assert len(matched) == 1
    post = matched[0]
    assert post["source"] == "user_post"
    assert post["post_type"] == "party"
    assert post["category"] == "run"
    assert post["capacity"] == 3
    assert post["author_nickname"] == "달리는춘식이"
    # SQLite(테스트 DB)는 tzinfo를 버리므로(Postgres는 유지, app/expiry.py 참고)
    # naive로 맞춰서 비교한다.
    deadline = datetime.fromisoformat(post["deadline"]).replace(tzinfo=None)
    assert deadline > before.replace(tzinfo=None)


def test_rejects_info_category_for_party_registration(client):
    res = client.post(
        "/posts/party",
        json={
            "category": "food",
            "content": "잘못된 카테고리",
            "capacity": 2,
            "deadline_minutes": 30,
            "nickname": "누군가",
        },
    )
    assert res.status_code == 422


def test_created_party_post_is_searchable_via_rag(client):
    """등록 직후 RAG 질문에도 근거로 잡혀야 한다(기획서 2장 데모 시나리오 5번)."""
    client.post(
        "/posts/party",
        json={
            "category": "ride",
            "content": "함덕 택시팟 4시반 출발 구해요",
            "capacity": 4,
            "deadline_minutes": 60,
            "nickname": "제주감귤",
        },
    )
    res = client.post("/search", json={"query": "함덕 가는 택시팟 있어?"})
    body = res.json()
    assert len(body["evidence"]) == 1
    assert body["evidence"][0]["content"] == "함덕 택시팟 4시반 출발 구해요"


def test_rejects_invalid_capacity(client):
    res = client.post(
        "/posts/party",
        json={
            "category": "ride",
            "content": "정원이 이상함",
            "capacity": 0,
            "deadline_minutes": 30,
            "nickname": "누군가",
        },
    )
    assert res.status_code == 422
