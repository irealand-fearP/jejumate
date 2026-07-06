"""
posts 테이블 ORM 모델 테스트.

완료 기준(태스크2): "테이블·인덱스 생성, 로컬에서 insert/select 확인" —
이 테스트가 그 로컬 검증 역할을 한다(SQLite 대체, conftest.py 주석 참고).
"""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Post


def _base_kwargs(**overrides):
    kwargs = dict(
        source="kakao",
        post_type="info",
        category="food",
        content="흑돼지 맛집 추천해주세요",
        author_nickname="제주감귤",
        original_timestamp=datetime.now(timezone.utc),
    )
    kwargs.update(overrides)
    return kwargs


def test_info_post_insert_and_select(db_session):
    """카톡 수집 info 글이 저장되고 그대로 조회되는지 확인한다."""
    post = Post(**_base_kwargs())
    db_session.add(post)
    db_session.commit()

    fetched = db_session.query(Post).one()
    assert fetched.id is not None
    assert fetched.source == "kakao"
    assert fetched.post_type == "info"
    assert fetched.category == "food"
    assert fetched.status == "active"  # 기본값
    assert fetched.capacity is None
    assert fetched.deadline is None
    assert fetched.owner_secret is None


def test_party_post_with_capacity_deadline_owner_secret(db_session):
    """직접 작성한 파티 모집 글은 정원·마감시간·글쓴이 권한 토큰을 가진다."""
    deadline = datetime.now(timezone.utc) + timedelta(hours=1)
    post = Post(
        **_base_kwargs(
            source="user_post",
            post_type="party",
            category="ride",
            content="함덕 가는 택시팟 구해요, 지금 출발",
            capacity=4,
            deadline=deadline,
            owner_secret="test-owner-secret-uuid",
        )
    )
    db_session.add(post)
    db_session.commit()

    fetched = db_session.query(Post).filter_by(category="ride").one()
    assert fetched.capacity == 4
    assert fetched.owner_secret == "test-owner-secret-uuid"
    assert fetched.deadline is not None


def test_embedding_round_trip(db_session):
    """1536차원 임베딩 벡터가 저장·조회 시 값 손실 없이 유지되는지 확인한다."""
    vector = [0.1] * 1536
    post = Post(**_base_kwargs(embedding=vector))
    db_session.add(post)
    db_session.commit()

    fetched = db_session.query(Post).one()
    assert len(fetched.embedding) == 1536
    assert fetched.embedding[0] == pytest.approx(0.1)


def test_metadata_jsonb_stores_extra_fields(db_session):
    """카테고리별 확장 필드(목적지 등)는 metadata에 스키마 변경 없이 담긴다."""
    post = Post(**_base_kwargs(metadata_={"destination": "함덕해수욕장"}))
    db_session.add(post)
    db_session.commit()

    fetched = db_session.query(Post).one()
    assert fetched.metadata_["destination"] == "함덕해수욕장"


@pytest.mark.parametrize("bad_post_type", ["party ", "PARTY", "unknown", ""])
def test_invalid_post_type_rejected(db_session, bad_post_type):
    """post_type은 party/info 외의 값을 허용하지 않는다."""
    post = Post(**_base_kwargs(post_type=bad_post_type))
    db_session.add(post)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("bad_category", ["nonexistent", "RIDE", ""])
def test_invalid_category_rejected(db_session, bad_category):
    """category는 6장에서 정의한 10종 외 값을 허용하지 않는다."""
    post = Post(**_base_kwargs(category=bad_category))
    db_session.add(post)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_status_rejected(db_session):
    """status는 active/closed 외의 값을 허용하지 않는다."""
    post = Post(**_base_kwargs(status="pending"))
    db_session.add(post)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
