"""
applications 테이블 ORM 모델 테스트 (태스크11).
post_id·nickname·message·status(pending/approved/rejected) 기본 검증.
"""
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Application, Post


def _make_post(session):
    post = Post(
        source="user_post",
        post_type="party",
        category="ride",
        content="함덕 택시팟 구해요",
        author_nickname="글쓴이",
        original_timestamp=datetime.now(timezone.utc),
        capacity=4,
        owner_secret="1234",
    )
    session.add(post)
    session.commit()
    return post


def test_application_insert_and_select_defaults_to_pending(db_session):
    post = _make_post(db_session)
    app_ = Application(post_id=post.id, nickname="신청자", message="같이 가고 싶어요")
    db_session.add(app_)
    db_session.commit()

    fetched = db_session.query(Application).one()
    assert fetched.post_id == post.id
    assert fetched.nickname == "신청자"
    assert fetched.message == "같이 가고 싶어요"
    assert fetched.status == "pending"


def test_application_message_is_optional(db_session):
    post = _make_post(db_session)
    app_ = Application(post_id=post.id, nickname="신청자")
    db_session.add(app_)
    db_session.commit()

    fetched = db_session.query(Application).one()
    assert fetched.message is None


@pytest.mark.parametrize("bad_status", ["approved_typo", "PENDING", ""])
def test_invalid_status_rejected(db_session, bad_status):
    post = _make_post(db_session)
    app_ = Application(post_id=post.id, nickname="신청자", status=bad_status)
    db_session.add(app_)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_application_references_nonexistent_post_id_is_allowed_at_orm_level(db_session):
    """SQLite는 기본적으로 FK 강제를 안 하므로 여기선 컬럼 존재만 확인.
    실제 FK 제약은 Postgres 마이그레이션(0002)에서 검증한다."""
    app_ = Application(post_id=uuid.uuid4(), nickname="신청자")
    db_session.add(app_)
    db_session.commit()
    assert db_session.query(Application).count() == 1
