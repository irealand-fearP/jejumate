"""
테스트용 DB 세션 fixture.

주의: 로컬 개발 셸에 docker/postgres가 없어(사용 불가 환경) 실제 pgvector가 붙은
Postgres 대신 SQLite 인메모리 DB로 ORM 동작(모델 정의·제약조건·insert/select)을
검증한다. embedding 컬럼은 Postgres에서는 진짜 vector(1536)이지만, SQLite에서는
FlexibleVector 타입(app/db.py)이 자동으로 JSON 저장으로 대체해 같은 코드로 양쪽이
동작하게 한다. 실제 pgvector 인덱스(ivfflat)·CREATE EXTENSION 동작 자체는
alembic 마이그레이션 SQL 자체(offline 모드)로만 검증 가능하다.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
